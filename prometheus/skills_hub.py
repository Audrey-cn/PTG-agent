from __future__ import annotations

import json
import shutil
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

from prometheus.config import get_prometheus_home

logger = logging.getLogger(__name__)

BUILTIN_CATEGORIES: list[str] = [
    "chronicler",
    "memory",
    "system",
    "creative",
    "research",
    "productivity",
]


@dataclass
class SkillEntry:
    name: str
    category: str
    description: str = ""
    version: str = "0.1.0"
    source_path: Optional[str] = None
    installed: bool = False
    metadata: dict = field(default_factory=dict)


class SkillsHub:
    def __init__(self) -> None:
        self._skills_dir = get_prometheus_home() / "skills"
        self._registry_path = self._skills_dir / "_registry.json"
        self._skills_dir.mkdir(parents=True, exist_ok=True)
        self._registry: dict[str, SkillEntry] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        if self._registry_path.exists():
            try:
                with open(self._registry_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for name, entry_data in data.items():
                    self._registry[name] = SkillEntry(**entry_data)
            except Exception as e:
                logger.warning("Failed to load skills registry: %s", e)

    def _save_registry(self) -> None:
        try:
            data = {name: asdict(entry) for name, entry in self._registry.items()}
            with open(self._registry_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Failed to save skills registry: %s", e)

    def search(self, query: str, category: Optional[str] = None) -> list[dict]:
        query_lower = query.lower()
        results: list[dict] = []
        for entry in self._registry.values():
            if category and entry.category != category:
                continue
            if query_lower in entry.name.lower() or query_lower in entry.description.lower():
                results.append(asdict(entry))
        return results

    def browse(self, category: Optional[str] = None) -> list[dict]:
        results: list[dict] = []
        for entry in self._registry.values():
            if category and entry.category != category:
                continue
            results.append(asdict(entry))
        return results

    def install(self, skill_name: str, source_path: Optional[str] = None) -> bool:
        if skill_name in self._registry and self._registry[skill_name].installed:
            logger.warning("Skill %s already installed", skill_name)
            return False

        dest = self._skills_dir / skill_name
        if dest.exists():
            logger.warning("Skill directory %s already exists", dest)
            return False

        try:
            if source_path:
                src = Path(source_path)
                if not src.exists():
                    logger.error("Source path %s does not exist", source_path)
                    return False
                if src.is_dir():
                    shutil.copytree(src, dest)
                else:
                    dest.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest / src.name)
            else:
                dest.mkdir(parents=True, exist_ok=True)

            entry = self._registry.get(skill_name, SkillEntry(name=skill_name, category="system"))
            entry.installed = True
            entry.source_path = source_path
            self._registry[skill_name] = entry
            self._save_registry()
            return True
        except Exception as e:
            logger.error("Failed to install skill %s: %s", skill_name, e)
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            return False

    def inspect(self, skill_name: str) -> Optional[dict]:
        entry = self._registry.get(skill_name)
        if not entry:
            return None
        result = asdict(entry)
        skill_dir = self._skills_dir / skill_name
        if skill_dir.exists():
            files = [str(p.relative_to(skill_dir)) for p in skill_dir.rglob("*") if p.is_file()]
            result["files"] = files
        return result

    def remove(self, skill_name: str) -> bool:
        entry = self._registry.get(skill_name)
        if not entry or not entry.installed:
            logger.warning("Skill %s not installed", skill_name)
            return False

        skill_dir = self._skills_dir / skill_name
        try:
            if skill_dir.exists():
                shutil.rmtree(skill_dir)
            del self._registry[skill_name]
            self._save_registry()
            return True
        except Exception as e:
            logger.error("Failed to remove skill %s: %s", skill_name, e)
            return False

    def list_installed(self) -> list[str]:
        return [name for name, entry in self._registry.items() if entry.installed]
