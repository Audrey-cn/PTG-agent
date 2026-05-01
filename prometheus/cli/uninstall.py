from __future__ import annotations

import shutil

from prometheus.config import get_prometheus_home


def cmd_uninstall(args) -> int:
    prometheus_home = get_prometheus_home()

    if not prometheus_home.exists():
        print("Prometheus is not installed.")
        return 0

    if not hasattr(args, "yes") or not args.yes:
        print(f"This will remove all Prometheus data from: {prometheus_home}")
        print("This action cannot be undone.")
        response = input("Are you sure you want to continue? [y/N] ")
        if response.lower() != "y":
            print("Uninstall cancelled.")
            return 1

    cache_dir = prometheus_home / "cache"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        print("Removed cache directory.")

    logs_dir = prometheus_home / "logs"
    if logs_dir.exists():
        shutil.rmtree(logs_dir)
        print("Removed logs directory.")

    sessions_dir = prometheus_home / "sessions"
    if sessions_dir.exists():
        shutil.rmtree(sessions_dir)
        print("Removed sessions directory.")

    checkpoints_dir = prometheus_home / "checkpoints"
    if checkpoints_dir.exists():
        shutil.rmtree(checkpoints_dir)
        print("Removed checkpoints directory.")

    config_file = prometheus_home / "config.yaml"
    if config_file.exists():
        config_file.unlink()
        print("Removed config.yaml.")

    if hasattr(args, "purge") and args.purge:
        shutil.rmtree(prometheus_home)
        print(f"Removed {prometheus_home}.")
    else:
        soul_file = prometheus_home / "SOUL.md"
        memories_dir = prometheus_home / "memories"

        if soul_file.exists():
            print(f"Retained: {soul_file}")
        if memories_dir.exists():
            print(f"Retained: {memories_dir}")

    print("Prometheus has been uninstalled.")
    return 0
