"""Auto-update system for Prometheus."""

import json
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger("prometheus.update")

UPDATE_INDEX_URL = "https://pypi.org/pypi/prometheus-agent/json"
UPDATE_CHECK_INTERVAL = 86400


class UpdateChecker:
    """Check for Prometheus updates."""

    def __init__(self, current_version: str = "0.8.0"):
        self._current_version = current_version
        self._latest_version: str | None = None
        self._update_info: dict[str, Any] | None = None

    def check(self) -> tuple[bool, str | None]:
        """Check for updates.

        Returns:
            Tuple of (update_available, latest_version)
        """
        try:
            info = self._fetch_latest_info()

            if info:
                latest = info.get("version", self._current_version)
                self._latest_version = latest
                self._update_info = info

                if self._compare_versions(latest, self._current_version) > 0:
                    return True, latest

        except Exception as e:
            logger.error(f"Update check failed: {e}")

        return False, None

    def _fetch_latest_info(self) -> dict[str, Any] | None:
        """Fetch latest package info from PyPI."""
        try:
            import urllib.request

            url = f"{UPDATE_INDEX_URL}"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data.get("info")

        except Exception as e:
            logger.debug(f"Failed to fetch from PyPI: {e}")

        return None

    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare version strings.

        Returns:
            Positive if v1 > v2, 0 if equal, negative if v1 < v2
        """

        def parse(v):
            return [int(x) for x in v.split(".")[:3]]

        p1, p2 = parse(v1), parse(v2)

        for i in range(max(len(p1), len(p2))):
            n1 = p1[i] if i < len(p1) else 0
            n2 = p2[i] if i < len(p2) else 0
            if n1 != n2:
                return n1 - n2

        return 0

    def get_update_info(self) -> dict[str, Any] | None:
        """Get detailed update information."""
        return self._update_info

    def get_changelog(self) -> str:
        """Get changelog for the update."""
        if not self._update_info:
            return ""

        release_notes = self._update_info.get("summary", "")

        if not release_notes:
            releases = self._update_info.get("releases", {})
            latest = self._latest_version
            if latest and latest in releases:
                release_data = releases[latest]
                if release_data and len(release_data) > 0:
                    release_notes = release_data[0].get("comment_text", "")

        return release_notes or "No release notes available."


class UpdateInstaller:
    """Install Prometheus updates."""

    def __init__(self):
        self._backup_dir: Path | None = None

    def install(self, version: str = "latest") -> bool:
        """Install an update.

        Args:
            version: Version to install (default: latest)

        Returns:
            True if installation was successful
        """
        try:
            if not self._backup_current():
                return False

            success = self._pip_install(version)

            if not success:
                self._restore_backup()

            return success

        except Exception as e:
            logger.error(f"Installation failed: {e}")
            self._restore_backup()
            return False

    def _backup_current(self) -> bool:
        """Backup the current installation."""
        try:
            self._backup_dir = Path(tempfile.mkdtemp(prefix="prometheus_backup_"))

            current_file = Path(__file__).resolve()
            install_location = current_file.parent

            backup_file = self._backup_dir / "current_version.txt"
            with open(backup_file, "w") as f:
                f.write(f"Location: {install_location}\n")
                f.write(f"Backup time: {__import__('datetime').datetime.now().isoformat()}\n")

            logger.info(f"Backup created at {self._backup_dir}")
            return True

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False

    def _pip_install(self, version: str = "latest") -> bool:
        """Install using pip."""
        try:
            package = f"prometheus-agent=={version}" if version != "latest" else "prometheus-agent"

            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package, "--upgrade"],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                logger.info("Installation successful")
                return True
            else:
                logger.error(f"pip install failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Installation timed out")
            return False
        except Exception as e:
            logger.error(f"pip install error: {e}")
            return False

    def _restore_backup(self):
        """Restore from backup."""
        if not self._backup_dir:
            return

        logger.info("Restoring from backup...")

    def cleanup_backup(self):
        """Clean up backup directory."""
        if self._backup_dir and self._backup_dir.exists():
            shutil.rmtree(self._backup_dir, ignore_errors=True)


class UpdateManager:
    """Manage update checking and installation."""

    def __init__(self, current_version: str = "0.8.0"):
        self._checker = UpdateChecker(current_version)
        self._installer = UpdateInstaller()
        self._last_check_file = Path.home() / ".prometheus" / "last_update_check.txt"

    def check_and_notify(self) -> tuple[bool, str | None]:
        """Check for updates and notify if available.

        Returns:
            Tuple of (update_available, latest_version)
        """
        if self._should_skip_check():
            return False, None

        update_available, latest_version = self._checker.check()

        self._update_last_check_time()

        return update_available, latest_version

    def _should_skip_check(self) -> bool:
        """Check if we should skip the update check."""
        if not self._last_check_file.exists():
            return False

        try:
            with open(self._last_check_file) as f:
                last_check = float(f.read().strip())

            import time

            if time.time() - last_check < UPDATE_CHECK_INTERVAL:
                return True

        except Exception:
            pass

        return False

    def _update_last_check_time(self):
        """Update the last check timestamp."""
        try:
            import time

            self._last_check_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._last_check_file, "w") as f:
                f.write(str(time.time()))
        except Exception:
            pass

    def install_update(self, version: str = "latest") -> bool:
        """Install an update.

        Args:
            version: Version to install

        Returns:
            True if installation was successful
        """
        return self._installer.install(version)

    def get_status(self) -> dict[str, Any]:
        """Get update status."""
        return {
            "current_version": self._checker._current_version,
            "latest_version": self._checker._latest_version,
            "update_available": self._checker._latest_version is not None
            and self._checker._compare_versions(
                self._checker._latest_version, self._checker._current_version
            )
            > 0,
        }


def check_for_updates() -> tuple[bool, str | None]:
    """Check for updates (convenience function)."""
    manager = UpdateManager()
    return manager.check_and_notify()


def install_update(version: str = "latest") -> bool:
    """Install an update (convenience function)."""
    manager = UpdateManager()
    return manager.install_update(version)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prometheus Auto-Update")
    parser.add_argument("command", choices=["check", "install"], help="Command")
    parser.add_argument("--version", default="latest", help="Version to install")

    args = parser.parse_args()

    if args.command == "check":
        update_available, latest = check_for_updates()
        if update_available:
            print(f"Update available: {latest}")
        else:
            print("No update available")

    elif args.command == "install":
        print(f"Installing version {args.version}...")
        success = install_update(args.version)
        print(f"Installation {'successful' if success else 'failed'}")
