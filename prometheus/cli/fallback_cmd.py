"""prometheus fallback — manage the fallback provider chain."""

from __future__ import annotations

import copy
from typing import Any


def _read_chain(config: dict[str, Any]) -> list[dict[str, Any]]:
    chain = config.get("fallback_providers") or []
    if isinstance(chain, list):
        result = [
            dict(e) for e in chain if isinstance(e, dict) and e.get("provider") and e.get("model")
        ]
        if result:
            return result
    legacy = config.get("fallback_model")
    if isinstance(legacy, dict) and legacy.get("provider") and legacy.get("model"):
        return [dict(legacy)]
    if isinstance(legacy, list):
        return [
            dict(e) for e in legacy if isinstance(e, dict) and e.get("provider") and e.get("model")
        ]
    return []


def _write_chain(config: dict[str, Any], chain: list[dict[str, Any]]) -> None:
    config["fallback_providers"] = chain
    if "fallback_model" in config:
        config.pop("fallback_model", None)


def _format_entry(entry: dict[str, Any]) -> str:
    provider = entry.get("provider", "?")
    model = entry.get("model", "?")
    base = entry.get("base_url")
    suffix = f"  [{base}]" if base else ""
    return f"{model}  (via {provider}){suffix}"


def _extract_fallback_from_model_cfg(model_cfg: Any) -> dict[str, Any] | None:
    if not isinstance(model_cfg, dict):
        return None
    provider = (model_cfg.get("provider") or "").strip()
    model = (model_cfg.get("default") or model_cfg.get("model") or "").strip()
    if not provider or not model:
        return None
    entry: dict[str, Any] = {"provider": provider, "model": model}
    base_url = (model_cfg.get("base_url") or "").strip()
    if base_url:
        entry["base_url"] = base_url
    api_mode = (model_cfg.get("api_mode") or "").strip()
    if api_mode:
        entry["api_mode"] = api_mode
    return entry


def _snapshot_auth_active_provider() -> Any:
    try:
        from prometheus.cli.auth import _load_auth_store

        store = _load_auth_store()
        return store.get("active_provider")
    except Exception:
        return None


def _restore_auth_active_provider(value: Any) -> None:
    try:
        from prometheus.cli.auth import _auth_store_lock, _load_auth_store, _save_auth_store

        with _auth_store_lock():
            store = _load_auth_store()
            store["active_provider"] = value
            _save_auth_store(store)
    except Exception:
        pass


def cmd_fallback_list(args) -> None:
    from prometheus.cli.config import load_config

    config = load_config()
    chain = _read_chain(config)

    print()
    if not chain:
        print("  No fallback providers configured.")
        print()
        print("  Add one with:  prometheus fallback add")
        print()
        return

    primary = _describe_primary(config)
    if primary:
        print(f"  Primary:   {primary}")
        print()
    print(f"  Fallback chain ({len(chain)} {'entry' if len(chain) == 1 else 'entries'}):")
    for i, entry in enumerate(chain, 1):
        print(f"    {i}. {_format_entry(entry)}")
    print()
    print("  Tried in order when the primary fails (rate-limit, 5xx, connection errors).")
    print()


def _describe_primary(config: dict[str, Any]) -> str | None:
    model_cfg = config.get("model")
    if isinstance(model_cfg, dict):
        provider = (model_cfg.get("provider") or "?").strip() or "?"
        model = (model_cfg.get("default") or model_cfg.get("model") or "?").strip() or "?"
        return f"{model}  (via {provider})"
    if isinstance(model_cfg, str) and model_cfg.strip():
        return model_cfg.strip()
    return None


def cmd_fallback_add(args) -> None:
    from prometheus.cli.config import load_config, save_config
    from prometheus.cli.main import _require_tty, select_provider_and_model

    _require_tty("fallback add")

    before_cfg = load_config()
    model_before = copy.deepcopy(before_cfg.get("model"))
    active_provider_before = _snapshot_auth_active_provider()

    print()
    print("  Adding a fallback provider.  The picker below is the same one used by")
    print("  `prometheus model` — select the provider + model you want as a fallback.")
    print()

    try:
        select_provider_and_model(args=args)
    except SystemExit:
        _restore_model_cfg(model_before)
        _restore_auth_active_provider(active_provider_before)
        raise

    after_cfg = load_config()
    model_after = after_cfg.get("model")

    new_entry = _extract_fallback_from_model_cfg(model_after)
    if not new_entry:
        _restore_model_cfg(model_before)
        _restore_auth_active_provider(active_provider_before)
        print()
        print("  No fallback added.")
        return

    primary_entry = _extract_fallback_from_model_cfg(model_before)
    if (
        primary_entry
        and primary_entry["provider"] == new_entry["provider"]
        and primary_entry["model"] == new_entry["model"]
    ):
        _restore_model_cfg(model_before)
        _restore_auth_active_provider(active_provider_before)
        print()
        print(f"  Selected model matches the current primary ({_format_entry(new_entry)}).")
        print("  A provider cannot be a fallback for itself — no change.")
        return

    _restore_model_cfg(model_before)
    _restore_auth_active_provider(active_provider_before)

    final_cfg = load_config()
    chain = _read_chain(final_cfg)

    for existing in chain:
        if (
            existing.get("provider") == new_entry["provider"]
            and existing.get("model") == new_entry["model"]
        ):
            print()
            print(f"  {_format_entry(new_entry)} is already in the fallback chain — skipped.")
            return

    chain.append(new_entry)
    _write_chain(final_cfg, chain)
    save_config(final_cfg)

    print()
    print(f"  Added fallback: {_format_entry(new_entry)}")
    print(f"  Chain is now {len(chain)} {'entry' if len(chain) == 1 else 'entries'} long.")
    print()
    print("  Run `prometheus fallback list` to view, or `prometheus fallback remove` to delete.")


def _restore_model_cfg(model_before: Any) -> None:
    from prometheus.cli.config import load_config, save_config

    cfg = load_config()
    if model_before is None:
        cfg.pop("model", None)
    else:
        cfg["model"] = copy.deepcopy(model_before)
    save_config(cfg)


def cmd_fallback_remove(args) -> None:
    from prometheus.cli.config import load_config, save_config

    config = load_config()
    chain = _read_chain(config)

    if not chain:
        print()
        print("  No fallback providers configured — nothing to remove.")
        print()
        return

    choices = [_format_entry(e) for e in chain]
    choices.append("Cancel")

    try:
        from prometheus.cli.setup import _curses_prompt_choice

        idx = _curses_prompt_choice("Select a fallback to remove:", choices, 0)
    except Exception:
        idx = _numbered_pick("Select a fallback to remove:", choices)

    if idx is None or idx < 0 or idx >= len(chain):
        print()
        print("  Cancelled — no change.")
        return

    removed = chain.pop(idx)
    _write_chain(config, chain)
    save_config(config)

    print()
    print(f"  Removed fallback: {_format_entry(removed)}")
    if chain:
        print(f"  Chain is now {len(chain)} {'entry' if len(chain) == 1 else 'entries'} long.")
    else:
        print("  Fallback chain is now empty.")
    print()


def cmd_fallback_clear(args) -> None:
    from prometheus.cli.config import load_config, save_config

    config = load_config()
    chain = _read_chain(config)

    if not chain:
        print()
        print("  No fallback providers configured — nothing to clear.")
        print()
        return

    print()
    print(f"  Current fallback chain ({len(chain)} {'entry' if len(chain) == 1 else 'entries'}):")
    for i, entry in enumerate(chain, 1):
        print(f"    {i}. {_format_entry(entry)}")
    print()
    try:
        resp = input("  Clear all entries? [y/N]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        print("  Cancelled.")
        return
    if resp not in ("y", "yes"):
        print("  Cancelled — no change.")
        return

    _write_chain(config, [])
    save_config(config)
    print()
    print("  Fallback chain cleared.")
    print()


def _numbered_pick(question: str, choices: list[str]) -> int | None:
    print(question)
    for i, c in enumerate(choices, 1):
        print(f"  {i}. {c}")
    print()
    while True:
        try:
            val = input(f"Choice [1-{len(choices)}]: ").strip()
            if not val:
                return None
            idx = int(val) - 1
            if 0 <= idx < len(choices):
                return idx
            print(f"Please enter 1-{len(choices)}")
        except ValueError:
            print("Please enter a number")
        except (KeyboardInterrupt, EOFError):
            print()
            return None


def cmd_fallback(args) -> None:
    sub = getattr(args, "fallback_command", None)
    if sub in (None, "", "list", "ls"):
        cmd_fallback_list(args)
    elif sub == "add":
        cmd_fallback_add(args)
    elif sub in ("remove", "rm"):
        cmd_fallback_remove(args)
    elif sub == "clear":
        cmd_fallback_clear(args)
    else:
        print(f"Unknown fallback subcommand: {sub}")
        print("Use one of: list, add, remove, clear")
        raise SystemExit(2)
