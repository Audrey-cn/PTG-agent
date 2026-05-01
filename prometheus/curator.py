from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class SkillStatus:
    name: str
    running: bool = False
    pinned: bool = False
    archived: bool = False
    last_run: str | None = None
    run_count: int = 0
    error: str | None = None


@dataclass
class CuratorState:
    skills: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_updated: str = ""


class Curator:
    def __init__(self) -> None:
        self._state: CuratorState = CuratorState()
        self._thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()
        self._state_path = Path.home() / ".prometheus" / "curator_state.json"
        self._load_state()

    def _load_state(self) -> None:
        if self._state_path.exists():
            try:
                with open(self._state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._state.skills = data.get("skills", {})
                self._state.last_updated = data.get("last_updated", "")
            except Exception:
                pass

    def _save_state(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state.last_updated = datetime.now().isoformat()
        try:
            with open(self._state_path, "w", encoding="utf-8") as f:
                json.dump({
                    "skills": self._state.skills,
                    "last_updated": self._state.last_updated,
                }, f, indent=2)
        except Exception:
            pass

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return False
            self._running = True
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self._running:
                return False
            self._running = False
            if self._thread:
                self._thread.join(timeout=5)
                self._thread = None
            return True

    def _run_loop(self) -> None:
        while self._running:
            time.sleep(60)

    def run_skill(self, skill_name: str) -> dict[str, Any]:
        with self._lock:
            if skill_name not in self._state.skills:
                self._state.skills[skill_name] = {
                    "name": skill_name,
                    "running": False,
                    "pinned": False,
                    "archived": False,
                    "last_run": None,
                    "run_count": 0,
                    "error": None,
                }
            skill = self._state.skills[skill_name]
            skill["running"] = True
            skill["last_run"] = datetime.now().isoformat()
            skill["run_count"] = skill.get("run_count", 0) + 1
            self._save_state()
            return {"status": "started", "skill": skill_name}

    def pin_skill(self, skill_name: str) -> bool:
        with self._lock:
            if skill_name not in self._state.skills:
                self._state.skills[skill_name] = {
                    "name": skill_name,
                    "running": False,
                    "pinned": False,
                    "archived": False,
                    "last_run": None,
                    "run_count": 0,
                    "error": None,
                }
            self._state.skills[skill_name]["pinned"] = True
            self._save_state()
            return True

    def archive_skill(self, skill_name: str) -> bool:
        with self._lock:
            if skill_name not in self._state.skills:
                return False
            self._state.skills[skill_name]["archived"] = True
            self._save_state()
            return True

    def get_skill_status(self, skill_name: str) -> dict[str, Any]:
        with self._lock:
            return self._state.skills.get(skill_name, {
                "name": skill_name,
                "running": False,
                "pinned": False,
                "archived": False,
                "last_run": None,
                "run_count": 0,
                "error": None,
            })

    def list_background_skills(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                skill for skill in self._state.skills.values()
                if skill.get("running") or skill.get("pinned")
            ]

    def is_running(self) -> bool:
        return self._running


_curator: Curator | None = None


def get_curator() -> Curator:
    global _curator
    if _curator is None:
        _curator = Curator()
    return _curator
