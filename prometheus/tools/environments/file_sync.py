"""File synchronization utilities for execution environments."""

import hashlib
import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FileSync:
    """
    File synchronization utility for execution environments.

    Handles copying files between local and remote/environment workspaces,
    with caching to avoid redundant transfers.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._cache_dir = Path(
            self._config.get("cache_dir", "~/.prometheus/file_sync")
        ).expanduser()
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._file_hashes: dict[str, str] = {}

    def sync_file(
        self,
        source_path: str,
        dest_path: str,
        source_env: str = "local",
        dest_env: str = "local",
        force: bool = False,
    ) -> bool:
        """
        Synchronize a single file between two environments.

        Args:
            source_path: Source file path
            dest_path: Destination file path
            source_env: Source environment name
            dest_env: Destination environment name
            force: Force sync even if file appears unchanged

        Returns:
            True if file was synced
        """
        source_file = Path(source_path)
        if not source_file.exists():
            logger.error(f"Source file not found: {source_path}")
            return False

        if not force and self._is_unchanged(source_path):
            logger.debug(f"File unchanged, skipping sync: {source_path}")
            return False

        if source_env == "local" and dest_env == "local":
            return self._copy_local(source_path, dest_path)

        logger.error(f"Sync between {source_env} and {dest_env} not implemented")
        return False

    def sync_directory(
        self,
        source_dir: str,
        dest_dir: str,
        source_env: str = "local",
        dest_env: str = "local",
        pattern: str = "*",
        force: bool = False,
    ) -> tuple[int, int]:
        """
        Synchronize a directory between environments.

        Args:
            source_dir: Source directory
            dest_dir: Destination directory
            source_env: Source environment
            dest_env: Destination environment
            pattern: File pattern to match
            force: Force sync even if files unchanged

        Returns:
            (synced_count, skipped_count)
        """
        source = Path(source_dir)
        if not source.exists():
            logger.error(f"Source directory not found: {source_dir}")
            return (0, 0)

        synced = 0
        skipped = 0

        for source_file in source.rglob(pattern):
            if source_file.is_file():
                rel_path = source_file.relative_to(source)
                dest_file = Path(dest_dir) / rel_path

                if self.sync_file(str(source_file), str(dest_file), source_env, dest_env, force):
                    synced += 1
                else:
                    skipped += 1

        return (synced, skipped)

    def _copy_local(self, source: str, dest: str) -> bool:
        """Copy file locally."""
        try:
            import shutil

            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            self._update_hash(source)
            logger.debug(f"Copied file: {source} -> {dest}")
            return True
        except Exception as e:
            logger.error(f"Failed to copy file {source} -> {dest}: {e}")
            return False

    def _get_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        return sha256_hash.hexdigest()

    def _is_unchanged(self, file_path: str) -> bool:
        """Check if file hasn't changed since last sync."""
        current_hash = self._get_file_hash(file_path)
        last_hash = self._file_hashes.get(file_path)
        return current_hash == last_hash

    def _update_hash(self, file_path: str) -> None:
        """Update cached file hash."""
        self._file_hashes[file_path] = self._get_file_hash(file_path)

    def clear_cache(self) -> None:
        """Clear all cached file hashes."""
        self._file_hashes.clear()
        logger.debug("File sync cache cleared")

    def get_sync_stats(self) -> dict[str, Any]:
        """Get file sync statistics."""
        return {"cached_files": len(self._file_hashes), "cache_dir": str(self._cache_dir)}


class RsyncSync(FileSync):
    """
    File synchronization using rsync for efficient transfers.

    rsync is faster for large directories and can compress data
    and skip unchanged files.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._rsync_args = self._config.get("rsync_args", "-avz")
        self._ssh_args = self._config.get("ssh_args", "-o StrictHostKeyChecking=no")

    def is_available(self) -> bool:
        """Check if rsync is available."""
        try:
            result = subprocess.run(["rsync", "--version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def sync_directory_rsync(
        self,
        source_dir: str,
        dest_dir: str,
        source_host: str | None = None,
        dest_host: str | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> bool:
        """
        Sync directory using rsync.

        Args:
            source_dir: Source directory
            dest_dir: Destination directory
            source_host: Optional source host (user@host format)
            dest_host: Optional destination host
            exclude_patterns: List of patterns to exclude

        Returns:
            True if successful
        """
        rsync_cmd = ["rsync", self._rsync_args]

        if exclude_patterns:
            for pattern in exclude_patterns:
                rsync_cmd.extend(["--exclude", pattern])

        source = source_dir
        if source_host:
            source = f"{source_host}:{source_dir}"

        dest = dest_dir
        if dest_host:
            dest = f"{dest_host}:{dest_dir}"

        rsync_cmd.extend([source, dest])

        logger.debug(f"Running rsync: {' '.join(rsync_cmd)}")

        try:
            result = subprocess.run(rsync_cmd, capture_output=True, text=True, timeout=3600)

            if result.returncode != 0:
                logger.error(f"rsync failed: {result.stderr}")
                return False

            logger.debug("rsync successful")
            return True
        except Exception as e:
            logger.error(f"rsync failed: {e}")
            return False


class GitSync(FileSync):
    """
    File synchronization using Git commits.

    Useful when changes should be version controlled.
    """

    def sync_to_git(
        self, repo_dir: str, message: str = "Auto-sync from Prometheus", branch: str | None = None
    ) -> bool:
        """
        Sync directory as a git commit.

        Args:
            repo_dir: Git repository directory
            message: Commit message
            branch: Optional branch to commit to

        Returns:
            True if successful
        """
        try:
            subprocess.run(["git", "add", "-A"], cwd=repo_dir, capture_output=True, timeout=60)

            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 1 and "nothing to commit" in result.stdout:
                logger.debug("No changes to commit")
                return True

            if result.returncode != 0:
                logger.error(f"Git commit failed: {result.stderr}")
                return False

            if branch:
                push_result = subprocess.run(
                    ["git", "push", "origin", branch],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if push_result.returncode != 0:
                    logger.error(f"Git push failed: {push_result.stderr}")
                    return False

            return True
        except Exception as e:
            logger.error(f"Git sync failed: {e}")
            return False
