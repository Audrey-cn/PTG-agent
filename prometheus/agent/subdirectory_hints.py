"""Subdirectory hint tracking for Prometheus."""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class SubdirectoryHintTracker:
    """Track subdirectory hints across sessions.

    Maintains a record of important subdirectories encountered during
    operations to provide hints for future file operations.
    """

    def __init__(self, storage_path: str | None = None):
        if storage_path is None:
            storage_path = str(Path.home() / ".prometheus" / "subdirectory_hints.json")

        self._storage_path = storage_path
        self._hints: dict[str, list[str]] = {}
        self._project_paths: set[str] = set()
        self._load()

    def _load(self):
        """Load hints from disk."""
        storage = Path(self._storage_path)
        if not storage.exists():
            return

        try:
            with open(storage, encoding="utf-8") as f:
                data = json.load(f)
                self._hints = data.get("hints", {})
                self._project_paths = set(data.get("project_paths", []))
        except Exception as e:
            logger.error(f"Failed to load subdirectory hints: {e}")

    def _save(self):
        """Save hints to disk."""
        storage = Path(self._storage_path)
        storage.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(storage, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "hints": self._hints,
                        "project_paths": list(self._project_paths),
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            logger.error(f"Failed to save subdirectory hints: {e}")

    def add_hint(self, project_root: str, subdirectory: str, hint_type: str = "default"):
        """Add a subdirectory hint.

        Args:
            project_root: Root directory of the project
            subdirectory: Subdirectory path to track
            hint_type: Type of hint (default, src, test, config, etc.)
        """
        if project_root not in self._hints:
            self._hints[project_root] = []

        hints_list = self._hints[project_root]

        new_hint = {
            "path": subdirectory,
            "type": hint_type,
        }

        if new_hint not in hints_list:
            hints_list.insert(0, new_hint)

            if len(hints_list) > 50:
                hints_list.pop()

            self._project_paths.add(project_root)
            self._save()

    def get_hints(self, project_root: str, hint_type: str | None = None) -> list[str]:
        """Get subdirectory hints for a project.

        Args:
            project_root: Root directory of the project
            hint_type: Optional filter by hint type

        Returns:
            List of subdirectory paths
        """
        hints = self._hints.get(project_root, [])

        if hint_type:
            return [h["path"] for h in hints if h.get("type") == hint_type]

        return [h["path"] for h in hints]

    def get_hint_string(self, project_root: str, hint_type: str | None = None) -> str:
        """Get a formatted hint string for a project.

        Args:
            project_root: Root directory of the project
            hint_type: Optional filter by hint type

        Returns:
            Formatted string of hints
        """
        hints = self.get_hints(project_root, hint_type)

        if not hints:
            return ""

        hint_paths = "\n".join(f"- {path}" for path in hints[:10])
        return f"Known subdirectories:\n{hint_paths}"

    def remove_hint(self, project_root: str, subdirectory: str):
        """Remove a subdirectory hint."""
        if project_root not in self._hints:
            return

        self._hints[project_root] = [
            h for h in self._hints[project_root] if h.get("path") != subdirectory
        ]

        if not self._hints[project_root]:
            del self._hints[project_root]
            self._project_paths.discard(project_root)

        self._save()

    def clear_project(self, project_root: str):
        """Clear all hints for a project."""
        if project_root in self._hints:
            del self._hints[project_root]
            self._project_paths.discard(project_root)
            self._save()

    def get_all_projects(self) -> list[str]:
        """Get all tracked project paths."""
        return list(self._project_paths)

    def detect_project_root(self, current_path: str | None = None) -> str | None:
        """Detect the project root from a current path.

        Looks for common project markers like:
        - .git
        - package.json
        - pyproject.toml
        - requirements.txt
        - Cargo.toml
        - go.mod
        """
        if current_path is None:
            current_path = os.getcwd()

        path = Path(current_path).resolve()

        markers = {
            ".git": "git",
            "package.json": "npm",
            "pyproject.toml": "python",
            "requirements.txt": "python",
            "Cargo.toml": "rust",
            "go.mod": "go",
            "Pipfile": "python",
            "yarn.lock": "yarn",
            "pnpm-lock.yaml": "pnpm",
        }

        while path != path.parent:
            for marker, _project_type in markers.items():
                if (path / marker).exists():
                    return str(path)

            path = path.parent

        return None


_global_tracker: SubdirectoryHintTracker | None = None


def get_subdirectory_hint_tracker() -> SubdirectoryHintTracker:
    """Get the global subdirectory hint tracker instance."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = SubdirectoryHintTracker()
    return _global_tracker


def build_environment_hints(
    project_root: str | None = None,
    include_subdirs: bool = True,
) -> str:
    """Build environment hints for a project.

    Args:
        project_root: Optional project root path
        include_subdirs: Whether to include subdirectory hints

    Returns:
        Formatted environment hints string
    """
    if project_root is None:
        tracker = get_subdirectory_hint_tracker()
        project_root = tracker.detect_project_root()

    if not project_root:
        return ""

    hints = []

    if include_subdirs:
        tracker = get_subdirectory_hint_tracker()
        subdir_hints = tracker.get_hint_string(project_root)
        if subdir_hints:
            hints.append(subdir_hints)

    return "\n\n".join(hints) if hints else ""
