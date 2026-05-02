"""Prometheus Plugin System."""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import logging
import os
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from prometheus.constants_core import get_prometheus_home
from prometheus.utils import env_var_enabled

if TYPE_CHECKING:
    from collections.abc import Callable


def get_bundled_plugins_dir() -> Path:
    """Locate the bundled ``plugins/`` directory.

    Honours ``PROMETHEUS_BUNDLED_PLUGINS`` (set by the Nix wrapper / packaged
    installs) so read-only store paths are consulted first.  Falls back to
    the in-repo path used during development.
    """
    env_override = os.getenv("PROMETHEUS_BUNDLED_PLUGINS")
    if env_override:
        return Path(env_override)
    return Path(__file__).resolve().parent.parent / "plugins"


try:
    import yaml
except ImportError:
    yaml = None


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_HOOKS: set[str] = {
    "pre_tool_call",
    "post_tool_call",
    "transform_terminal_output",
    "transform_tool_result",
    "pre_llm_call",
    "post_llm_call",
    "pre_api_request",
    "post_api_request",
    "on_session_start",
    "on_session_end",
    "on_session_finalize",
    "on_session_reset",
    "subagent_stop",
    "pre_gateway_dispatch",
    "pre_approval_request",
    "post_approval_response",
}

ENTRY_POINTS_GROUP = "prometheus_agent.plugins"

_NS_PARENT = "prometheus_plugins"


def _env_enabled(name: str) -> bool:
    """Return True when an env var is set to a truthy opt-in value."""
    return env_var_enabled(name)


def _get_disabled_plugins() -> set:
    """Read the disabled plugins list from config.yaml.

    Kept for backward compat and explicit deny-list semantics. A plugin
    name in this set will never load, even if it appears in
    ``plugins.enabled``.
    """
    try:
        from prometheus.config import PrometheusConfig

        config = PrometheusConfig.load()
        disabled = config.get("plugins.disabled", default=[])
        return set(disabled) if isinstance(disabled, list) else set()
    except Exception:
        return set()


def _get_enabled_plugins() -> set | None:
    """Read the enabled-plugins allow-list from config.yaml.

    Plugins are opt-in by default — only plugins whose name appears in
    this set are loaded. Returns:

    * ``None`` — the key is missing or malformed. Callers should treat
      this as "nothing enabled yet" (the opt-in default); the first
      ``migrate_config`` run populates the key with a grandfathered set
      of currently-installed user plugins so existing setups don't
      break on upgrade.
    * ``set()`` — an empty list was explicitly set; nothing loads.
    * ``set(...)`` — the concrete allow-list.
    """
    try:
        from prometheus.config import PrometheusConfig

        config = PrometheusConfig.load()
        plugins_cfg = config.get("plugins")
        if not isinstance(plugins_cfg, dict):
            return None
        if "enabled" not in plugins_cfg:
            return None
        enabled = plugins_cfg.get("enabled")
        if not isinstance(enabled, list):
            return None
        return set(enabled)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

_VALID_PLUGIN_KINDS: set[str] = {"standalone", "backend", "exclusive", "platform"}


@dataclass
class PluginManifest:
    """Parsed representation of a plugin.yaml manifest."""

    name: str
    version: str = ""
    description: str = ""
    author: str = ""
    requires_env: list[str | dict[str, Any]] = field(default_factory=list)
    provides_tools: list[str] = field(default_factory=list)
    provides_hooks: list[str] = field(default_factory=list)
    source: str = ""
    path: str | None = None
    kind: str = "standalone"
    key: str = ""


@dataclass
class LoadedPlugin:
    """Runtime state for a single loaded plugin."""

    manifest: PluginManifest
    module: types.ModuleType | None = None
    tools_registered: list[str] = field(default_factory=list)
    hooks_registered: list[str] = field(default_factory=list)
    commands_registered: list[str] = field(default_factory=list)
    enabled: bool = False
    error: str | None = None


# ---------------------------------------------------------------------------
# PluginContext  – handed to each plugin's ``register()`` function
# ---------------------------------------------------------------------------


class PluginContext:
    """Facade given to plugins so they can register tools and hooks."""

    def __init__(self, manifest: PluginManifest, manager: PluginManager):
        self.manifest = manifest
        self._manager = manager

    def register_tool(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        check_fn: Callable | None = None,
        requires_env: list | None = None,
        is_async: bool = False,
        description: str = "",
        emoji: str = "",
    ) -> None:
        """Register a tool in the global registry **and** track it as plugin-provided."""
        from prometheus.tools.registry import registry

        registry.register(
            name=name,
            toolset=toolset,
            schema=schema,
            handler=handler,
            check_fn=check_fn,
            requires_env=requires_env,
            is_async=is_async,
            description=description,
            emoji=emoji,
        )
        self._manager._plugin_tool_names.add(name)
        logger.debug("Plugin %s registered tool: %s", self.manifest.name, name)

    def inject_message(self, content: str, role: str = "user") -> bool:
        """Inject a message into the active conversation.

        If the agent is idle (waiting for user input), this starts a new turn.
        If the agent is running, this interrupts and injects the message.

        This enables plugins (e.g. remote control viewers, messaging bridges)
        to send messages into the conversation from external sources.

        Returns True if the message was queued successfully.
        """
        cli = self._manager._cli_ref
        if cli is None:
            logger.warning("inject_message: no CLI reference (not available in gateway mode)")
            return False

        msg = content if role == "user" else f"[{role}] {content}"

        if getattr(cli, "_agent_running", False):
            cli._interrupt_queue.put(msg)
        else:
            cli._pending_input.put(msg)
        return True

    def register_cli_command(
        self,
        name: str,
        help: str,
        setup_fn: Callable,
        handler_fn: Callable | None = None,
        description: str = "",
    ) -> None:
        """Register a CLI subcommand (e.g. ``prometheus honcho ...``)."""
        self._manager._cli_commands[name] = {
            "name": name,
            "help": help,
            "description": description,
            "setup_fn": setup_fn,
            "handler_fn": handler_fn,
            "plugin": self.manifest.name,
        }
        logger.debug("Plugin %s registered CLI command: %s", self.manifest.name, name)

    def register_command(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        args_hint: str = "",
    ) -> None:
        """Register a slash command (e.g. ``/lcm``) available in CLI and gateway sessions."""
        clean = name.lower().strip().lstrip("/").replace(" ", "-")
        if not clean:
            logger.warning(
                "Plugin '%s' tried to register a command with an empty name.",
                self.manifest.name,
            )
            return

        try:
            from prometheus.cli.commands import resolve_command

            if resolve_command(clean) is not None:
                logger.warning(
                    "Plugin '%s' tried to register command '/%s' which conflicts "
                    "with a built-in command. Skipping.",
                    self.manifest.name,
                    clean,
                )
                return
        except Exception:
            pass

        self._manager._plugin_commands[clean] = {
            "handler": handler,
            "description": description or "Plugin command",
            "plugin": self.manifest.name,
            "args_hint": (args_hint or "").strip(),
        }
        logger.debug("Plugin %s registered command: /%s", self.manifest.name, clean)

    def dispatch_tool(self, tool_name: str, args: dict, **kwargs) -> str:
        """Dispatch a tool call through the registry, with parent agent context."""
        from prometheus.tools.registry import registry

        if "parent_agent" not in kwargs:
            cli = self._manager._cli_ref
            agent = getattr(cli, "agent", None) if cli else None
            if agent is not None:
                kwargs["parent_agent"] = agent

        return registry.dispatch(tool_name, args, **kwargs)

    def register_context_engine(self, engine) -> None:
        """Register a context engine to replace the built-in ContextCompressor."""
        if self._manager._context_engine is not None:
            logger.warning(
                "Plugin '%s' tried to register a context engine, but one is "
                "already registered. Only one context engine plugin is allowed.",
                self.manifest.name,
            )
            return
        from prometheus.agent.context_engine import ContextEngine

        if not isinstance(engine, ContextEngine):
            logger.warning(
                "Plugin '%s' tried to register a context engine that does not "
                "inherit from ContextEngine. Ignoring.",
                self.manifest.name,
            )
            return
        self._manager._context_engine = engine
        logger.info(
            "Plugin '%s' registered context engine: %s",
            self.manifest.name,
            engine.name,
        )

    def register_image_gen_provider(self, provider) -> None:
        """Register an image generation backend."""
        from prometheus.agent.image_gen_provider import ImageGenProvider
        from prometheus.agent.image_gen_registry import register_provider

        if not isinstance(provider, ImageGenProvider):
            logger.warning(
                "Plugin '%s' tried to register an image_gen provider that does "
                "not inherit from ImageGenProvider. Ignoring.",
                self.manifest.name,
            )
            return
        register_provider(provider)
        logger.info(
            "Plugin '%s' registered image_gen provider: %s",
            self.manifest.name,
            provider.name,
        )

    def register_platform(
        self,
        name: str,
        label: str,
        adapter_factory: Callable,
        check_fn: Callable,
        validate_config: Callable | None = None,
        required_env: list | None = None,
        install_hint: str = "",
        **entry_kwargs: Any,
    ) -> None:
        """Register a gateway platform adapter."""
        from prometheus.gateway.platform_registry import PlatformEntry, platform_registry

        entry_kwargs.setdefault("plugin_name", self.manifest.name)
        entry = PlatformEntry(
            name=name,
            label=label,
            adapter_factory=adapter_factory,
            check_fn=check_fn,
            validate_config=validate_config,
            required_env=required_env or [],
            install_hint=install_hint,
            source="plugin",
            **entry_kwargs,
        )
        platform_registry.register(entry)
        self._manager._plugin_platform_names.add(name)
        logger.debug(
            "Plugin %s registered platform: %s",
            self.manifest.name,
            name,
        )

    def register_hook(self, hook_name: str, callback: Callable) -> None:
        """Register a lifecycle hook callback."""
        if hook_name not in VALID_HOOKS:
            logger.warning(
                "Plugin '%s' registered unknown hook '%s' (valid: %s)",
                self.manifest.name,
                hook_name,
                ", ".join(sorted(VALID_HOOKS)),
            )
        self._manager._hooks.setdefault(hook_name, []).append(callback)
        logger.debug("Plugin %s registered hook: %s", self.manifest.name, hook_name)

    def register_skill(
        self,
        name: str,
        path: Path,
        description: str = "",
    ) -> None:
        """Register a read-only skill provided by this plugin."""
        from prometheus.skill_utils import _NAMESPACE_RE

        if ":" in name:
            raise ValueError(
                f"Skill name '{name}' must not contain ':' "
                f"(the namespace is derived from the plugin name "
                f"'{self.manifest.name}' automatically)."
            )
        if not name or not _NAMESPACE_RE.match(name):
            raise ValueError(f"Invalid skill name '{name}'. Must match [a-zA-Z0-9_-]+.")
        if not path.exists():
            raise FileNotFoundError(f"SKILL.md not found at {path}")

        qualified = f"{self.manifest.name}:{name}"
        self._manager._plugin_skills[qualified] = {
            "path": path,
            "plugin": self.manifest.name,
            "bare_name": name,
            "description": description,
        }
        logger.debug(
            "Plugin %s registered skill: %s",
            self.manifest.name,
            qualified,
        )


# ---------------------------------------------------------------------------
# PluginManager
# ---------------------------------------------------------------------------


class PluginManager:
    """Central manager that discovers, loads, and invokes plugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, LoadedPlugin] = {}
        self._hooks: dict[str, list[Callable]] = {}
        self._plugin_tool_names: set[str] = set()
        self._plugin_platform_names: set[str] = set()
        self._cli_commands: dict[str, dict] = {}
        self._context_engine = None
        self._plugin_commands: dict[str, dict] = {}
        self._discovered: bool = False
        self._cli_ref = None
        self._plugin_skills: dict[str, dict[str, Any]] = {}

    def discover_and_load(self, force: bool = False) -> None:
        """Scan all plugin sources and load each plugin found."""
        if self._discovered and not force:
            return
        if force:
            self._plugins.clear()
            self._hooks.clear()
            self._plugin_tool_names.clear()
            self._cli_commands.clear()
            self._plugin_commands.clear()
            self._plugin_skills.clear()
            self._context_engine = None
        self._discovered = True

        manifests: list[PluginManifest] = []

        repo_plugins = get_bundled_plugins_dir()
        manifests.extend(
            self._scan_directory(
                repo_plugins,
                source="bundled",
                skip_names={"memory", "context_engine", "platforms"},
            )
        )
        manifests.extend(self._scan_directory(repo_plugins / "platforms", source="bundled"))

        user_dir = get_prometheus_home() / "plugins"
        manifests.extend(self._scan_directory(user_dir, source="user"))

        if _env_enabled("PROMETHEUS_ENABLE_PROJECT_PLUGINS"):
            project_dir = Path.cwd() / ".prometheus" / "plugins"
            manifests.extend(self._scan_directory(project_dir, source="project"))

        manifests.extend(self._scan_entry_points())

        disabled = _get_disabled_plugins()
        enabled = _get_enabled_plugins()
        winners: dict[str, PluginManifest] = {}
        for manifest in manifests:
            winners[manifest.key or manifest.name] = manifest
        for manifest in winners.values():
            lookup_key = manifest.key or manifest.name

            if lookup_key in disabled or manifest.name in disabled:
                loaded = LoadedPlugin(manifest=manifest, enabled=False)
                loaded.error = "disabled via config"
                self._plugins[lookup_key] = loaded
                logger.debug("Skipping disabled plugin '%s'", lookup_key)
                continue

            if manifest.kind == "exclusive":
                loaded = LoadedPlugin(manifest=manifest, enabled=False)
                loaded.error = "exclusive plugin — activate via <category>.provider config"
                self._plugins[lookup_key] = loaded
                logger.debug(
                    "Skipping '%s' (exclusive, handled by category discovery)",
                    lookup_key,
                )
                continue

            if manifest.source == "bundled" and manifest.kind in ("backend", "platform"):
                self._load_plugin(manifest)
                continue

            is_enabled = enabled is not None and (lookup_key in enabled or manifest.name in enabled)
            if not is_enabled:
                loaded = LoadedPlugin(manifest=manifest, enabled=False)
                loaded.error = f"not enabled in config (run `prometheus plugins enable {lookup_key}` to activate)"
                self._plugins[lookup_key] = loaded
                logger.debug("Skipping '%s' (not in plugins.enabled)", lookup_key)
                continue
            self._load_plugin(manifest)

        if manifests:
            logger.info(
                "Plugin discovery complete: %d found, %d enabled",
                len(self._plugins),
                sum(1 for p in self._plugins.values() if p.enabled),
            )

    def _scan_directory(
        self,
        path: Path,
        source: str,
        skip_names: set[str] | None = None,
    ) -> list[PluginManifest]:
        """Read ``plugin.yaml`` manifests from subdirectories of *path*."""
        return self._scan_directory_level(path, source, skip_names=skip_names, prefix="", depth=0)

    def _scan_directory_level(
        self,
        path: Path,
        source: str,
        *,
        skip_names: set[str] | None,
        prefix: str,
        depth: int,
    ) -> list[PluginManifest]:
        """Recursive implementation of :meth:`_scan_directory`."""
        manifests: list[PluginManifest] = []
        if not path.is_dir():
            return manifests

        for child in sorted(path.iterdir()):
            if not child.is_dir():
                continue
            if depth == 0 and skip_names and child.name in skip_names:
                continue
            manifest_file = child / "plugin.yaml"
            if not manifest_file.exists():
                manifest_file = child / "plugin.yml"

            if manifest_file.exists():
                manifest = self._parse_manifest(manifest_file, child, source, prefix)
                if manifest is not None:
                    manifests.append(manifest)
                continue

            if depth >= 1:
                logger.debug("Skipping %s (no plugin.yaml, depth cap reached)", child)
                continue

            sub_prefix = f"{prefix}/{child.name}" if prefix else child.name
            manifests.extend(
                self._scan_directory_level(
                    child,
                    source,
                    skip_names=None,
                    prefix=sub_prefix,
                    depth=depth + 1,
                )
            )

        return manifests

    def _parse_manifest(
        self,
        manifest_file: Path,
        plugin_dir: Path,
        source: str,
        prefix: str,
    ) -> PluginManifest | None:
        """Parse a single ``plugin.yaml`` into a :class:`PluginManifest`."""
        try:
            if yaml is None:
                logger.warning("PyYAML not installed – cannot load %s", manifest_file)
                return None
            data = yaml.safe_load(manifest_file.read_text()) or {}

            name = data.get("name", plugin_dir.name)
            key = f"{prefix}/{plugin_dir.name}" if prefix else name

            raw_kind = data.get("kind", "standalone")
            if not isinstance(raw_kind, str):
                raw_kind = "standalone"
            kind = raw_kind.strip().lower()
            if kind not in _VALID_PLUGIN_KINDS:
                logger.warning(
                    "Plugin %s: unknown kind '%s' (valid: %s); treating as 'standalone'",
                    key,
                    raw_kind,
                    ", ".join(sorted(_VALID_PLUGIN_KINDS)),
                )
                kind = "standalone"

            if kind == "standalone" and "kind" not in data:
                init_file = plugin_dir / "__init__.py"
                if init_file.exists():
                    try:
                        source_text = init_file.read_text(errors="replace")[:8192]
                        if (
                            "register_memory_provider" in source_text
                            or "MemoryProvider" in source_text
                        ):
                            kind = "exclusive"
                            logger.debug(
                                "Plugin %s: detected memory provider, treating as kind='exclusive'",
                                key,
                            )
                    except Exception:
                        pass

            return PluginManifest(
                name=name,
                version=str(data.get("version", "")),
                description=data.get("description", ""),
                author=data.get("author", ""),
                requires_env=data.get("requires_env", []),
                provides_tools=data.get("provides_tools", []),
                provides_hooks=data.get("provides_hooks", []),
                source=source,
                path=str(plugin_dir),
                kind=kind,
                key=key,
            )
        except Exception as exc:
            logger.warning("Failed to parse %s: %s", manifest_file, exc)
            return None

    def _scan_entry_points(self) -> list[PluginManifest]:
        """Check ``importlib.metadata`` for pip-installed plugins."""
        manifests: list[PluginManifest] = []
        try:
            eps = importlib.metadata.entry_points()
            if hasattr(eps, "select"):
                group_eps = eps.select(group=ENTRY_POINTS_GROUP)
            elif isinstance(eps, dict):
                group_eps = eps.get(ENTRY_POINTS_GROUP, [])
            else:
                group_eps = [ep for ep in eps if ep.group == ENTRY_POINTS_GROUP]

            for ep in group_eps:
                manifest = PluginManifest(
                    name=ep.name,
                    source="entrypoint",
                    path=ep.value,
                    key=ep.name,
                )
                manifests.append(manifest)
        except Exception as exc:
            logger.debug("Entry-point scan failed: %s", exc)

        return manifests

    def _load_plugin(self, manifest: PluginManifest) -> None:
        """Import a plugin module and call its ``register(ctx)`` function."""
        loaded = LoadedPlugin(manifest=manifest)

        try:
            if manifest.source in ("user", "project", "bundled"):
                module = self._load_directory_module(manifest)
            else:
                module = self._load_entrypoint_module(manifest)

            loaded.module = module

            register_fn = getattr(module, "register", None)
            if register_fn is None:
                loaded.error = "no register() function"
                logger.warning("Plugin '%s' has no register() function", manifest.name)
            else:
                ctx = PluginContext(manifest, self)
                register_fn(ctx)
                loaded.tools_registered = [
                    t
                    for t in self._plugin_tool_names
                    if t not in {n for name, p in self._plugins.items() for n in p.tools_registered}
                ]
                loaded.hooks_registered = list(
                    {h for h, cbs in self._hooks.items() if cbs}
                    - {h for name, p in self._plugins.items() for h in p.hooks_registered}
                )
                loaded.commands_registered = [
                    c
                    for c in self._plugin_commands
                    if self._plugin_commands[c].get("plugin") == manifest.name
                ]
                loaded.enabled = True

        except Exception as exc:
            loaded.error = str(exc)
            logger.warning("Failed to load plugin '%s': %s", manifest.name, exc)

        self._plugins[manifest.key or manifest.name] = loaded

    def _load_directory_module(self, manifest: PluginManifest) -> types.ModuleType:
        """Import a directory-based plugin as ``prometheus_plugins.<slug>``."""
        plugin_dir = Path(manifest.path)
        init_file = plugin_dir / "__init__.py"
        if not init_file.exists():
            raise FileNotFoundError(f"No __init__.py in {plugin_dir}")

        if _NS_PARENT not in sys.modules:
            ns_pkg = types.ModuleType(_NS_PARENT)
            ns_pkg.__path__ = []
            ns_pkg.__package__ = _NS_PARENT
            sys.modules[_NS_PARENT] = ns_pkg

        key = manifest.key or manifest.name
        slug = key.replace("/", "__").replace("-", "_")
        module_name = f"{_NS_PARENT}.{slug}"
        spec = importlib.util.spec_from_file_location(
            module_name,
            init_file,
            submodule_search_locations=[str(plugin_dir)],
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for {init_file}")

        module = importlib.util.module_from_spec(spec)
        module.__package__ = module_name
        module.__path__ = [str(plugin_dir)]
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def _load_entrypoint_module(self, manifest: PluginManifest) -> types.ModuleType:
        """Load a pip-installed plugin via its entry-point reference."""
        eps = importlib.metadata.entry_points()
        if hasattr(eps, "select"):
            group_eps = eps.select(group=ENTRY_POINTS_GROUP)
        elif isinstance(eps, dict):
            group_eps = eps.get(ENTRY_POINTS_GROUP, [])
        else:
            group_eps = [ep for ep in eps if ep.group == ENTRY_POINTS_GROUP]

        for ep in group_eps:
            if ep.name == manifest.name:
                return ep.load()

        raise ImportError(
            f"Entry point '{manifest.name}' not found in group '{ENTRY_POINTS_GROUP}'"
        )

    def invoke_hook(self, hook_name: str, **kwargs: Any) -> list[Any]:
        """Call all registered callbacks for *hook_name*."""
        callbacks = self._hooks.get(hook_name, [])
        results: list[Any] = []
        for cb in callbacks:
            try:
                ret = cb(**kwargs)
                if ret is not None:
                    results.append(ret)
            except Exception as exc:
                logger.warning(
                    "Hook '%s' callback %s raised: %s",
                    hook_name,
                    getattr(cb, "__name__", repr(cb)),
                    exc,
                )
        return results

    def list_plugins(self) -> list[dict[str, Any]]:
        """Return a list of info dicts for all discovered plugins."""
        result: list[dict[str, Any]] = []
        for _key, loaded in sorted(self._plugins.items()):
            result.append(
                {
                    "name": loaded.manifest.name,
                    "key": loaded.manifest.key or loaded.manifest.name,
                    "kind": loaded.manifest.kind,
                    "version": loaded.manifest.version,
                    "description": loaded.manifest.description,
                    "source": loaded.manifest.source,
                    "enabled": loaded.enabled,
                    "tools": len(loaded.tools_registered),
                    "hooks": len(loaded.hooks_registered),
                    "commands": len(loaded.commands_registered),
                    "error": loaded.error,
                }
            )
        return result

    def find_plugin_skill(self, qualified_name: str) -> Path | None:
        """Return the ``Path`` to a plugin skill's SKILL.md, or ``None``."""
        entry = self._plugin_skills.get(qualified_name)
        return entry["path"] if entry else None

    def list_plugin_skills(self, plugin_name: str) -> list[str]:
        """Return sorted bare names of all skills registered by *plugin_name*."""
        prefix = f"{plugin_name}:"
        return sorted(
            e["bare_name"] for qn, e in self._plugin_skills.items() if qn.startswith(prefix)
        )

    def remove_plugin_skill(self, qualified_name: str) -> None:
        """Remove a stale registry entry (silently ignores missing keys)."""
        self._plugin_skills.pop(qualified_name, None)


# ---------------------------------------------------------------------------
# Module-level singleton & convenience functions
# ---------------------------------------------------------------------------

_plugin_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """Return (and lazily create) the global PluginManager singleton."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


def discover_plugins(force: bool = False) -> None:
    """Discover and load all plugins."""
    get_plugin_manager().discover_and_load(force=force)


def invoke_hook(hook_name: str, **kwargs: Any) -> list[Any]:
    """Invoke a lifecycle hook on all loaded plugins."""
    return get_plugin_manager().invoke_hook(hook_name, **kwargs)


def get_pre_tool_call_block_message(
    tool_name: str,
    args: dict[str, Any] | None,
    task_id: str = "",
    session_id: str = "",
    tool_call_id: str = "",
) -> str | None:
    """Check ``pre_tool_call`` hooks for a blocking directive."""
    hook_results = invoke_hook(
        "pre_tool_call",
        tool_name=tool_name,
        args=args if isinstance(args, dict) else {},
        task_id=task_id,
        session_id=session_id,
        tool_call_id=tool_call_id,
    )

    for result in hook_results:
        if not isinstance(result, dict):
            continue
        if result.get("action") != "block":
            continue
        message = result.get("message")
        if isinstance(message, str) and message:
            return message

    return None


def _ensure_plugins_discovered(force: bool = False) -> PluginManager:
    """Return the global manager after ensuring plugin discovery has run."""
    manager = get_plugin_manager()
    manager.discover_and_load(force=force)
    return manager


def get_plugin_context_engine():
    """Return the plugin-registered context engine, or None."""
    return _ensure_plugins_discovered()._context_engine


def get_plugin_command_handler(name: str) -> Callable | None:
    """Return the handler for a plugin-registered slash command, or ``None``."""
    entry = _ensure_plugins_discovered()._plugin_commands.get(name)
    return entry["handler"] if entry else None


def get_plugin_commands() -> dict[str, dict]:
    """Return the full plugin commands dict (name → {handler, description, plugin})."""
    return _ensure_plugins_discovered()._plugin_commands


def get_plugin_toolsets() -> list[tuple]:
    """Return plugin toolsets as ``(key, label, description)`` tuples."""
    manager = get_plugin_manager()
    if not manager._plugin_tool_names:
        return []

    try:
        from prometheus.tools.registry import registry
    except Exception:
        return []

    toolset_tools: dict[str, list[str]] = {}
    toolset_plugin: dict[str, LoadedPlugin] = {}
    for tool_name in manager._plugin_tool_names:
        entry = registry.get_entry(tool_name)
        if not entry:
            continue
        ts = entry.toolset
        toolset_tools.setdefault(ts, []).append(entry.name)

    for _name, loaded in manager._plugins.items():
        for tool_name in loaded.tools_registered:
            entry = registry.get_entry(tool_name)
            if entry and entry.toolset in toolset_tools:
                toolset_plugin.setdefault(entry.toolset, loaded)

    result = []
    for ts_key in sorted(toolset_tools):
        plugin = toolset_plugin.get(ts_key)
        label = f"🔌 {ts_key.replace('_', ' ').title()}"
        if plugin and plugin.manifest.description:
            desc = plugin.manifest.description
        else:
            desc = ", ".join(sorted(toolset_tools[ts_key]))
        result.append((ts_key, label, desc))

    return result
