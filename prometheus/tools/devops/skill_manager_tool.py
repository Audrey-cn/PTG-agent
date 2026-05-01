#!/usr/bin/env python3
"""Skill Manager Tool -- Agent-Managed Skill Creation & Editing."""

import json
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from prometheus.cli.config import cfg_get
from prometheus.constants_core import display_prometheus_home, get_prometheus_home
from prometheus.utils import atomic_replace

logger = logging.getLogger(__name__)

try:
    from prometheus.tools.skills_guard import format_scan_report, scan_skill, should_allow_install

    _GUARD_AVAILABLE = True
except ImportError:
    _GUARD_AVAILABLE = False


def _guard_agent_created_enabled() -> bool:
    """Read skills.guard_agent_created from config (default False).

    Off by default because the agent can already execute the same code
    paths via terminal() with no gate, so the scan adds friction without
    meaningful security.  Users who want belt-and-suspenders can turn it
    on via `prometheus config set skills.guard_agent_created true`.
    """
    try:
        from prometheus.cli.config import load_config

        cfg = load_config()
        return bool(cfg_get(cfg, "skills", "guard_agent_created", default=False))
    except Exception:
        return False


def _security_scan_skill(skill_dir: Path) -> str | None:
    """Scan a skill directory after write. Returns error string if blocked, else None.

    No-op when skills.guard_agent_created is disabled (the default).
    """
    if not _GUARD_AVAILABLE:
        return None
    if not _guard_agent_created_enabled():
        return None
    try:
        result = scan_skill(skill_dir, source="agent-created")
        allowed, reason = should_allow_install(result)
        if allowed is False:
            report = format_scan_report(result)
            return f"Security scan blocked this skill ({reason}):\n{report}"
        if allowed is None:
            report = format_scan_report(result)
            logger.warning("Agent-created skill blocked (dangerous findings): %s", reason)
            return f"Security scan blocked this skill ({reason}):\n{report}"
    except Exception as e:
        logger.warning("Security scan failed for %s: %s", skill_dir, e, exc_info=True)
    return None


import yaml

PROMETHEUS_HOME = get_prometheus_home()
SKILLS_DIR = PROMETHEUS_HOME / "skills"

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024


def _containing_skills_root(skill_path: Path) -> Path:
    """Return the skills root directory (local or external_dirs entry) that
    contains ``skill_path``.  Falls back to the local ``SKILLS_DIR`` if no
    match is found (defensive — callers should have located the skill via
    ``_find_skill`` first).
    """
    from prometheus.agent.skill_utils import get_all_skills_dirs

    try:
        resolved = skill_path.resolve()
    except OSError:
        resolved = skill_path

    for root in get_all_skills_dirs():
        try:
            resolved.relative_to(root.resolve())
            return root
        except (ValueError, OSError):
            continue
    return SKILLS_DIR


def _pinned_guard(name: str) -> str | None:
    """Return a refusal message if *name* is pinned, else None.

    Pinned skills are off-limits to the agent's skill_manage tool.  The only
    way to modify one is for the user to unpin it via
    ``prometheus curator unpin <name>`` (or edit it directly by hand).  This
    mirrors the curator's own pinned-skip behavior but extends the guard
    to tool-driven writes as well, giving users a hard fence against
    accidental agent edits.

    Best-effort: if the sidecar is unreadable we let the write through
    rather than block on a broken telemetry file.
    """
    try:
        from prometheus.tools import skill_usage

        rec = skill_usage.get_record(name)
        if rec.get("pinned"):
            return (
                f"Skill '{name}' is pinned and cannot be modified by "
                f"skill_manage. Ask the user to run "
                f"`prometheus curator unpin {name}` if they want the change."
            )
    except Exception:
        logger.debug("pinned-guard lookup failed for %s", name, exc_info=True)
    return None


MAX_SKILL_CONTENT_CHARS = 100_000
MAX_SKILL_FILE_BYTES = 1_048_576

VALID_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

ALLOWED_SUBDIRS = {"references", "templates", "scripts", "assets"}


def _validate_name(name: str) -> str | None:
    """Validate a skill name. Returns error message or None if valid."""
    if not name:
        return "Skill name is required."
    if len(name) > MAX_NAME_LENGTH:
        return f"Skill name exceeds {MAX_NAME_LENGTH} characters."
    if not VALID_NAME_RE.match(name):
        return (
            f"Invalid skill name '{name}'. Use lowercase letters, numbers, "
            f"hyphens, dots, and underscores. Must start with a letter or digit."
        )
    return None


def _validate_category(category: str | None) -> str | None:
    """Validate an optional category name used as a single directory segment."""
    if category is None:
        return None
    if not isinstance(category, str):
        return "Category must be a string."

    category = category.strip()
    if not category:
        return None
    if "/" in category or "\\" in category:
        return (
            f"Invalid category '{category}'. Use lowercase letters, numbers, "
            "hyphens, dots, and underscores. Categories must be a single directory name."
        )
    if len(category) > MAX_NAME_LENGTH:
        return f"Category exceeds {MAX_NAME_LENGTH} characters."
    if not VALID_NAME_RE.match(category):
        return (
            f"Invalid category '{category}'. Use lowercase letters, numbers, "
            "hyphens, dots, and underscores. Categories must be a single directory name."
        )
    return None


def _validate_frontmatter(content: str) -> str | None:
    """
    Validate that SKILL.md content has proper frontmatter with required fields.
    Returns error message or None if valid.
    """
    if not content.strip():
        return "Content cannot be empty."

    if not content.startswith("---"):
        return "SKILL.md must start with YAML frontmatter (---). See existing skills for format."

    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return "SKILL.md frontmatter is not closed. Ensure you have a closing '---' line."

    yaml_content = content[3 : end_match.start() + 3]

    try:
        parsed = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        return f"YAML frontmatter parse error: {e}"

    if not isinstance(parsed, dict):
        return "Frontmatter must be a YAML mapping (key: value pairs)."

    if "name" not in parsed:
        return "Frontmatter must include 'name' field."
    if "description" not in parsed:
        return "Frontmatter must include 'description' field."
    if len(str(parsed["description"])) > MAX_DESCRIPTION_LENGTH:
        return f"Description exceeds {MAX_DESCRIPTION_LENGTH} characters."

    body = content[end_match.end() + 3 :].strip()
    if not body:
        return "SKILL.md must have content after the frontmatter (instructions, procedures, etc.)."

    return None


def _validate_content_size(content: str, label: str = "SKILL.md") -> str | None:
    """Check that content doesn't exceed the character limit for agent writes.

    Returns an error message or None if within bounds.
    """
    if len(content) > MAX_SKILL_CONTENT_CHARS:
        return (
            f"{label} content is {len(content):,} characters "
            f"(limit: {MAX_SKILL_CONTENT_CHARS:,}). "
            f"Consider splitting into a smaller SKILL.md with supporting files "
            f"in references/ or templates/."
        )
    return None


def _resolve_skill_dir(name: str, category: str = None) -> Path:
    """Build the directory path for a new skill, optionally under a category."""
    if category:
        return SKILLS_DIR / category / name
    return SKILLS_DIR / name


def _find_skill(name: str) -> dict[str, Any] | None:
    """
    Find a skill by name across all skill directories.

    Searches the local skills dir (~/.prometheus/skills/) first, then any
    external dirs configured via skills.external_dirs.  Returns
    {"path": Path} or None.
    """
    from prometheus.agent.skill_utils import get_all_skills_dirs

    for skills_dir in get_all_skills_dirs():
        if not skills_dir.exists():
            continue
        for skill_md in skills_dir.rglob("SKILL.md"):
            if skill_md.parent.name == name:
                return {"path": skill_md.parent}
    return None


def _validate_file_path(file_path: str) -> str | None:
    """
    Validate a file path for write_file/remove_file.
    Must be under an allowed subdirectory and not escape the skill dir.
    """
    from prometheus.tools.path_security import has_traversal_component

    if not file_path:
        return "file_path is required."

    normalized = Path(file_path)

    if has_traversal_component(file_path):
        return "Path traversal ('..') is not allowed."

    if not normalized.parts or normalized.parts[0] not in ALLOWED_SUBDIRS:
        allowed = ", ".join(sorted(ALLOWED_SUBDIRS))
        return f"File must be under one of: {allowed}. Got: '{file_path}'"

    if len(normalized.parts) < 2:
        return (
            f"Provide a file path, not just a directory. Example: '{normalized.parts[0]}/myfile.md'"
        )

    return None


def _resolve_skill_target(skill_dir: Path, file_path: str) -> tuple[Path | None, str | None]:
    """Resolve a supporting-file path and ensure it stays within the skill directory."""
    from prometheus.tools.path_security import validate_within_dir

    target = skill_dir / file_path
    error = validate_within_dir(target, skill_dir)
    if error:
        return None, error
    return target, None


def _atomic_write_text(file_path: Path, content: str, encoding: str = "utf-8") -> None:
    """
    Atomically write text content to a file.

    Uses a temporary file in the same directory and os.replace() to ensure
    the target file is never left in a partially-written state if the process
    crashes or is interrupted.

    Args:
        file_path: Target file path
        content: Content to write
        encoding: Text encoding (default: utf-8)
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        dir=str(file_path.parent),
        prefix=f".{file_path.name}.tmp.",
        suffix="",
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
        atomic_replace(temp_path, file_path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            logger.error(
                "Failed to remove temporary file %s during atomic write", temp_path, exc_info=True
            )
        raise


def _create_skill(name: str, content: str, category: str = None) -> dict[str, Any]:
    """Create a new user skill with SKILL.md content."""
    err = _validate_name(name)
    if err:
        return {"success": False, "error": err}

    err = _validate_category(category)
    if err:
        return {"success": False, "error": err}

    err = _validate_frontmatter(content)
    if err:
        return {"success": False, "error": err}

    err = _validate_content_size(content)
    if err:
        return {"success": False, "error": err}

    existing = _find_skill(name)
    if existing:
        return {
            "success": False,
            "error": f"A skill named '{name}' already exists at {existing['path']}.",
        }

    skill_dir = _resolve_skill_dir(name, category)
    skill_dir.mkdir(parents=True, exist_ok=True)

    skill_md = skill_dir / "SKILL.md"
    _atomic_write_text(skill_md, content)

    scan_error = _security_scan_skill(skill_dir)
    if scan_error:
        shutil.rmtree(skill_dir, ignore_errors=True)
        return {"success": False, "error": scan_error}

    result = {
        "success": True,
        "message": f"Skill '{name}' created.",
        "path": str(skill_dir.relative_to(SKILLS_DIR)),
        "skill_md": str(skill_md),
    }
    if category:
        result["category"] = category
    result["hint"] = (
        "To add reference files, templates, or scripts, use "
        f"skill_manage(action='write_file', name='{name}', file_path='references/example.md', file_content='...')"
    )
    return result


def _edit_skill(name: str, content: str) -> dict[str, Any]:
    """Replace the SKILL.md of any existing skill (full rewrite)."""
    err = _validate_frontmatter(content)
    if err:
        return {"success": False, "error": err}

    err = _validate_content_size(content)
    if err:
        return {"success": False, "error": err}

    existing = _find_skill(name)
    if not existing:
        return {
            "success": False,
            "error": f"Skill '{name}' not found. Use skills_list() to see available skills.",
        }

    pinned_err = _pinned_guard(name)
    if pinned_err:
        return {"success": False, "error": pinned_err}

    skill_md = existing["path"] / "SKILL.md"
    original_content = skill_md.read_text(encoding="utf-8") if skill_md.exists() else None
    _atomic_write_text(skill_md, content)

    scan_error = _security_scan_skill(existing["path"])
    if scan_error:
        if original_content is not None:
            _atomic_write_text(skill_md, original_content)
        return {"success": False, "error": scan_error}

    return {
        "success": True,
        "message": f"Skill '{name}' updated.",
        "path": str(existing["path"]),
    }


def _patch_skill(
    name: str,
    old_string: str,
    new_string: str,
    file_path: str = None,
    replace_all: bool = False,
) -> dict[str, Any]:
    """Targeted find-and-replace within a skill file.

    Defaults to SKILL.md. Use file_path to patch a supporting file instead.
    Requires a unique match unless replace_all is True.
    """
    if not old_string:
        return {"success": False, "error": "old_string is required for 'patch'."}
    if new_string is None:
        return {
            "success": False,
            "error": "new_string is required for 'patch'. Use an empty string to delete matched text.",
        }

    existing = _find_skill(name)
    if not existing:
        return {"success": False, "error": f"Skill '{name}' not found."}

    pinned_err = _pinned_guard(name)
    if pinned_err:
        return {"success": False, "error": pinned_err}

    skill_dir = existing["path"]

    if file_path:
        err = _validate_file_path(file_path)
        if err:
            return {"success": False, "error": err}
        target, err = _resolve_skill_target(skill_dir, file_path)
        if err:
            return {"success": False, "error": err}
    else:
        target = skill_dir / "SKILL.md"

    if not target.exists():
        return {"success": False, "error": f"File not found: {target.relative_to(skill_dir)}"}

    content = target.read_text(encoding="utf-8")

    from prometheus.tools.fuzzy_match import fuzzy_find_and_replace

    new_content, match_count, _strategy, match_error = fuzzy_find_and_replace(
        content, old_string, new_string, replace_all
    )
    if match_error:
        preview = content[:500] + ("..." if len(content) > 500 else "")
        err_msg = match_error
        try:
            from prometheus.tools.fuzzy_match import format_no_match_hint

            err_msg += format_no_match_hint(match_error, match_count, old_string, content)
        except Exception:
            pass
        return {
            "success": False,
            "error": err_msg,
            "file_preview": preview,
        }

    target_label = file_path if file_path else "SKILL.md"
    err = _validate_content_size(new_content, label=target_label)
    if err:
        return {"success": False, "error": err}

    if not file_path:
        err = _validate_frontmatter(new_content)
        if err:
            return {
                "success": False,
                "error": f"Patch would break SKILL.md structure: {err}",
            }

    original_content = content
    _atomic_write_text(target, new_content)

    scan_error = _security_scan_skill(skill_dir)
    if scan_error:
        _atomic_write_text(target, original_content)
        return {"success": False, "error": scan_error}

    return {
        "success": True,
        "message": f"Patched {file_path if file_path else 'SKILL.md'} in skill '{name}' ({match_count} replacement{'s' if match_count > 1 else ''}).",
    }


def _delete_skill(name: str) -> dict[str, Any]:
    """Delete a skill."""
    existing = _find_skill(name)
    if not existing:
        return {"success": False, "error": f"Skill '{name}' not found."}

    pinned_err = _pinned_guard(name)
    if pinned_err:
        return {"success": False, "error": pinned_err}

    skill_dir = existing["path"]
    skills_root = _containing_skills_root(skill_dir)
    shutil.rmtree(skill_dir)

    parent = skill_dir.parent
    if parent != skills_root and parent.exists() and not any(parent.iterdir()):
        parent.rmdir()

    return {
        "success": True,
        "message": f"Skill '{name}' deleted.",
    }


def _write_file(name: str, file_path: str, file_content: str) -> dict[str, Any]:
    """Add or overwrite a supporting file within any skill directory."""
    err = _validate_file_path(file_path)
    if err:
        return {"success": False, "error": err}

    if not file_content and file_content != "":
        return {"success": False, "error": "file_content is required."}

    content_bytes = len(file_content.encode("utf-8"))
    if content_bytes > MAX_SKILL_FILE_BYTES:
        return {
            "success": False,
            "error": (
                f"File content is {content_bytes:,} bytes "
                f"(limit: {MAX_SKILL_FILE_BYTES:,} bytes / 1 MiB). "
                f"Consider splitting into smaller files."
            ),
        }
    err = _validate_content_size(file_content, label=file_path)
    if err:
        return {"success": False, "error": err}

    existing = _find_skill(name)
    if not existing:
        return {
            "success": False,
            "error": f"Skill '{name}' not found. Create it first with action='create'.",
        }

    pinned_err = _pinned_guard(name)
    if pinned_err:
        return {"success": False, "error": pinned_err}

    target, err = _resolve_skill_target(existing["path"], file_path)
    if err:
        return {"success": False, "error": err}
    target.parent.mkdir(parents=True, exist_ok=True)
    original_content = target.read_text(encoding="utf-8") if target.exists() else None
    _atomic_write_text(target, file_content)

    scan_error = _security_scan_skill(existing["path"])
    if scan_error:
        if original_content is not None:
            _atomic_write_text(target, original_content)
        else:
            target.unlink(missing_ok=True)
        return {"success": False, "error": scan_error}

    return {
        "success": True,
        "message": f"File '{file_path}' written to skill '{name}'.",
        "path": str(target),
    }


def _remove_file(name: str, file_path: str) -> dict[str, Any]:
    """Remove a supporting file from any skill directory."""
    err = _validate_file_path(file_path)
    if err:
        return {"success": False, "error": err}

    existing = _find_skill(name)
    if not existing:
        return {"success": False, "error": f"Skill '{name}' not found."}

    pinned_err = _pinned_guard(name)
    if pinned_err:
        return {"success": False, "error": pinned_err}

    skill_dir = existing["path"]

    target, err = _resolve_skill_target(skill_dir, file_path)
    if err:
        return {"success": False, "error": err}
    if not target.exists():
        available = []
        for subdir in ALLOWED_SUBDIRS:
            d = skill_dir / subdir
            if d.exists():
                for f in d.rglob("*"):
                    if f.is_file():
                        available.append(str(f.relative_to(skill_dir)))
        return {
            "success": False,
            "error": f"File '{file_path}' not found in skill '{name}'.",
            "available_files": available if available else None,
        }

    target.unlink()

    parent = target.parent
    if parent != skill_dir and parent.exists() and not any(parent.iterdir()):
        parent.rmdir()

    return {
        "success": True,
        "message": f"File '{file_path}' removed from skill '{name}'.",
    }


def skill_manage(
    action: str,
    name: str,
    content: str = None,
    category: str = None,
    file_path: str = None,
    file_content: str = None,
    old_string: str = None,
    new_string: str = None,
    replace_all: bool = False,
) -> str:
    """
    Manage user-created skills. Dispatches to the appropriate action handler.

    Returns JSON string with results.
    """
    if action == "create":
        if not content:
            return tool_error(
                "content is required for 'create'. Provide the full SKILL.md text (frontmatter + body).",
                success=False,
            )
        result = _create_skill(name, content, category)

    elif action == "edit":
        if not content:
            return tool_error(
                "content is required for 'edit'. Provide the full updated SKILL.md text.",
                success=False,
            )
        result = _edit_skill(name, content)

    elif action == "patch":
        if not old_string:
            return tool_error(
                "old_string is required for 'patch'. Provide the text to find.", success=False
            )
        if new_string is None:
            return tool_error(
                "new_string is required for 'patch'. Use empty string to delete matched text.",
                success=False,
            )
        result = _patch_skill(name, old_string, new_string, file_path, replace_all)

    elif action == "delete":
        result = _delete_skill(name)

    elif action == "write_file":
        if not file_path:
            return tool_error(
                "file_path is required for 'write_file'. Example: 'references/api-guide.md'",
                success=False,
            )
        if file_content is None:
            return tool_error("file_content is required for 'write_file'.", success=False)
        result = _write_file(name, file_path, file_content)

    elif action == "remove_file":
        if not file_path:
            return tool_error("file_path is required for 'remove_file'.", success=False)
        result = _remove_file(name, file_path)

    else:
        result = {
            "success": False,
            "error": f"Unknown action '{action}'. Use: create, edit, patch, delete, write_file, remove_file",
        }

    if result.get("success"):
        try:
            from prometheus.agent.prompt_builder import clear_skills_system_prompt_cache

            clear_skills_system_prompt_cache(clear_snapshot=True)
        except Exception:
            pass
        try:
            from prometheus.tools.skill_usage import bump_patch, forget

            if action in ("patch", "edit", "write_file", "remove_file"):
                bump_patch(name)
            elif action == "delete":
                forget(name)
        except Exception:
            pass

    return json.dumps(result, ensure_ascii=False)


SKILL_MANAGE_SCHEMA = {
    "name": "skill_manage",
    "description": (
        "Manage skills (create, update, delete). Skills are your procedural "
        "memory — reusable approaches for recurring task types. "
        f"New skills go to {display_prometheus_home()}/skills/; existing skills can be modified wherever they live.\n\n"
        "Actions: create (full SKILL.md + optional category), "
        "patch (old_string/new_string — preferred for fixes), "
        "edit (full SKILL.md rewrite — major overhauls only), "
        "delete, write_file, remove_file.\n\n"
        "Create when: complex task succeeded (5+ calls), errors overcome, "
        "user-corrected approach worked, non-trivial workflow discovered, "
        "or user asks you to remember a procedure.\n"
        "Update when: instructions stale/wrong, OS-specific failures, "
        "missing steps or pitfalls found during use. "
        "If you used a skill and hit issues not covered by it, patch it immediately.\n\n"
        "After difficult/iterative tasks, offer to save as a skill. "
        "Skip for simple one-offs. Confirm with user before creating/deleting.\n\n"
        "Good skills: trigger conditions, numbered steps with exact commands, "
        "pitfalls section, verification steps. Use skill_view() to see format examples.\n\n"
        "Pinned skills are off-limits — all write actions refuse with a message "
        "pointing the user to `prometheus curator unpin <name>`. Don't try to route "
        "around this by renaming or recreating."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "patch", "edit", "delete", "write_file", "remove_file"],
                "description": "The action to perform.",
            },
            "name": {
                "type": "string",
                "description": (
                    "Skill name (lowercase, hyphens/underscores, max 64 chars). "
                    "Must match an existing skill for patch/edit/delete/write_file/remove_file."
                ),
            },
            "content": {
                "type": "string",
                "description": (
                    "Full SKILL.md content (YAML frontmatter + markdown body). "
                    "Required for 'create' and 'edit'. For 'edit', read the skill "
                    "first with skill_view() and provide the complete updated text."
                ),
            },
            "old_string": {
                "type": "string",
                "description": (
                    "Text to find in the file (required for 'patch'). Must be unique "
                    "unless replace_all=true. Include enough surrounding context to "
                    "ensure uniqueness."
                ),
            },
            "new_string": {
                "type": "string",
                "description": (
                    "Replacement text (required for 'patch'). Can be empty string "
                    "to delete the matched text."
                ),
            },
            "replace_all": {
                "type": "boolean",
                "description": "For 'patch': replace all occurrences instead of requiring a unique match (default: false).",
            },
            "category": {
                "type": "string",
                "description": (
                    "Optional category/domain for organizing the skill (e.g., 'devops', "
                    "'data-science', 'mlops'). Creates a subdirectory grouping. "
                    "Only used with 'create'."
                ),
            },
            "file_path": {
                "type": "string",
                "description": (
                    "Path to a supporting file within the skill directory. "
                    "For 'write_file'/'remove_file': required, must be under references/, "
                    "templates/, scripts/, or assets/. "
                    "For 'patch': optional, defaults to SKILL.md if omitted."
                ),
            },
            "file_content": {
                "type": "string",
                "description": "Content for the file. Required for 'write_file'.",
            },
        },
        "required": ["action", "name"],
    },
}


from prometheus.tools.registry import registry, tool_error

registry.register(
    name="skill_manage",
    toolset="skills",
    schema=SKILL_MANAGE_SCHEMA,
    handler=lambda args, **kw: skill_manage(
        action=args.get("action", ""),
        name=args.get("name", ""),
        content=args.get("content"),
        category=args.get("category"),
        file_path=args.get("file_path"),
        file_content=args.get("file_content"),
        old_string=args.get("old_string"),
        new_string=args.get("new_string"),
        replace_all=args.get("replace_all", False),
    ),
    emoji="📝",
)
