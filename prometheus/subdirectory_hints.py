from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


HINT_FILENAMES: List[str] = ["AGENTS.md", "CLAUDE.md", ".cursorrules", "PROMETHEUS.md", "RULES.md", ".claude"]


@dataclass
class HintFile:
    path: str
    filename: str
    content: Optional[str] = None
    loaded: bool = False


@dataclass
class DirectoryRecord:
    path: str
    visited_at: str = ""
    hint_files: List[HintFile] = field(default_factory=list)


class SubdirectoryHintTracker:
    def __init__(self, auto_load: bool = True, max_file_size: int = 100000) -> None:
        self._tracked_paths: Dict[str, DirectoryRecord] = {}
        self._auto_load = auto_load
        self._max_file_size = max_file_size
        self._loaded_hints: Set[str] = set()

    def track_path(self, path: str) -> bool:
        abs_path = os.path.abspath(path)
        if abs_path in self._tracked_paths:
            return False
        from datetime import datetime
        record = DirectoryRecord(
            path=abs_path,
            visited_at=datetime.now().isoformat(),
        )
        hints = self.scan_directory(abs_path)
        if hints:
            record.hint_files = [
                HintFile(path=p, filename=os.path.basename(p))
                for p in hints.get(abs_path, {}).get("files", [])
            ]
        self._tracked_paths[abs_path] = record
        if self._auto_load:
            self._auto_load_hints(record)
        return True

    def get_hints_for_path(self, path: str) -> List[str]:
        abs_path = os.path.abspath(path)
        hints: List[str] = []
        if abs_path in self._tracked_paths:
            record = self._tracked_paths[abs_path]
            for hint_file in record.hint_files:
                if hint_file.content:
                    hints.append(hint_file.content)
        parent = os.path.dirname(abs_path)
        while parent and parent != os.path.dirname(parent):
            if parent in self._tracked_paths:
                record = self._tracked_paths[parent]
                for hint_file in record.hint_files:
                    if hint_file.content and hint_file.path not in self._loaded_hints:
                        hints.append(hint_file.content)
                        self._loaded_hints.add(hint_file.path)
            parent = os.path.dirname(parent)
        return hints

    def scan_directory(self, dir_path: str) -> Dict[str, Dict[str, List[str]]]:
        abs_path = os.path.abspath(dir_path)
        result: Dict[str, Dict[str, List[str]]] = {}
        if not os.path.isdir(abs_path):
            return result
        found_files: List[str] = []
        for hint_name in HINT_FILENAMES:
            hint_path = os.path.join(abs_path, hint_name)
            if os.path.isfile(hint_path):
                found_files.append(hint_path)
        result[abs_path] = {"files": found_files}
        return result

    def _auto_load_hints(self, record: DirectoryRecord) -> None:
        for hint_file in record.hint_files:
            if hint_file.path in self._loaded_hints:
                continue
            try:
                file_size = os.path.getsize(hint_file.path)
                if file_size > self._max_file_size:
                    continue
                with open(hint_file.path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                hint_file.content = content
                hint_file.loaded = True
                self._loaded_hints.add(hint_file.path)
            except Exception:
                pass

    def get_all_tracked_paths(self) -> List[str]:
        return list(self._tracked_paths.keys())

    def get_record(self, path: str) -> Optional[DirectoryRecord]:
        abs_path = os.path.abspath(path)
        return self._tracked_paths.get(abs_path)

    def clear(self) -> None:
        self._tracked_paths.clear()
        self._loaded_hints.clear()

    def is_tracked(self, path: str) -> bool:
        abs_path = os.path.abspath(path)
        return abs_path in self._tracked_paths

    def get_loaded_hint_count(self) -> int:
        return len(self._loaded_hints)
