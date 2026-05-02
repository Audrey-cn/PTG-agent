from __future__ import annotations

#!/usr/bin/env python3
"""Skills Tool Module."""

import json
import logging
import re
from enum import StrEnum
from pathlib import Path
from typing import Any

from prometheus.constants_core import display_prometheus_home, get_prometheus_home
from prometheus.tools.security.path_security import has_traversal_component, validate_within_dir
from prometheus.tools.security.registry import registry, tool_error

logger = logging.getLogger(__name__)

SKILLS_DIR = get_prometheus_home() / "skills"

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024

_PLATFORM_MAP = {
    "macos": "darwin",
    "linux": "linux",
    "windows": "win32",
}
_ENV_VAR_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_EXCLUDED_SKILL_DIRS = frozenset((".git", ".github", ".hub", ".archive"))


def load_env() -> dict[str, str]:
    """Load profile-scoped environment variables from PROMETHEUS_HOME/.env."""
    env_path = get_prometheus_home() / ".env"
    env_vars: dict[str, str] = {}
    if not env_path.exists():
        return env_vars

    with env_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env_vars[key.strip()] = value.strip().strip("\"'")
    return env_vars


class SkillReadinessStatus(StrEnum):
    AVAILABLE = "available"
    SETUP_NEEDED = "setup_needed"
    UNSUPPORTED = "unsupported"


_INJECTION_PATTERNS: list = [
    "ignore previous instructions",
    "ignore all previous",
    "you are now",
    "disregard your",
    "forget your instructions",
    "new instructions:",
    "system prompt:",
    "<system>",
    "]]>",
]


def skill_matches_platform(frontmatter: dict[str, Any]) -> bool:
    """Check if a skill is compatible with the current OS platform."""
    platforms = frontmatter.get("platforms")
    if not platforms:
        return True
    current = sys.platform
    for p in platforms:
        mapped = _PLATFORM_MAP.get(p, p)
        if current.startswith(mapped) or current == mapped:
            return True
    return False


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}, content
    match = re.search(r"\n---\s*\n", content[3:])
    if not match:
        return {}, content
    frontmatter_str = content[3 : match.start() + 3]
    body = content[match.end() + 3 :]
    try:
        import yaml

        fm = yaml.safe_load(frontmatter_str)
        if not isinstance(fm, dict):
            return {}, body
        return fm, body
    except Exception:
        return {}, body


def _get_category_from_path(skill_path: Path) -> str | None:
    """Extract category from skill path based on directory structure."""
    dirs_to_check = [SKILLS_DIR]
    for skills_dir in dirs_to_check:
        try:
            rel_path = skill_path.relative_to(skills_dir)
            parts = rel_path.parts
            if len(parts) >= 3:
                return parts[0]
        except ValueError:
            continue
    return None


def _parse_tags(tags_value) -> list[str]:
    """Parse tags from frontmatter value."""
    if not tags_value:
        return []
    if isinstance(tags_value, list):
        return [str(t).strip() for t in tags_value if t]
    tags_value = str(tags_value).strip()
    if tags_value.startswith("[") and tags_value.endswith("]"):
        tags_value = tags_value[1:-1]
    return [t.strip().strip("\"'") for t in tags_value.split(",") if t.strip()]


def _get_disabled_skill_names() -> set[str]:
    """Load disabled skill names from config."""
    try:
        from prometheus.tools.config import get_config

        config = get_config()
        return set(config.get("skills.disabled", []))
    except Exception:
        return set()


def _is_skill_disabled(name: str) -> bool:
    """Check if a skill is disabled in config."""
    try:
        from prometheus.tools.config import get_config

        config = get_config()
        return name in config.get("skills.disabled", [])
    except Exception:
        return False


def _find_all_skills(*, skip_disabled: bool = False) -> list[dict[str, Any]]:
    """Recursively find all skills in ~/.prometheus/skills/ and external dirs."""
    skills = []
    seen_names: set = set()

    disabled = set() if skip_disabled else _get_disabled_skill_names()

    if not SKILLS_DIR.exists():
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    for skill_md in SKILLS_DIR.rglob("SKILL.md"):
        if any(part in _EXCLUDED_SKILL_DIRS for part in skill_md.parts):
            continue

        skill_dir = skill_md.parent

        try:
            content = skill_md.read_text(encoding="utf-8")[:4000]
            frontmatter, body = _parse_frontmatter(content)

            if not skill_matches_platform(frontmatter):
                continue

            name = frontmatter.get("name", skill_dir.name)[:MAX_NAME_LENGTH]
            if name in seen_names:
                continue
            if name in disabled:
                continue

            description = frontmatter.get("description", "")
            if not description:
                for line in body.strip().split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        description = line
                        break

            if len(description) > MAX_DESCRIPTION_LENGTH:
                description = description[: MAX_DESCRIPTION_LENGTH - 3] + "..."

            category = _get_category_from_path(skill_md)

            seen_names.add(name)
            skills.append(
                {
                    "name": name,
                    "description": description,
                    "category": category,
                }
            )

        except (UnicodeDecodeError, PermissionError) as e:
            logger.debug("Failed to read skill file %s: %s", skill_md, e)
            continue
        except Exception as e:
            logger.debug("Skipping skill at %s: failed to parse: %s", skill_md, e, exc_info=True)
            continue

    return skills


def _sort_skills(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep every skill listing path ordered the same way."""
    return sorted(skills, key=lambda s: (s.get("category") or "", s["name"]))


def _load_category_description(category_dir: Path) -> str | None:
    """Load category description from DESCRIPTION.md if it exists."""
    desc_file = category_dir / "DESCRIPTION.md"
    if not desc_file.exists():
        return None

    try:
        content = desc_file.read_text(encoding="utf-8")
        frontmatter, body = _parse_frontmatter(content)

        description = frontmatter.get("description", "")
        if not description:
            for line in body.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    description = line
                    break

        if len(description) > MAX_DESCRIPTION_LENGTH:
            description = description[: MAX_DESCRIPTION_LENGTH - 3] + "..."

        return description if description else None
    except Exception as e:
        logger.debug("Failed to read category description %s: %s", desc_file, e)
        return None


def check_skills_requirements() -> bool:
    """Skills are always available -- the directory is created on first use if needed."""
    return True


def skills_list(category: str = None, task_id: str = None) -> str:
    """List all available skills (progressive disclosure tier 1 - minimal metadata)."""
    try:
        if not SKILLS_DIR.exists():
            SKILLS_DIR.mkdir(parents=True, exist_ok=True)
            return json.dumps(
                {
                    "success": True,
                    "skills": [],
                    "categories": [],
                    "message": f"No skills found. Skills directory created at {display_prometheus_home()}/skills/",
                },
                ensure_ascii=False,
            )

        all_skills = _find_all_skills()

        if not all_skills:
            return json.dumps(
                {
                    "success": True,
                    "skills": [],
                    "categories": [],
                    "message": "No skills found in skills/ directory.",
                },
                ensure_ascii=False,
            )

        if category:
            all_skills = [s for s in all_skills if s.get("category") == category]

        all_skills = _sort_skills(all_skills)

        categories = sorted(set(s.get("category") for s in all_skills if s.get("category")))

        return json.dumps(
            {
                "success": True,
                "skills": all_skills,
                "categories": categories,
                "count": len(all_skills),
                "hint": "Use skill_view(name) to see full content, tags, and linked files",
            },
            ensure_ascii=False,
        )

    except Exception as e:
        return tool_error(str(e), success=False)


def skill_view(
    name: str,
    file_path: str = None,
    task_id: str = None,
    preprocess: bool = True,
) -> str:
    """View the content of a skill or a specific file within a skill directory."""
    try:
        skill_dir = None
        skill_md = None

        if SKILLS_DIR.exists():
            direct_path = SKILLS_DIR / name
            if direct_path.is_dir() and (direct_path / "SKILL.md").exists():
                skill_dir = direct_path
                skill_md = direct_path / "SKILL.md"
            elif direct_path.with_suffix(".md").exists():
                skill_md = direct_path.with_suffix(".md")

        if not skill_md:
            for found_skill_md in SKILLS_DIR.rglob("SKILL.md"):
                if found_skill_md.parent.name == name:
                    skill_dir = found_skill_md.parent
                    skill_md = found_skill_md
                    break

        if not skill_md or not skill_md.exists():
            available = [s["name"] for s in _sort_skills(_find_all_skills())[:20]]
            return json.dumps(
                {
                    "success": False,
                    "error": f"Skill '{name}' not found.",
                    "available_skills": available,
                    "hint": "Use skills_list to see all available skills",
                },
                ensure_ascii=False,
            )

        try:
            content = skill_md.read_text(encoding="utf-8")
        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Failed to read skill '{name}': {e}",
                },
                ensure_ascii=False,
            )

        _outside_skills_dir = True
        _trusted_dirs = [SKILLS_DIR.resolve()]
        for _td in _trusted_dirs:
            try:
                skill_md.resolve().relative_to(_td)
                _outside_skills_dir = False
                break
            except ValueError:
                continue

        _content_lower = content.lower()
        _injection_detected = any(p in _content_lower for p in _INJECTION_PATTERNS)

        if _outside_skills_dir or _injection_detected:
            _warnings = []
            if _outside_skills_dir:
                _warnings.append(
                    f"skill file is outside the trusted skills directory (~/.prometheus/skills/): {skill_md}"
                )
            if _injection_detected:
                _warnings.append(
                    "skill content contains patterns that may indicate prompt injection"
                )
            logging.getLogger(__name__).warning(
                "Skill security warning for '%s': %s", name, "; ".join(_warnings)
            )

        parsed_frontmatter: dict[str, Any] = {}
        try:
            parsed_frontmatter, _ = _parse_frontmatter(content)
        except Exception:
            parsed_frontmatter = {}

        if not skill_matches_platform(parsed_frontmatter):
            return json.dumps(
                {
                    "success": False,
                    "error": f"Skill '{name}' is not supported on this platform.",
                    "readiness_status": SkillReadinessStatus.UNSUPPORTED.value,
                },
                ensure_ascii=False,
            )

        resolved_name = parsed_frontmatter.get("name", skill_md.parent.name)
        if _is_skill_disabled(resolved_name):
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        f"Skill '{resolved_name}' is disabled. "
                        "Enable it or inspect the files directly on disk."
                    ),
                },
                ensure_ascii=False,
            )

        if file_path and skill_dir:
            if has_traversal_component(file_path):
                return json.dumps(
                    {
                        "success": False,
                        "error": "Path traversal ('..') is not allowed.",
                        "hint": "Use a relative path within the skill directory",
                    },
                    ensure_ascii=False,
                )

            target_file = skill_dir / file_path

            traversal_error = validate_within_dir(target_file, skill_dir)
            if traversal_error:
                return json.dumps(
                    {
                        "success": False,
                        "error": traversal_error,
                        "hint": "Use a relative path within the skill directory",
                    },
                    ensure_ascii=False,
                )
            if not target_file.exists():
                available_files = {
                    "references": [],
                    "templates": [],
                    "assets": [],
                    "scripts": [],
                    "other": [],
                }

                for f in skill_dir.rglob("*"):
                    if f.is_file() and f.name != "SKILL.md":
                        rel = str(f.relative_to(skill_dir))
                        if rel.startswith("references/"):
                            available_files["references"].append(rel)
                        elif rel.startswith("templates/"):
                            available_files["templates"].append(rel)
                        elif rel.startswith("assets/"):
                            available_files["assets"].append(rel)
                        elif rel.startswith("scripts/"):
                            available_files["scripts"].append(rel)
                        elif f.suffix in [
                            ".md",
                            ".py",
                            ".yaml",
                            ".yml",
                            ".json",
                            ".tex",
                            ".sh",
                        ]:
                            available_files["other"].append(rel)

                available_files = {k: v for k, v in available_files.items() if v}

                return json.dumps(
                    {
                        "success": False,
                        "error": f"File '{file_path}' not found in skill '{name}'.",
                        "available_files": available_files,
                        "hint": "Use one of the available file paths listed above",
                    },
                    ensure_ascii=False,
                )

            try:
                content = target_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return json.dumps(
                    {
                        "success": True,
                        "name": name,
                        "file": file_path,
                        "content": f"[Binary file: {target_file.name}, size: {target_file.stat().st_size} bytes]",
                        "is_binary": True,
                    },
                    ensure_ascii=False,
                )

            return json.dumps(
                {
                    "success": True,
                    "name": name,
                    "file": file_path,
                    "content": content,
                    "file_type": target_file.suffix,
                },
                ensure_ascii=False,
            )

        frontmatter = parsed_frontmatter

        reference_files = []
        template_files = []
        asset_files = []
        script_files = []

        if skill_dir:
            references_dir = skill_dir / "references"
            if references_dir.exists():
                reference_files = [
                    str(f.relative_to(skill_dir)) for f in references_dir.glob("*.md")
                ]

            templates_dir = skill_dir / "templates"
            if templates_dir.exists():
                for ext in [
                    "*.md",
                    "*.py",
                    "*.yaml",
                    "*.yml",
                    "*.json",
                    "*.tex",
                    "*.sh",
                ]:
                    template_files.extend(
                        [str(f.relative_to(skill_dir)) for f in templates_dir.rglob(ext)]
                    )

            assets_dir = skill_dir / "assets"
            if assets_dir.exists():
                for f in assets_dir.rglob("*"):
                    if f.is_file():
                        asset_files.append(str(f.relative_to(skill_dir)))

            scripts_dir = skill_dir / "scripts"
            if scripts_dir.exists():
                for ext in ["*.py", "*.sh", "*.bash", "*.js", "*.ts", "*.rb"]:
                    script_files.extend(
                        [str(f.relative_to(skill_dir)) for f in scripts_dir.glob(ext)]
                    )

        prometheus_meta = {}
        metadata = frontmatter.get("metadata")
        if isinstance(metadata, dict):
            prometheus_meta = metadata.get("prometheus", {}) or {}

        tags = _parse_tags(prometheus_meta.get("tags") or frontmatter.get("tags", ""))
        related_skills = _parse_tags(
            prometheus_meta.get("related_skills") or frontmatter.get("related_skills", "")
        )

        linked_files = {}
        if reference_files:
            linked_files["references"] = reference_files
        if template_files:
            linked_files["templates"] = template_files
        if asset_files:
            linked_files["assets"] = asset_files
        if script_files:
            linked_files["scripts"] = script_files

        try:
            rel_path = str(skill_md.relative_to(SKILLS_DIR))
        except ValueError:
            rel_path = skill_md.name
        skill_name = frontmatter.get("name", skill_md.stem if not skill_dir else skill_dir.name)

        rendered_content = content
        if preprocess:
            try:
                from prometheus.skill_preprocessing import preprocess_skill

                rendered_content = preprocess_skill(
                    content,
                    str(skill_dir) if skill_dir else "",
                    task_id or "",
                )
            except Exception:
                logger.debug("Could not preprocess skill content for %s", skill_name, exc_info=True)

        result = {
            "success": True,
            "name": skill_name,
            "description": frontmatter.get("description", ""),
            "tags": tags,
            "related_skills": related_skills,
            "content": rendered_content,
            "path": rel_path,
            "skill_dir": str(skill_dir) if skill_dir else None,
            "linked_files": linked_files if linked_files else None,
            "usage_hint": "To view linked files, call skill_view(name, file_path) where file_path is e.g. 'references/api.md' or 'assets/config.yaml'"
            if linked_files
            else None,
            "readiness_status": SkillReadinessStatus.AVAILABLE.value,
        }

        if frontmatter.get("compatibility"):
            result["compatibility"] = frontmatter["compatibility"]
        if isinstance(metadata, dict):
            result["metadata"] = metadata

        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        return tool_error(str(e), success=False)


import sys

SKILLS_LIST_SCHEMA = {
    "name": "skills_list",
    "description": "List available skills (name + description). Use skill_view(name) to load full content.",
    "parameters": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "Optional category filter to narrow results",
            }
        },
        "required": [],
    },
}

SKILL_VIEW_SCHEMA = {
    "name": "skill_view",
    "description": "Skills allow for loading information about specific tasks and workflows, as well as scripts and templates. Load a skill's full content or access its linked files (references, templates, scripts). First call returns SKILL.md content plus a 'linked_files' dict showing available references/templates/scripts. To access those, call again with file_path parameter.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The skill name (use skills_list to see available skills).",
            },
            "file_path": {
                "type": "string",
                "description": "OPTIONAL: Path to a linked file within the skill (e.g., 'references/api.md', 'templates/config.yaml', 'scripts/validate.py'). Omit to get the main SKILL.md content.",
            },
        },
        "required": ["name"],
    },
}

registry.register(
    name="skills_list",
    toolset="skills",
    schema=SKILLS_LIST_SCHEMA,
    handler=lambda args, **kw: skills_list(
        category=args.get("category"), task_id=kw.get("task_id")
    ),
    check_fn=check_skills_requirements,
    emoji="📚",
)

registry.register(
    name="skill_view",
    toolset="skills",
    schema=SKILL_VIEW_SCHEMA,
    handler=lambda args, **kw: skill_view(
        name=args.get("name", ""),
        file_path=args.get("file_path"),
        task_id=kw.get("task_id"),
    ),
    check_fn=check_skills_requirements,
    emoji="📚",
)
