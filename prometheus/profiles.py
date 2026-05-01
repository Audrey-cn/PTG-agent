from __future__ import annotations

import shutil
import json
from dataclasses import dataclass, field
from pathlib import Path

from prometheus.config import get_prometheus_home


@dataclass
class Profile:
    name: str
    config_path: Path
    is_active: bool = False


def _profiles_dir() -> Path:
    return get_prometheus_home() / "profiles"


def _active_symlink() -> Path:
    return get_prometheus_home() / "active_profile"


def _profile_meta_path(name: str) -> Path:
    return _profiles_dir() / name / "profile.json"


class ProfileManager:
    def __init__(self) -> None:
        self._base = get_prometheus_home()

    def list_profiles(self) -> list[Profile]:
        profiles_dir = _profiles_dir()
        if not profiles_dir.exists():
            return []
        active_target = self._resolve_active()
        result: list[Profile] = []
        for entry in sorted(profiles_dir.iterdir()):
            if entry.is_dir() and (entry / "profile.json").exists():
                name = entry.name
                config_path = entry / "config.yaml"
                is_active = active_target is not None and entry == active_target
                result.append(Profile(name=name, config_path=config_path, is_active=is_active))
        return result

    def get_active_profile(self) -> Profile | None:
        active_target = self._resolve_active()
        if active_target is None:
            return None
        config_path = active_target / "config.yaml"
        return Profile(name=active_target.name, config_path=config_path, is_active=True)

    def create_profile(self, name: str, base_on: str | None = None) -> Profile:
        profile_dir = _profiles_dir() / name
        if profile_dir.exists():
            raise FileExistsError(f"Profile '{name}' already exists")
        profile_dir.mkdir(parents=True, exist_ok=True)

        if base_on is not None:
            source_dir = _profiles_dir() / base_on
            if not source_dir.exists():
                raise FileNotFoundError(f"Base profile '{base_on}' not found")
            for item in source_dir.iterdir():
                if item.name == "profile.json":
                    continue
                dest = profile_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
        else:
            default_config = self._base / "config.yaml"
            if default_config.exists():
                shutil.copy2(default_config, profile_dir / "config.yaml")

        meta = {"name": name, "base_on": base_on}
        meta_path = _profile_meta_path(name)
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

        config_path = profile_dir / "config.yaml"
        return Profile(name=name, config_path=config_path, is_active=False)

    def switch_profile(self, name: str) -> bool:
        profile_dir = _profiles_dir() / name
        if not profile_dir.exists():
            return False
        symlink = _active_symlink()
        if symlink.is_symlink() or symlink.exists():
            symlink.unlink()
        symlink.symlink_to(profile_dir)
        return True

    def delete_profile(self, name: str) -> bool:
        profile_dir = _profiles_dir() / name
        if not profile_dir.exists():
            return False
        active_target = self._resolve_active()
        if active_target is not None and active_target.name == name:
            symlink = _active_symlink()
            if symlink.is_symlink() or symlink.exists():
                symlink.unlink()
        shutil.rmtree(profile_dir)
        return True

    def rename_profile(self, old_name: str, new_name: str) -> bool:
        old_dir = _profiles_dir() / old_name
        new_dir = _profiles_dir() / new_name
        if not old_dir.exists():
            return False
        if new_dir.exists():
            return False
        old_dir.rename(new_dir)

        meta_path = _profile_meta_path(new_name)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["name"] = new_name
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

        active_target = self._resolve_active()
        if active_target is not None and active_target.name == old_name:
            symlink = _active_symlink()
            if symlink.is_symlink() or symlink.exists():
                symlink.unlink()
            symlink.symlink_to(new_dir)
        return True

    def _resolve_active(self) -> Path | None:
        symlink = _active_symlink()
        if not symlink.exists():
            return None
        try:
            target = symlink.resolve()
            if target.exists() and target.is_dir():
                return target
        except (OSError, ValueError):
            pass
        return None
