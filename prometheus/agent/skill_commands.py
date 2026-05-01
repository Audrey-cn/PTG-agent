"""Shared slash command helpers for skills."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from prometheus.agent.skill_preprocessing import (
    expand_inline_shell as _expand_inline_shell,
)
from prometheus.agent.skill_preprocessing import (
    load_skills_config as _load_skills_config,
)
from prometheus.agent.skill_preprocessing import (
    substitute_template_vars as _substitute_template_vars,
)

logger = logging.getLogger(__name__)

_skill_commands: dict[str, dict[str, Any]] = {}
_SKILL_INVALID_CHARS = re.compile(r"[^a-z0-9-]")
_SKILL_MULTI_HYPHEN = re.compile(r"-{2,}")


def _load_skill_payload(
    skill_identifier: str, task_id: str | None = None
) -> Tuple[dict[str, Any], Path | None, str] | None:
    """Load a skill by name/path and return (loaded_payload, skill_dir, display_name)."""
    raw_identifier = (skill_identifier or "").strip()
    if not raw_identifier:
        return None

    try:
        identifier_path = Path(raw_identifier).expanduser()
        loaded_skill = {
            "success": True,
            "name": raw_identifier,
            "path": str(identifier_path),
            "content": f"Skill: {raw_identifier}",
        }

    except Exception:
        return None

    if not loaded_skill.get("success"):
        return None

    skill_name = str(loaded_skill.get("name") or raw_identifier)
    skill_path = str(loaded_skill.get("path") or "")
    skill_dir = Path(skill_path).parent if skill_path else None

    return loaded_skill, skill_dir, skill_name


def _inject_skill_config(loaded_skill: dict[str, Any], parts: List[str]) -> None:
    """Resolve and inject skill-declared config values into the message parts."""
    try:
        config_vars = loaded_skill.get("config_vars", {})
        if not config_vars:
            return

        lines = ["", "[Skill config:"]
        for key, value in config_vars.items():
            display_val = str(value) if value else "(not set)"
            lines.append(f"  {key} = {display_val}")
        lines.append("]")
        parts.extend(lines)
    except Exception:
        pass


def _build_skill_message(
    loaded_skill: dict[str, Any],
    skill_dir: Path | None,
    activation_note: str,
    user_instruction: str = "",
    runtime_note: str = "",
    session_id: str | None = None,
) -> str:
    """Format a loaded skill into a user/system message payload."""

    content = str(loaded_skill.get("content") or "")

    skills_cfg = _load_skills_config()
    if skills_cfg.get("template_vars", True):
        content = _substitute_template_vars(content, skill_dir, session_id)
    if skills_cfg.get("inline_shell", False):
        timeout = int(skills_cfg.get("inline_shell_timeout", 10) or 10)
        content = _expand_inline_shell(content, skill_dir, timeout)

    parts = [activation_note, "", content.strip()]

    if skill_dir:
        parts.append("")
        parts.append(f"[Skill directory: {skill_dir}]")
        parts.append("Resolve any relative paths in this skill against that directory.")

    _inject_skill_config(loaded_skill, parts)

    if loaded_skill.get("setup_skipped"):
        parts.extend(
            [
                "",
                "[Skill setup note: Required environment setup was skipped.]",
            ]
        )
    elif loaded_skill.get("setup_needed") and loaded_skill.get("setup_note"):
        parts.extend(
            [
                "",
                f"[Skill setup note: {loaded_skill['setup_note']}]",
            ]
        )

    supporting = []
    linked_files = loaded_skill.get("linked_files") or {}
    for entries in linked_files.values():
        if isinstance(entries, list):
            supporting.extend(entries)

    if not supporting and skill_dir:
        for subdir in ("references", "templates", "scripts", "assets"):
            subdir_path = skill_dir / subdir
            if subdir_path.exists():
                for f in sorted(subdir_path.rglob("*")):
                    if f.is_file() and not f.is_symlink():
                        rel = str(f.relative_to(skill_dir))
                        supporting.append(rel)

    if supporting and skill_dir:
        parts.append("")
        parts.append("[This skill has supporting files:]")
        for sf in supporting:
            parts.append(f"- {sf}  ->  {skill_dir / sf}")

    return "\n".join(parts)


def get_skill_command(name: str) -> dict[str, Any] | None:
    """Get a skill command by name."""
    return _skill_commands.get(name)


def register_skill_command(name: str, config: dict[str, Any]) -> None:
    """Register a skill command."""
    _skill_commands[name] = config


def list_skill_commands() -> List[str]:
    """List all registered skill commands."""
    return list(_skill_commands.keys())


def sanitize_skill_name(name: str) -> str:
    """Convert a skill name into a clean hyphen-separated slug."""
    slug = name.lower()
    slug = _SKILL_INVALID_CHARS.sub("", slug)
    slug = _SKILL_MULTI_HYPHEN.sub("-", slug)
    return slug.strip("-")
