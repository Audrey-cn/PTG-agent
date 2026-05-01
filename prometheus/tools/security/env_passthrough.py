"""Environment variable passthrough registry."""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import TYPE_CHECKING

from prometheus.cli.config import cfg_get

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)

_allowed_env_vars_var: ContextVar[Set[str]] = ContextVar("_allowed_env_vars")


def _get_allowed() -> Set[str]:
    """Get or create the allowed env vars set for the current context/session."""
    try:
        return _allowed_env_vars_var.get()
    except LookupError:
        val: Set[str] = set()
        _allowed_env_vars_var.set(val)
        return val


_config_passthrough: frozenSet[str] | None = None


def _is_prometheus_provider_credential(name: str) -> bool:
    """True if ``name`` is a Prometheus-managed provider credential per
    ``_PROMETHEUS_PROVIDER_ENV_BLOCKLIST``.

    Skill-declared ``required_environment_variables`` frontmatter must
    not be able to override this list.
    """
    try:
        from prometheus.tools.environments.local import _PROMETHEUS_PROVIDER_ENV_BLOCKLIST
    except Exception:
        return False
    return name in _PROMETHEUS_PROVIDER_ENV_BLOCKLIST


def register_env_passthrough(var_names: Iterable[str]) -> None:
    """Register environment variable names as allowed in sandboxed environments.

    Typically called when a skill declares ``required_environment_variables``.

    Variables that are Prometheus-managed provider credentials (from
    ``_PROMETHEUS_PROVIDER_ENV_BLOCKLIST``) are rejected here to preserve
    the ``execute_code`` sandbox's credential-scrubbing guarantee.
    """
    for name in var_names:
        name = name.strip()
        if not name:
            continue
        if _is_prometheus_provider_credential(name):
            logger.warning(
                "env passthrough: refusing to register Prometheus provider "
                "credential %r (blocked by _PROMETHEUS_PROVIDER_ENV_BLOCKLIST). "
                "Skills must not override the execute_code sandbox's "
                "credential scrubbing.",
                name,
            )
            continue
        _get_allowed().add(name)
        logger.debug("env passthrough: registered %s", name)


def _load_config_passthrough() -> frozenSet[str]:
    """Load ``prometheus.env_passthrough`` from config.yaml (cached)."""
    global _config_passthrough
    if _config_passthrough is not None:
        return _config_passthrough

    result: Set[str] = set()
    try:
        from prometheus.cli.config import read_raw_config

        cfg = read_raw_config()
        passthrough = cfg_get(cfg, "terminal", "env_passthrough")
        if isinstance(passthrough, list):
            for item in passthrough:
                if isinstance(item, str) and item.strip():
                    result.add(item.strip())
    except Exception as e:
        logger.debug("Could not read prometheus.env_passthrough from config: %s", e)

    _config_passthrough = frozenset(result)
    return _config_passthrough


def is_env_passthrough(var_name: str) -> bool:
    """Check whether *var_name* is allowed to pass through to sandboxes.

    Returns ``True`` if the variable was registered by a skill or listed in
    the user's ``prometheus.env_passthrough`` config.
    """
    if var_name in _get_allowed():
        return True
    return var_name in _load_config_passthrough()


def get_all_passthrough() -> frozenSet[str]:
    """Return the union of skill-registered and config-based passthrough vars."""
    return frozenset(_get_allowed()) | _load_config_passthrough()


def clear_env_passthrough() -> None:
    """Reset the skill-scoped allowlist (e.g. on session reset)."""
    _get_allowed().clear()
