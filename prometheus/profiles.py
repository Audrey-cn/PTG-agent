"""Profile management for Prometheus."""

import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prometheus._paths import get_paths

logger = logging.getLogger("prometheus.profiles")

DEFAULT_PROFILE_NAME = "default"


@dataclass
class Profile:
    """A configuration profile."""

    name: str
    home: Path
    is_active: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_path(self, *parts) -> Path:
        """Get a path within this profile's home directory."""
        return self.home.joinpath(*parts)


class ProfileManager:
    """Manages Prometheus configuration profiles.

    Profiles provide isolated configuration environments with their own:
    - Config files
    - Memory files (USER.md, MEMORY.md, SOUL.md)
    - Session history
    - Plugin configurations
    """

    def __init__(self, profiles_dir: Path | None = None):
        """Initialize the profile manager.

        Args:
            profiles_dir: Directory for profile storage
        """
        self._profiles_dir = profiles_dir or get_paths().home / "profiles"
        self._profiles_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: dict[str, Profile] = {}
        self._active_profile_name: str | None = None
        self._load_active_profile()

    def _get_prometheus_home_for_profile(self, profile_name: str) -> Path:
        """Get the PROMETHEUS_HOME equivalent for a profile."""
        return self._profiles_dir / profile_name

    def _load_active_profile(self) -> None:
        """Load the active profile from disk."""
        if ACTIVE_PROFILE_FILE.exists():
            try:
                with open(ACTIVE_PROFILE_FILE) as f:
                    self._active_profile_name = f.read().strip()
            except Exception as e:
                logger.error(f"Failed to load active profile: {e}")
                self._active_profile_name = DEFAULT_PROFILE_NAME
        else:
            self._active_profile_name = DEFAULT_PROFILE_NAME

    def _save_active_profile(self, profile_name: str) -> None:
        """Save the active profile to disk."""
        ACTIVE_PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(ACTIVE_PROFILE_FILE, "w") as f:
            f.write(profile_name)

    def _ensure_profile_home(self, profile: Profile) -> None:
        """Ensure a profile's home directory structure exists."""
        dirs = ["", "memories", "sessions", "plugins", "cache"]
        for d in dirs:
            profile.get_path(d).mkdir(parents=True, exist_ok=True)

        paths = get_paths()
        config_source = paths.home / "config.yaml"
        if config_source.exists():
            config_dest = profile.get_path("config.yaml")
            if not config_dest.exists():
                shutil.copy2(config_source, config_dest)

        soul_source = paths.home / "SOUL.md"
        if soul_source.exists():
            shutil.copy2(soul_source, profile.get_path("SOUL.md"))

        user_source = paths.home / "memories" / "USER.md"
        if user_source.exists():
            profile.get_path("memories").mkdir(parents=True, exist_ok=True)
            shutil.copy2(user_source, profile.get_path("memories", "USER.md"))

    def create_profile(self, name: str, copy_from: str | None = None) -> Profile:
        """Create a new profile.

        Args:
            name: Name of the profile
            copy_from: Optional profile to copy settings from

        Returns:
            Created Profile
        """
        if name in self._profiles:
            raise ValueError(f"Profile already exists: {name}")

        profile_home = self._get_prometheus_home_for_profile(name)
        profile = Profile(name=name, home=profile_home)
        self._ensure_profile_home(profile)

        if copy_from:
            source_home = self._get_prometheus_home_for_profile(copy_from)
            if source_home.exists():
                for item in source_home.iterdir():
                    if item.is_file():
                        dest = profile.get_path(item.name)
                        if not dest.exists():
                            shutil.copy2(item, dest)

        self._profiles[name] = profile
        logger.info(f"Created profile: {name}")
        return profile

    def delete_profile(self, name: str, force: bool = False) -> None:
        """Delete a profile.

        Args:
            name: Name of the profile
            force: Force deletion even if active
        """
        if name == DEFAULT_PROFILE_NAME and not force:
            raise ValueError("Cannot delete default profile")

        if name == self._active_profile_name:
            raise ValueError("Cannot delete active profile")

        profile = self._profiles.get(name)
        if profile:
            shutil.rmtree(profile.home, ignore_errors=True)
            del self._profiles[name]
            logger.info(f"Deleted profile: {name}")

    def activate_profile(self, name: str) -> None:
        """Activate a profile.

        Args:
            name: Name of the profile
        """
        if name not in self._profiles:
            self.get_profile(name)

        self._active_profile_name = name
        self._save_active_profile(name)
        os.environ["PROMETHEUS_PROFILE"] = name
        logger.info(f"Activated profile: {name}")

    def get_profile(self, name: str) -> Profile:
        """Get a profile by name.

        Args:
            name: Name of the profile

        Returns:
            Profile
        """
        if name in self._profiles:
            return self._profiles[name]

        profile_home = self._get_prometheus_home_for_profile(name)
        if not profile_home.exists():
            raise ValueError(f"Profile not found: {name}")

        profile = Profile(name=name, home=profile_home)
        self._profiles[name] = profile
        return profile

    def get_active_profile(self) -> Profile:
        """Get the currently active profile.

        Returns:
            Active Profile
        """
        name = self._active_profile_name or DEFAULT_PROFILE_NAME

        if name not in self._profiles:
            profile_home = self._get_prometheus_home_for_profile(name)
            if not profile_home.exists():
                profile = Profile(name=name, home=profile_home)
                self._ensure_profile_home(profile)
                self._profiles[name] = profile
            else:
                self._profiles[name] = Profile(name=name, home=profile_home)

        profile = self._profiles[name]
        profile.is_active = name == self._active_profile_name
        return profile

    def list_profiles(self) -> list[Profile]:
        """List all profiles.

        Returns:
            List of profiles
        """
        if not self._profiles_dir.exists():
            return []

        profiles = []
        for item in self._profiles_dir.iterdir():
            if item.is_dir():
                profile = self.get_profile(item.name)
                profiles.append(profile)

        return profiles

    def get_active_profile_name(self) -> str:
        """Get the name of the active profile.

        Returns:
            Active profile name
        """
        return self._active_profile_name or DEFAULT_PROFILE_NAME

    def clone_profile(self, source: str, destination: str) -> Profile:
        """Clone a profile.

        Args:
            source: Source profile name
            destination: Destination profile name

        Returns:
            Cloned Profile
        """
        return self.create_profile(destination, copy_from=source)

    def export_profile(self, name: str, export_path: Path) -> None:
        """Export a profile to a directory.

        Args:
            name: Profile name
            export_path: Path to export to
        """
        profile = self.get_profile(name)
        shutil.copytree(profile.home, export_path, dirs_exist_ok=True)
        logger.info(f"Exported profile {name} to {export_path}")

    def import_profile(self, name: str, import_path: Path) -> Profile:
        """Import a profile from a directory.

        Args:
            name: Profile name
            import_path: Path to import from

        Returns:
            Imported Profile
        """
        profile_home = self._get_prometheus_home_for_profile(name)
        shutil.copytree(import_path, profile_home, dirs_exist_ok=True)

        profile = Profile(name=name, home=profile_home)
        self._profiles[name] = profile
        logger.info(f"Imported profile {name} from {import_path}")
        return profile

    def get_prometheus_home(self) -> Path:
        """Get the Prometheus home directory for the active profile.

        Returns:
            Path to active profile's home
        """
        return self.get_active_profile().home

    def get_config_path(self) -> Path:
        """Get the config file path for the active profile.

        Returns:
            Path to config.yaml
        """
        return self.get_prometheus_home() / "config.yaml"

    def get_memory_path(self, filename: str) -> Path:
        """Get a memory file path for the active profile.

        Args:
            filename: Memory filename

        Returns:
            Path to memory file
        """
        memory_dir = self.get_prometheus_home() / "memories"
        memory_dir.mkdir(parents=True, exist_ok=True)
        return memory_dir / filename


_global_profile_manager: ProfileManager | None = None


def get_profile_manager() -> ProfileManager:
    """Get the global profile manager instance."""
    global _global_profile_manager
    if _global_profile_manager is None:
        _global_profile_manager = ProfileManager()
    return _global_profile_manager


def get_prometheus_home() -> Path:
    """Get the Prometheus home directory for the active profile.

    Returns:
        Path to Prometheus home
    """
    return get_profile_manager().get_prometheus_home()


def get_active_profile_name() -> str:
    """Get the name of the active profile.

    Returns:
        Active profile name
    """
    return get_profile_manager().get_active_profile_name()


def activate_profile(name: str) -> None:
    """Activate a profile.

    Args:
        name: Profile name
    """
    get_profile_manager().activate_profile(name)


def list_profiles() -> list[Profile]:
    """List all profiles.

    Returns:
        List of profiles
    """
    return get_profile_manager().list_profiles()
