from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


_skill_commands: Dict[str, Callable] = {}
_skill_aliases: Dict[str, str] = {}


def register_skill_command(skill_name: str, handler: Callable, aliases: Optional[List[str]] = None) -> bool:
    normalized = skill_name.lower().lstrip("/")
    if normalized in _skill_commands:
        return False
    _skill_commands[normalized] = handler
    if aliases:
        for alias in aliases:
            alias_normalized = alias.lower().lstrip("/")
            _skill_aliases[alias_normalized] = normalized
    return True


def dispatch_skill_command(command: str, args: Any) -> Optional[Any]:
    normalized = command.lower().lstrip("/")
    if normalized in _skill_aliases:
        normalized = _skill_aliases[normalized]
    handler = _skill_commands.get(normalized)
    if handler is None:
        return None
    return handler(args)


def list_skill_commands() -> List[str]:
    return list(_skill_commands.keys())


def get_skill_command_aliases() -> Dict[str, str]:
    return dict(_skill_aliases)


def unregister_skill_command(skill_name: str) -> bool:
    normalized = skill_name.lower().lstrip("/")
    if normalized not in _skill_commands:
        return False
    del _skill_commands[normalized]
    aliases_to_remove = [alias for alias, target in _skill_aliases.items() if target == normalized]
    for alias in aliases_to_remove:
        del _skill_aliases[alias]
    return True


def is_skill_command(command: str) -> bool:
    normalized = command.lower().lstrip("/")
    return normalized in _skill_commands or normalized in _skill_aliases


def get_skill_command_handler(command: str) -> Optional[Callable]:
    normalized = command.lower().lstrip("/")
    if normalized in _skill_aliases:
        normalized = _skill_aliases[normalized]
    return _skill_commands.get(normalized)


def clear_all_skill_commands() -> None:
    _skill_commands.clear()
    _skill_aliases.clear()


def integrate_with_slash_commands() -> None:
    try:
        from prometheus.slash_commands import SlashCommandDispatcher, COMMAND_REGISTRY, CommandDef
    except ImportError:
        return
    for skill_name in _skill_commands:
        existing = any(cmd.name == skill_name for cmd in COMMAND_REGISTRY)
        if not existing:
            cmd_def = CommandDef(
                name=skill_name,
                description=f"Skill: {skill_name}",
                category="Skills",
            )
            COMMAND_REGISTRY.append(cmd_def)
