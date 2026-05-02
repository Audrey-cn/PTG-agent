"""Slash command definitions and autocomplete for the Prometheus CLI."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

try:
    from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
    from prompt_toolkit.completion import Completer, Completion
except ImportError:
    AutoSuggest = object
    Completer = object
    Suggestion = None
    Completion = None


@dataclass(frozen=True)
class CommandDef:
    """Definition of a single slash command."""

    name: str
    description: str
    category: str
    aliases: Tuple[str, ...] = ()
    args_hint: str = ""
    subcommands: Tuple[str, ...] = ()
    cli_only: bool = False
    gateway_only: bool = False
    gateway_config_gate: Optional[str] = None


COMMAND_REGISTRY: list[CommandDef] = [
    # Session
    CommandDef(
        "new", "Start a new session (fresh session ID + history)", "Session", aliases=("reset",)
    ),
    CommandDef("clear", "Clear screen and start a new session", "Session", cli_only=True),
    CommandDef(
        "redraw", "Force a full UI repaint (recovers from terminal drift)", "Session", cli_only=True
    ),
    CommandDef("history", "Show conversation history", "Session", cli_only=True),
    CommandDef("save", "Save the current conversation", "Session", cli_only=True),
    CommandDef("retry", "Retry the last message (resend to agent)", "Session"),
    CommandDef("undo", "Remove the last user/assistant exchange", "Session"),
    CommandDef("title", "Set a title for the current session", "Session", args_hint="[name]"),
    CommandDef(
        "branch",
        "Branch the current session (explore a different path)",
        "Session",
        aliases=("fork",),
        args_hint="[name]",
    ),
    CommandDef(
        "compress", "Manually compress conversation context", "Session", args_hint="[focus topic]"
    ),
    CommandDef(
        "rollback", "List or restore filesystem checkpoints", "Session", args_hint="[number]"
    ),
    CommandDef(
        "snapshot",
        "Create or restore state snapshots of Prometheus config/state",
        "Session",
        cli_only=True,
        aliases=("snap",),
        args_hint="[create|restore <id>|prune]",
    ),
    CommandDef("stop", "Kill all running background processes", "Session"),
    CommandDef(
        "approve",
        "Approve a pending dangerous command",
        "Session",
        gateway_only=True,
        args_hint="[session|always]",
    ),
    CommandDef("deny", "Deny a pending dangerous command", "Session", gateway_only=True),
    CommandDef(
        "background",
        "Run a prompt in the background",
        "Session",
        aliases=("bg", "btw"),
        args_hint="<prompt>",
    ),
    CommandDef("agents", "Show active agents and running tasks", "Session", aliases=("tasks",)),
    CommandDef(
        "queue",
        "Queue a prompt for the next turn (doesn't interrupt)",
        "Session",
        aliases=("q",),
        args_hint="<prompt>",
    ),
    CommandDef(
        "steer",
        "Inject a message after the next tool call without interrupting",
        "Session",
        args_hint="<prompt>",
    ),
    CommandDef("status", "Show session info", "Session"),
    CommandDef("profile", "Show active profile name and home directory", "Info"),
    CommandDef(
        "sethome",
        "Set this chat as the home channel",
        "Session",
        gateway_only=True,
        aliases=("set-home",),
    ),
    CommandDef("resume", "Resume a previously-named session", "Session", args_hint="[name]"),
    # Configuration
    CommandDef("config", "Show current configuration", "Configuration", cli_only=True),
    CommandDef(
        "model",
        "Switch model for this session",
        "Configuration",
        aliases=("provider",),
        args_hint="[model] [--provider name] [--global]",
    ),
    CommandDef("gquota", "Show Google Gemini Code Assist quota usage", "Info", cli_only=True),
    CommandDef("personality", "Set a predefined personality", "Configuration", args_hint="[name]"),
    CommandDef(
        "statusbar",
        "Toggle the context/model status bar",
        "Configuration",
        cli_only=True,
        aliases=("sb",),
    ),
    CommandDef(
        "verbose",
        "Cycle tool progress display: off -> new -> all -> verbose",
        "Configuration",
        cli_only=True,
        gateway_config_gate="display.tool_progress_command",
    ),
    CommandDef(
        "footer",
        "Toggle gateway runtime-metadata footer on final replies",
        "Configuration",
        args_hint="[on|off|status]",
        subcommands=("on", "off", "status"),
    ),
    CommandDef("yolo", "Toggle YOLO mode (skip all dangerous command approvals)", "Configuration"),
    CommandDef(
        "reasoning",
        "Manage reasoning effort and display",
        "Configuration",
        args_hint="[level|show|hide]",
        subcommands=(
            "none",
            "minimal",
            "low",
            "medium",
            "high",
            "xhigh",
            "show",
            "hide",
            "on",
            "off",
        ),
    ),
    CommandDef(
        "fast",
        "Toggle fast mode — OpenAI Priority Processing / Anthropic Fast Mode (Normal/Fast)",
        "Configuration",
        args_hint="[normal|fast|status]",
        subcommands=("normal", "fast", "status", "on", "off"),
    ),
    CommandDef(
        "skin",
        "Show or change the display skin/theme",
        "Configuration",
        cli_only=True,
        args_hint="[name]",
    ),
    CommandDef(
        "indicator",
        "Pick the TUI busy-indicator style",
        "Configuration",
        cli_only=True,
        args_hint="[kaomoji|emoji|unicode|ascii]",
        subcommands=("kaomoji", "emoji", "unicode", "ascii"),
    ),
    CommandDef(
        "voice",
        "Toggle voice mode",
        "Configuration",
        args_hint="[on|off|tts|status]",
        subcommands=("on", "off", "tts", "status"),
    ),
    CommandDef(
        "busy",
        "Control what Enter does while Prometheus is working",
        "Configuration",
        cli_only=True,
        args_hint="[queue|steer|interrupt|status]",
        subcommands=("queue", "steer", "interrupt", "status"),
    ),
    # Tools & Skills
    CommandDef(
        "tools",
        "Manage tools: /tools [list|disable|enable] [name...]",
        "Tools & Skills",
        args_hint="[list|disable|enable] [name...]",
        cli_only=True,
    ),
    CommandDef("toolsets", "List available toolsets", "Tools & Skills", cli_only=True),
    CommandDef(
        "skills",
        "Search, install, inspect, or manage skills",
        "Tools & Skills",
        cli_only=True,
        subcommands=("search", "browse", "inspect", "install"),
    ),
    CommandDef(
        "cron",
        "Manage scheduled tasks",
        "Tools & Skills",
        cli_only=True,
        args_hint="[subcommand]",
        subcommands=("list", "add", "create", "edit", "pause", "resume", "run", "remove"),
    ),
    CommandDef(
        "curator",
        "Background skill maintenance (status, run, pin, archive)",
        "Tools & Skills",
        args_hint="[subcommand]",
        subcommands=("status", "run", "pause", "resume", "pin", "unpin", "restore"),
    ),
    CommandDef(
        "reload", "Reload .env variables into the running session", "Tools & Skills", cli_only=True
    ),
    CommandDef(
        "reload-mcp", "Reload MCP servers from config", "Tools & Skills", aliases=("reload_mcp",)
    ),
    CommandDef(
        "reload-skills",
        "Re-scan ~/.prometheus/skills/ for newly installed or removed skills",
        "Tools & Skills",
        aliases=("reload_skills",),
    ),
    CommandDef(
        "browser",
        "Connect browser tools to your live Chrome via CDP",
        "Tools & Skills",
        cli_only=True,
        args_hint="[connect|disconnect|status]",
        subcommands=("connect", "disconnect", "status"),
    ),
    CommandDef(
        "plugins", "List installed plugins and their status", "Tools & Skills", cli_only=True
    ),
    # Info
    CommandDef(
        "commands",
        "Browse all commands and skills (paginated)",
        "Info",
        gateway_only=True,
        args_hint="[page]",
    ),
    CommandDef("help", "Show available commands", "Info"),
    CommandDef(
        "restart",
        "Gracefully restart the gateway after draining active runs",
        "Session",
        gateway_only=True,
    ),
    CommandDef("usage", "Show token usage and rate limits for the current session", "Info"),
    CommandDef("insights", "Show usage insights and analytics", "Info", args_hint="[days]"),
    CommandDef(
        "platforms",
        "Show gateway/messaging platform status",
        "Info",
        cli_only=True,
        aliases=("gateway",),
    ),
    CommandDef(
        "copy",
        "Copy the last assistant response to clipboard",
        "Info",
        cli_only=True,
        args_hint="[number]",
    ),
    CommandDef("paste", "Attach clipboard image from your clipboard", "Info", cli_only=True),
    CommandDef(
        "image",
        "Attach a local image file for your next prompt",
        "Info",
        cli_only=True,
        args_hint="<path>",
    ),
    CommandDef(
        "update", "Update Prometheus Agent to the latest version", "Info", gateway_only=True
    ),
    CommandDef("debug", "Upload debug report (system info + logs) and get shareable links", "Info"),
    # Exit
    CommandDef("quit", "Exit the CLI", "Exit", cli_only=True, aliases=("exit",)),
]


def _build_command_lookup() -> Dict[str, CommandDef]:
    """Map every name and alias to its CommandDef."""
    lookup: Dict[str, CommandDef] = {}
    for cmd in COMMAND_REGISTRY:
        lookup[cmd.name] = cmd
        for alias in cmd.aliases:
            lookup[alias] = cmd
    return lookup


_COMMAND_LOOKUP: Dict[str, CommandDef] = _build_command_lookup()


def resolve_command(name: str) -> CommandDef | None:
    """Resolve a command name or alias to its CommandDef."""
    return _COMMAND_LOOKUP.get(name.lower().lstrip("/"))


def _build_description(cmd: CommandDef) -> str:
    """Build a CLI-facing description string including usage hint."""
    if cmd.args_hint:
        return f"{cmd.description} (usage: /{cmd.name} {cmd.args_hint})"
    return cmd.description


COMMANDS: Dict[str, str] = {}
for _cmd in COMMAND_REGISTRY:
    if not _cmd.gateway_only:
        COMMANDS[f"/{_cmd.name}"] = _build_description(_cmd)
        for _alias in _cmd.aliases:
            COMMANDS[f"/{_alias}"] = f"{_cmd.description} (alias for /{_cmd.name})"

COMMANDS_BY_CATEGORY: Dict[str, Dict[str, str]] = {}
for _cmd in COMMAND_REGISTRY:
    if not _cmd.gateway_only:
        _cat = COMMANDS_BY_CATEGORY.setdefault(_cmd.category, {})
        _cat[f"/{_cmd.name}"] = COMMANDS[f"/{_cmd.name}"]
        for _alias in _cmd.aliases:
            _cat[f"/{_alias}"] = COMMANDS[f"/{_alias}"]


SUBCOMMANDS: Dict[str, List[str]] = {}
for _cmd in COMMAND_REGISTRY:
    if _cmd.subcommands:
        SUBCOMMANDS[f"/{_cmd.name}"] = list(_cmd.subcommands)

_PIPE_SUBS_RE = re.compile(r"[a-z]+(?:\|[a-z]+)+")
for _cmd in COMMAND_REGISTRY:
    key = f"/{_cmd.name}"
    if key in SUBCOMMANDS or not _cmd.args_hint:
        continue
    m = _PIPE_SUBS_RE.search(_cmd.args_hint)
    if m:
        SUBCOMMANDS[key] = m.group(0).split("|")


GATEWAY_KNOWN_COMMANDS: frozenSet[str] = frozenset(
    name
    for cmd in COMMAND_REGISTRY
    if not cmd.cli_only or cmd.gateway_config_gate
    for name in (cmd.name, *cmd.aliases)
)


def is_gateway_known_command(name: Optional[str]) -> bool:
    """Return True if ``name`` resolves to a gateway-dispatchable slash command."""
    if not name:
        return False
    if name in GATEWAY_KNOWN_COMMANDS:
        return True
    for plugin_name, _description, _args_hint in _iter_plugin_command_entries():
        if plugin_name == name:
            return True
    return False


ACTIVE_SESSION_BYPASS_COMMANDS: frozenSet[str] = frozenset(
    {
        "agents",
        "approve",
        "background",
        "commands",
        "deny",
        "help",
        "new",
        "profile",
        "queue",
        "restart",
        "status",
        "steer",
        "stop",
        "update",
    }
)


def should_bypass_active_session(command_name: Optional[str]) -> bool:
    """Return True for any resolvable slash command."""
    return resolve_command(command_name) is not None if command_name else False


def _resolve_config_gates() -> Set[str]:
    """Return canonical names of commands whose ``gateway_config_gate`` is truthy."""
    gated = [c for c in COMMAND_REGISTRY if c.gateway_config_gate]
    if not gated:
        return set()
    try:
        from prometheus.config import PrometheusConfig

        cfg = PrometheusConfig.load()
    except Exception:
        return set()
    result: Set[str] = set()
    for cmd in gated:
        val: Any = cfg
        for key in cmd.gateway_config_gate.split("."):
            if isinstance(val, dict):
                val = val.get(key)
            else:
                val = None
                break
        if val:
            result.add(cmd.name)
    return result


def _is_gateway_available(cmd: CommandDef, config_overrides: Set[str] | None = None) -> bool:
    """Check if *cmd* should appear in gateway surfaces."""
    if not cmd.cli_only:
        return True
    if cmd.gateway_config_gate:
        overrides = config_overrides if config_overrides is not None else _resolve_config_gates()
        return cmd.name in overrides
    return False


def gateway_help_lines() -> List[str]:
    """Generate gateway help text lines from the registry."""
    overrides = _resolve_config_gates()
    lines: List[str] = []
    for cmd in COMMAND_REGISTRY:
        if not _is_gateway_available(cmd, overrides):
            continue
        args = f" {cmd.args_hint}" if cmd.args_hint else ""
        alias_parts: List[str] = []
        for a in cmd.aliases:
            if a.replace("-", "_") == cmd.name.replace("-", "_") and a != cmd.name:
                continue
            alias_parts.append(f"`/{a}`")
        alias_note = f" (alias: {', '.join(alias_parts)})" if alias_parts else ""
        lines.append(f"`/{cmd.name}{args}` -- {cmd.description}{alias_note}")
    return lines


def _iter_plugin_command_entries() -> list[Tuple[str, str, str]]:
    """Yield (name, description, args_hint) tuples for all plugin slash commands."""
    try:
        from prometheus.cli.plugins import get_plugin_commands
    except Exception:
        return []
    try:
        commands = get_plugin_commands() or {}
    except Exception:
        return []
    entries: list[Tuple[str, str, str]] = []
    for name, meta in commands.items():
        if not isinstance(name, str) or not isinstance(meta, dict):
            continue
        description = str(meta.get("description") or f"Run /{name}")
        args_hint = str(meta.get("args_hint") or "").strip()
        entries.append((name, description, args_hint))
    return entries


def telegram_bot_commands() -> list[Tuple[str, str]]:
    """Return (command_name, description) pairs for Telegram setMyCommands."""
    overrides = _resolve_config_gates()
    result: list[Tuple[str, str]] = []
    for cmd in COMMAND_REGISTRY:
        if not _is_gateway_available(cmd, overrides):
            continue
        tg_name = _sanitize_telegram_name(cmd.name)
        if tg_name:
            result.append((tg_name, cmd.description))
    for name, description, _args_hint in _iter_plugin_command_entries():
        tg_name = _sanitize_telegram_name(name)
        if tg_name:
            result.append((tg_name, description))
    return result


_CMD_NAME_LIMIT = 32

_TG_NAME_LIMIT = _CMD_NAME_LIMIT

_TG_INVALID_CHARS = re.compile(r"[^a-z0-9_]")
_TG_MULTI_UNDERSCORE = re.compile(r"_{2,}")


def _sanitize_telegram_name(raw: str) -> str:
    """Convert a command/skill/plugin name to a valid Telegram command name."""
    name = raw.lower().replace("-", "_")
    name = _TG_INVALID_CHARS.sub("", name)
    name = _TG_MULTI_UNDERSCORE.sub("_", name)
    return name.strip("_")


def _clamp_command_names(
    entries: list[Tuple[str, str]],
    reserved: Set[str],
) -> list[Tuple[str, str]]:
    """Enforce 32-char command name limit with collision avoidance."""
    used: Set[str] = set(reserved)
    result: list[Tuple[str, str]] = []
    for name, desc in entries:
        if len(name) > _CMD_NAME_LIMIT:
            candidate = name[:_CMD_NAME_LIMIT]
            if candidate in used:
                prefix = name[: _CMD_NAME_LIMIT - 1]
                for digit in range(10):
                    candidate = f"{prefix}{digit}"
                    if candidate not in used:
                        break
                else:
                    continue
            name = candidate
        if name in used:
            continue
        used.add(name)
        result.append((name, desc))
    return result


_clamp_telegram_names = _clamp_command_names


def _collect_gateway_skill_entries(
    platform: str,
    max_slots: int,
    reserved_names: Set[str],
    desc_limit: int = 100,
    sanitize_name: Callable[[str], str] | None = None,
) -> Tuple[list[Tuple[str, str, str]], int]:
    """Collect plugin + skill entries for a gateway platform."""
    all_entries: list[Tuple[str, str, str]] = []

    plugin_pairs: list[Tuple[str, str]] = []
    try:
        from prometheus.cli.plugins import get_plugin_commands

        plugin_cmds = get_plugin_commands()
        for cmd_name in sorted(plugin_cmds):
            name = sanitize_name(cmd_name) if sanitize_name else cmd_name
            if not name:
                continue
            desc = plugin_cmds[cmd_name].get("description", "Plugin command")
            if len(desc) > desc_limit:
                desc = desc[: desc_limit - 3] + "..."
            plugin_pairs.append((name, desc))
    except Exception:
        pass

    plugin_pairs = _clamp_command_names(plugin_pairs, reserved_names)
    reserved_names.update(n for n, _ in plugin_pairs)
    for n, d in plugin_pairs:
        all_entries.append((n, d, ""))

    _platform_disabled: Set[str] = set()
    try:
        from prometheus.agent.skill_utils import get_disabled_skill_names

        _platform_disabled = get_disabled_skill_names(platform=platform)
    except Exception:
        pass

    skill_triples: list[Tuple[str, str, str]] = []
    try:
        from prometheus.agent.skill_commands import get_skill_commands
        from prometheus.tools.skills_tool import SKILLS_DIR

        _skills_dir = str(SKILLS_DIR.resolve())
        _hub_dir = str((SKILLS_DIR / ".hub").resolve())
        skill_cmds = get_skill_commands()
        for cmd_key in sorted(skill_cmds):
            info = skill_cmds[cmd_key]
            skill_path = info.get("skill_md_path", "")
            if not skill_path.startswith(_skills_dir):
                continue
            if skill_path.startswith(_hub_dir):
                continue
            skill_name = info.get("name", "")
            if skill_name in _platform_disabled:
                continue
            raw_name = cmd_key.lstrip("/")
            name = sanitize_name(raw_name) if sanitize_name else raw_name
            if not name:
                continue
            desc = info.get("description", "")
            if len(desc) > desc_limit:
                desc = desc[: desc_limit - 3] + "..."
            skill_triples.append((name, desc, cmd_key))
    except Exception:
        pass

    skill_pairs = [(n, d) for n, d, _ in skill_triples]
    key_by_pair = {(n, d): k for n, d, k in skill_triples}
    skill_pairs = _clamp_command_names(skill_pairs, reserved_names)

    remaining = max(0, max_slots - len(all_entries))
    hidden_count = max(0, len(skill_pairs) - remaining)
    for n, d in skill_pairs[:remaining]:
        all_entries.append((n, d, key_by_pair.get((n, d), "")))

    return all_entries[:max_slots], hidden_count


def telegram_menu_commands(max_commands: int = 100) -> Tuple[list[Tuple[str, str]], int]:
    """Return Telegram menu commands capped to the Bot API limit."""
    core_commands = list(telegram_bot_commands())
    reserved_names = {n for n, _ in core_commands}
    all_commands = list(core_commands)

    remaining_slots = max(0, max_commands - len(all_commands))
    entries, hidden_count = _collect_gateway_skill_entries(
        platform="telegram",
        max_slots=remaining_slots,
        reserved_names=reserved_names,
        desc_limit=40,
        sanitize_name=_sanitize_telegram_name,
    )
    all_commands.extend((n, d) for n, d, _k in entries)
    return all_commands[:max_commands], hidden_count


def discord_skill_commands(
    max_slots: int,
    reserved_names: Set[str],
) -> Tuple[list[Tuple[str, str, str]], int]:
    """Return skill entries for Discord slash command registration."""
    return _collect_gateway_skill_entries(
        platform="discord",
        max_slots=max_slots,
        reserved_names=set(reserved_names),
        desc_limit=100,
    )


def discord_skill_commands_by_category(
    reserved_names: Set[str],
) -> Tuple[Dict[str, list[Tuple[str, str, str]]], list[Tuple[str, str, str]], int]:
    """Return skill entries organized by category for Discord ``/skill`` subcommand groups."""
    from pathlib import Path as _P

    _platform_disabled: Set[str] = set()
    try:
        from prometheus.agent.skill_utils import get_disabled_skill_names

        _platform_disabled = get_disabled_skill_names(platform="discord")
    except Exception:
        pass

    categories: Dict[str, list[Tuple[str, str, str]]] = {}
    uncategorized: list[Tuple[str, str, str]] = []
    _names_used: Set[str] = set(reserved_names)
    hidden = 0

    try:
        from prometheus.agent.skill_commands import get_skill_commands
        from prometheus.tools.skills_tool import SKILLS_DIR

        _skills_dir = SKILLS_DIR.resolve()
        _hub_dir = (SKILLS_DIR / ".hub").resolve()
        skill_cmds = get_skill_commands()

        for cmd_key in sorted(skill_cmds):
            info = skill_cmds[cmd_key]
            skill_path = info.get("skill_md_path", "")
            if not skill_path:
                continue
            sp = _P(skill_path).resolve()
            if not str(sp).startswith(str(_skills_dir)):
                continue
            if str(sp).startswith(str(_hub_dir)):
                continue

            skill_name = info.get("name", "")
            if skill_name in _platform_disabled:
                continue

            raw_name = cmd_key.lstrip("/")
            discord_name = raw_name[:32]
            if discord_name in _names_used:
                continue
            _names_used.add(discord_name)

            desc = info.get("description", "")
            if len(desc) > 100:
                desc = desc[:97] + "..."

            try:
                rel = sp.parent.relative_to(_skills_dir)
            except ValueError:
                continue
            parts = rel.parts
            if len(parts) >= 2:
                cat = parts[0]
                categories.setdefault(cat, []).append((discord_name, desc, cmd_key))
            else:
                uncategorized.append((discord_name, desc, cmd_key))
    except Exception:
        pass

    _MAX_GROUPS = 25
    _MAX_PER_GROUP = 25

    trimmed_categories: Dict[str, list[Tuple[str, str, str]]] = {}
    group_count = 0
    for cat in sorted(categories):
        if group_count >= _MAX_GROUPS:
            hidden += len(categories[cat])
            continue
        entries = categories[cat][:_MAX_PER_GROUP]
        hidden += max(0, len(categories[cat]) - _MAX_PER_GROUP)
        trimmed_categories[cat] = entries
        group_count += 1

    remaining_slots = _MAX_GROUPS - group_count
    if len(uncategorized) > remaining_slots:
        hidden += len(uncategorized) - remaining_slots
        uncategorized = uncategorized[:remaining_slots]

    return trimmed_categories, uncategorized, hidden


_SLACK_MAX_SLASH_COMMANDS = 50
_SLACK_NAME_LIMIT = 32
_SLACK_INVALID_CHARS = re.compile(r"[^a-z0-9_\-]")


def _sanitize_slack_name(raw: str) -> str:
    """Convert a command name to a valid Slack slash command name."""
    name = raw.lower()
    name = _SLACK_INVALID_CHARS.sub("", name)
    name = name.strip("-_")
    return name[:_SLACK_NAME_LIMIT]


def slack_native_slashes() -> list[Tuple[str, str, str]]:
    """Return (slash_name, description, usage_hint) triples for Slack."""
    overrides = _resolve_config_gates()
    entries: list[Tuple[str, str, str]] = []
    seen: Set[str] = set()

    entries.append(("prometheus", "Talk to Prometheus or run a subcommand", "[subcommand] [args]"))
    seen.add("prometheus")

    def _add(name: str, desc: str, hint: str) -> None:
        slack_name = _sanitize_slack_name(name)
        if not slack_name or slack_name in seen:
            return
        if len(entries) >= _SLACK_MAX_SLASH_COMMANDS:
            return
        entries.append((slack_name, desc[:140], hint[:100]))
        seen.add(slack_name)

    for cmd in COMMAND_REGISTRY:
        if not _is_gateway_available(cmd, overrides):
            continue
        _add(cmd.name, cmd.description, cmd.args_hint or "")

    for cmd in COMMAND_REGISTRY:
        if not _is_gateway_available(cmd, overrides):
            continue
        for alias in cmd.aliases:
            _add(alias, f"Alias for /{cmd.name} — {cmd.description}", cmd.args_hint or "")

    for name, description, args_hint in _iter_plugin_command_entries():
        _add(name, description, args_hint or "")

    return entries


def slack_app_manifest(
    request_url: str = "https://prometheus-agent.local/slack/commands",
) -> Dict[str, Any]:
    """Generate a Slack app manifest with all gateway commands as slashes."""
    slashes = []
    for name, desc, usage in slack_native_slashes():
        entry = {
            "command": f"/{name}",
            "description": desc or f"Run /{name}",
            "should_escape": False,
            "url": request_url,
        }
        if usage:
            entry["usage_hint"] = usage
        slashes.append(entry)
    return {"features": {"slash_commands": slashes}}


def slack_subcommand_map() -> Dict[str, str]:
    """Return subcommand -> /command mapping for Slack /prometheus handler."""
    overrides = _resolve_config_gates()
    mapping: Dict[str, str] = {}
    for cmd in COMMAND_REGISTRY:
        if not _is_gateway_available(cmd, overrides):
            continue
        mapping[cmd.name] = f"/{cmd.name}"
        for alias in cmd.aliases:
            mapping[alias] = f"/{alias}"
    for name, _description, _args_hint in _iter_plugin_command_entries():
        if name not in mapping:
            mapping[name] = f"/{name}"
    return mapping


_LMSTUDIO_COMPLETION_CACHE: Tuple[float, List[str]] | None = None


def _lmstudio_completion_models() -> List[str]:
    """Locally-loaded LM Studio models for /model autocomplete (cached, gated)."""
    global _LMSTUDIO_COMPLETION_CACHE
    if not (os.environ.get("LM_API_KEY") or os.environ.get("LM_BASE_URL")):
        try:
            from prometheus.cli.auth import _load_auth_store

            store = _load_auth_store() or {}
            if "lmstudio" not in (store.get("providers") or {}) and "lmstudio" not in (
                store.get("credential_pool") or {}
            ):
                return []
        except Exception:
            return []
    now = time.time()
    if _LMSTUDIO_COMPLETION_CACHE and (now - _LMSTUDIO_COMPLETION_CACHE[0]) < 30.0:
        return _LMSTUDIO_COMPLETION_CACHE[1]
    try:
        from prometheus.cli.models import fetch_lmstudio_models

        models = fetch_lmstudio_models(
            api_key=os.environ.get("LM_API_KEY", ""),
            base_url=os.environ.get("LM_BASE_URL") or "http://127.0.0.1:1234/v1",
            timeout=0.8,
        )
    except Exception:
        models = []
    _LMSTUDIO_COMPLETION_CACHE = (now, models)
    return models


class SlashCommandCompleter(Completer):
    """Autocomplete for built-in slash commands, subcommands, and skill commands."""

    def __init__(
        self,
        skill_commands_provider: Callable[[], Mapping[str, Dict[str, Any]]] | None = None,
        command_filter: Callable[[str], bool] | None = None,
    ) -> None:
        self._skill_commands_provider = skill_commands_provider
        self._command_filter = command_filter
        self._file_cache: List[str] = []
        self._file_cache_time: float = 0.0
        self._file_cache_cwd: str = ""

    def _command_allowed(self, slash_command: str) -> bool:
        if self._command_filter is None:
            return True
        try:
            return bool(self._command_filter(slash_command))
        except Exception:
            return True

    def _iter_skill_commands(self) -> Mapping[str, Dict[str, Any]]:
        if self._skill_commands_provider is None:
            return {}
        try:
            return self._skill_commands_provider() or {}
        except Exception:
            return {}

    @staticmethod
    def _completion_text(cmd_name: str, word: str) -> str:
        return f"{cmd_name} " if cmd_name == word else cmd_name

    @staticmethod
    def _extract_path_word(text: str) -> str | None:
        if not text:
            return None
        i = len(text) - 1
        while i >= 0 and text[i] != " ":
            i -= 1
        word = text[i + 1 :]
        if not word:
            return None
        if word.startswith(("./", "../", "~/", "/")) or "/" in word:
            return word
        return None

    @staticmethod
    def _path_completions(word: str, limit: int = 30):
        expanded = os.path.expanduser(word)
        if expanded.endswith("/"):
            search_dir = expanded
            prefix = ""
        else:
            search_dir = os.path.dirname(expanded) or "."
            prefix = os.path.basename(expanded)

        try:
            entries = os.listdir(search_dir)
        except OSError:
            return

        count = 0
        prefix_lower = prefix.lower()
        for entry in sorted(entries):
            if prefix and not entry.lower().startswith(prefix_lower):
                continue
            if count >= limit:
                break

            full_path = os.path.join(search_dir, entry)
            is_dir = os.path.isdir(full_path)

            if word.startswith("~"):
                display_path = "~/" + os.path.relpath(full_path, os.path.expanduser("~"))
            elif os.path.isabs(word):
                display_path = full_path
            else:
                display_path = os.path.relpath(full_path)

            if is_dir:
                display_path += "/"

            suffix = "/" if is_dir else ""
            meta = "dir" if is_dir else _file_size_label(full_path)

            yield Completion(
                display_path,
                start_position=-len(word),
                display=entry + suffix,
                display_meta=meta,
            )
            count += 1

    @staticmethod
    def _extract_context_word(text: str) -> str | None:
        if not text:
            return None
        i = len(text) - 1
        while i >= 0 and text[i] != " ":
            i -= 1
        word = text[i + 1 :]
        if not word.startswith("@"):
            return None
        return word

    def _context_completions(self, word: str, limit: int = 30):
        """Yield Claude Code-style @ context completions."""
        lowered = word.lower()

        _STATIC_REFS = (
            ("@diff", "Git working tree diff"),
            ("@staged", "Git staged diff"),
            ("@file:", "Attach a file"),
            ("@folder:", "Attach a folder"),
            ("@git:", "Git log with diffs (e.g. @git:5)"),
            ("@url:", "Fetch web content"),
        )
        for candidate, meta in _STATIC_REFS:
            if candidate.lower().startswith(lowered) and candidate.lower() != lowered:
                yield Completion(
                    candidate,
                    start_position=-len(word),
                    display=candidate,
                    display_meta=meta,
                )

        for prefix in ("@file:", "@folder:"):
            bare = prefix[:-1]

            if word == bare or word.startswith(prefix):
                want_dir = prefix == "@folder:"
                path_part = "" if word == bare else word[len(prefix) :]
                expanded = os.path.expanduser(path_part)

                if not expanded or expanded == ".":
                    search_dir, match_prefix = ".", ""
                elif expanded.endswith("/"):
                    search_dir, match_prefix = expanded, ""
                else:
                    search_dir = os.path.dirname(expanded) or "."
                    match_prefix = os.path.basename(expanded)

                try:
                    entries = os.listdir(search_dir)
                except OSError:
                    return

                count = 0
                prefix_lower = match_prefix.lower()
                for entry in sorted(entries):
                    if match_prefix and not entry.lower().startswith(prefix_lower):
                        continue
                    full_path = os.path.join(search_dir, entry)
                    is_dir = os.path.isdir(full_path)
                    if want_dir != is_dir:
                        continue
                    if count >= limit:
                        break
                    display_path = os.path.relpath(full_path)
                    suffix = "/" if is_dir else ""
                    meta = "dir" if is_dir else _file_size_label(full_path)
                    completion = f"{prefix}{display_path}{suffix}"
                    yield Completion(
                        completion,
                        start_position=-len(word),
                        display=entry + suffix,
                        display_meta=meta,
                    )
                return

        query = word[1:]
        yield from self._fuzzy_file_completions(word, query, limit)

    def _get_project_files(self) -> List[str]:
        """Return cached list of project files (refreshed every 5s)."""
        cwd = os.getcwd()
        now = time.monotonic()
        if self._file_cache and self._file_cache_cwd == cwd and now - self._file_cache_time < 5.0:
            return self._file_cache

        files: List[str] = []
        for cmd in [
            ["rg", "--files", "--sortr=modified", cwd],
            ["rg", "--files", cwd],
            ["fd", "--type", "f", "--base-directory", cwd],
        ]:
            tool = cmd[0]
            if not shutil.which(tool):
                continue
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=2,
                    cwd=cwd,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    raw = proc.stdout.strip().split("\n")
                    for p in raw[:5000]:
                        rel = os.path.relpath(p, cwd) if os.path.isabs(p) else p
                        files.append(rel)
                    break
            except (subprocess.TimeoutExpired, OSError):
                continue

        self._file_cache = files
        self._file_cache_time = now
        self._file_cache_cwd = cwd
        return files

    @staticmethod
    def _score_path(filepath: str, query: str) -> int:
        """Score a file path against a fuzzy query. Higher = better match."""
        if not query:
            return 1

        filename = os.path.basename(filepath)
        lower_file = filename.lower()
        lower_path = filepath.lower()
        lower_q = query.lower()

        if lower_file == lower_q:
            return 100
        if lower_file.startswith(lower_q):
            return 80
        if lower_q in lower_file:
            return 60
        if lower_q in lower_path:
            return 40
        qi = 0
        for c in lower_file:
            if qi < len(lower_q) and c == lower_q[qi]:
                qi += 1
        if qi == len(lower_q):
            boundary_hits = 0
            qi = 0
            prev = "_"
            for c in lower_file:
                if qi < len(lower_q) and c == lower_q[qi]:
                    if prev in "_-./":
                        boundary_hits += 1
                    qi += 1
                prev = c
            if boundary_hits >= len(lower_q) * 0.5:
                return 35
            return 25
        return 0

    def _fuzzy_file_completions(self, word: str, query: str, limit: int = 20):
        """Yield fuzzy file completions for bare @query."""
        files = self._get_project_files()

        if not query:
            for fp in files[:limit]:
                is_dir = fp.endswith("/")
                filename = os.path.basename(fp)
                kind = "folder" if is_dir else "file"
                meta = "dir" if is_dir else _file_size_label(os.path.join(os.getcwd(), fp))
                yield Completion(
                    f"@{kind}:{fp}",
                    start_position=-len(word),
                    display=filename,
                    display_meta=meta,
                )
            return

        scored = []
        for fp in files:
            s = self._score_path(fp, query)
            if s > 0:
                scored.append((s, fp))
        scored.sort(key=lambda x: (-x[0], x[1]))

        for _, fp in scored[:limit]:
            is_dir = fp.endswith("/")
            filename = os.path.basename(fp)
            kind = "folder" if is_dir else "file"
            meta = "dir" if is_dir else _file_size_label(os.path.join(os.getcwd(), fp))
            yield Completion(
                f"@{kind}:{fp}",
                start_position=-len(word),
                display=filename,
                display_meta=f"{fp}  {meta}" if meta else fp,
            )

    @staticmethod
    def _skin_completions(sub_text: str, sub_lower: str):
        """Yield completions for /skin from available skins."""
        try:
            from prometheus.skin_engine import list_skins

            for s in list_skins():
                name = s["name"]
                if name.startswith(sub_lower) and name != sub_lower:
                    yield Completion(
                        name,
                        start_position=-len(sub_text),
                        display=name,
                        display_meta=s.get("description", "") or s.get("source", ""),
                    )
        except Exception:
            pass

    @staticmethod
    def _personality_completions(sub_text: str, sub_lower: str):
        """Yield completions for /personality from configured personalities."""
        try:
            personalities = load_config().get("agent", {}).get("personalities", {})
            if "none".startswith(sub_lower) and sub_lower != "none":
                yield Completion(
                    "none",
                    start_position=-len(sub_text),
                    display="none",
                    display_meta="clear personality overlay",
                )
            for name, prompt in personalities.items():
                if name.startswith(sub_lower) and name != sub_lower:
                    if isinstance(prompt, dict):
                        meta = prompt.get("description") or prompt.get("system_prompt", "")[:50]
                    else:
                        meta = str(prompt)[:50]
                    yield Completion(
                        name,
                        start_position=-len(sub_text),
                        display=name,
                        display_meta=meta,
                    )
        except Exception:
            pass

    def _model_completions(self, sub_text: str, sub_lower: str):
        """Yield completions for /model from config aliases + built-in aliases."""
        seen = set()
        try:
            from prometheus.cli.model_switch import (
                DIRECT_ALIASES,
                MODEL_ALIASES,
                _ensure_direct_aliases,
            )

            _ensure_direct_aliases()
            for name, da in DIRECT_ALIASES.items():
                if name.startswith(sub_lower) and name != sub_lower:
                    seen.add(name)
                    yield Completion(
                        name,
                        start_position=-len(sub_text),
                        display=name,
                        display_meta=f"{da.model} ({da.provider})",
                    )
            for name in sorted(MODEL_ALIASES.keys()):
                if name in seen:
                    continue
                if name.startswith(sub_lower) and name != sub_lower:
                    identity = MODEL_ALIASES[name]
                    yield Completion(
                        name,
                        start_position=-len(sub_text),
                        display=name,
                        display_meta=f"{identity.vendor}/{identity.family}",
                    )
        except Exception:
            pass
        for name in _lmstudio_completion_models():
            if name in seen:
                continue
            if name.startswith(sub_lower) and name != sub_lower:
                yield Completion(
                    name,
                    start_position=-len(sub_text),
                    display=name,
                    display_meta="LM Studio",
                )

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/"):
            ctx_word = self._extract_context_word(text)
            if ctx_word is not None:
                yield from self._context_completions(ctx_word)
                return
            path_word = self._extract_path_word(text)
            if path_word is not None:
                yield from self._path_completions(path_word)
            return

        parts = text.split(maxsplit=1)
        base_cmd = parts[0].lower()
        if len(parts) > 1 or (len(parts) == 1 and text.endswith(" ")):
            sub_text = parts[1] if len(parts) > 1 else ""
            sub_lower = sub_text.lower()

            if " " not in sub_text:
                if base_cmd == "/model":
                    yield from self._model_completions(sub_text, sub_lower)
                    return
                if base_cmd == "/skin":
                    yield from self._skin_completions(sub_text, sub_lower)
                    return
                if base_cmd == "/personality":
                    yield from self._personality_completions(sub_text, sub_lower)
                    return

            if " " not in sub_text and base_cmd in SUBCOMMANDS and self._command_allowed(base_cmd):
                for sub in SUBCOMMANDS[base_cmd]:
                    if sub.startswith(sub_lower) and sub != sub_lower:
                        yield Completion(
                            sub,
                            start_position=-len(sub_text),
                            display=sub,
                        )
            return

        word = text[1:]

        for cmd, desc in COMMANDS.items():
            if not self._command_allowed(cmd):
                continue
            cmd_name = cmd[1:]
            if cmd_name.startswith(word):
                yield Completion(
                    self._completion_text(cmd_name, word),
                    start_position=-len(word),
                    display=cmd,
                    display_meta=desc,
                )

        for cmd, info in self._iter_skill_commands().items():
            cmd_name = cmd[1:]
            if cmd_name.startswith(word):
                description = str(info.get("description", "Skill command"))
                short_desc = description[:50] + ("..." if len(description) > 50 else "")
                yield Completion(
                    self._completion_text(cmd_name, word),
                    start_position=-len(word),
                    display=cmd,
                    display_meta=f"⚡ {short_desc}",
                )

        try:
            from prometheus.cli.plugins import get_plugin_commands

            for cmd_name, cmd_info in get_plugin_commands().items():
                if cmd_name.startswith(word):
                    desc = str(cmd_info.get("description", "Plugin command"))
                    short_desc = desc[:50] + ("..." if len(desc) > 50 else "")
                    yield Completion(
                        self._completion_text(cmd_name, word),
                        start_position=-len(word),
                        display=f"/{cmd_name}",
                        display_meta=f"🔌 {short_desc}",
                    )
        except Exception:
            pass


class SlashCommandAutoSuggest(AutoSuggest):
    """Inline ghost-text suggestions for slash commands and their subcommands."""

    def __init__(
        self,
        history_suggest: AutoSuggest | None = None,
        completer: SlashCommandCompleter | None = None,
    ) -> None:
        self._history = history_suggest
        self._completer = completer

    def get_suggestion(self, buffer, document):
        text = document.text_before_cursor

        if not text.startswith("/"):
            if self._history:
                return self._history.get_suggestion(buffer, document)
            return None

        parts = text.split(maxsplit=1)
        base_cmd = parts[0].lower()

        if len(parts) == 1 and not text.endswith(" "):
            word = text[1:].lower()
            for cmd in COMMANDS:
                if self._completer is not None and not self._completer._command_allowed(cmd):
                    continue
                cmd_name = cmd[1:]
                if cmd_name.startswith(word) and cmd_name != word:
                    return Suggestion(cmd_name[len(word) :])
            return None

        sub_text = parts[1] if len(parts) > 1 else ""
        sub_lower = sub_text.lower()

        if self._completer is not None and not self._completer._command_allowed(base_cmd):
            return None
        if base_cmd in SUBCOMMANDS and SUBCOMMANDS[base_cmd] and " " not in sub_text:
            for sub in SUBCOMMANDS[base_cmd]:
                if sub.startswith(sub_lower) and sub != sub_lower:
                    return Suggestion(sub[len(sub_text) :])

        if self._history:
            return self._history.get_suggestion(buffer, document)
        return None


def _file_size_label(path: str) -> str:
    """Return a compact human-readable file size, or '' on error."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return ""
    if size < 1024:
        return f"{size}B"
    if size < 1024 * 1024:
        return f"{size / 1024:.0f}K"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f}M"
    return f"{size / (1024 * 1024 * 1024):.1f}G"
