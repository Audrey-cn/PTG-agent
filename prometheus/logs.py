from __future__ import annotations

import contextlib
import logging
import shutil
from logging.handlers import RotatingFileHandler
from pathlib import Path

from prometheus._paths import get_paths

_logger_configured = False


def get_log_file_path() -> Path:
    try:
        return get_paths().logs / "prometheus.log"
    except Exception:
        return get_paths().home / "prometheus.log"


def setup_logging(level: str = "INFO", log_file: str | None = None) -> None:
    global _logger_configured
    if _logger_configured:
        return

    log_path = Path(log_file) if log_file else get_log_file_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger("prometheus")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        str(log_path),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING)
    root_logger.addHandler(console_handler)

    _logger_configured = True


def rotate_logs(max_size_mb: int = 10, max_files: int = 5) -> None:
    log_path = get_log_file_path()
    if not log_path.exists():
        return

    max_bytes = max_size_mb * 1024 * 1024

    if log_path.stat().st_size < max_bytes:
        return

    for i in range(max_files - 1, 0, -1):
        older = log_path.parent / f"{log_path.name}.{i}"
        newer = log_path.parent / f"{log_path.name}.{i - 1}" if i > 1 else log_path
        if newer.exists():
            if older.exists():
                older.unlink()
            shutil.move(str(newer), str(older))

    if log_path.exists():
        first_backup = log_path.parent / f"{log_path.name}.1"
        if first_backup.exists():
            first_backup.unlink()
        shutil.move(str(log_path), str(first_backup))

    log_path.touch()


def read_recent_logs(lines: int = 100) -> list[str]:
    log_path = get_log_file_path()
    if not log_path.exists():
        return []

    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        return [line.rstrip("\n") for line in all_lines[-lines:]]
    except Exception:
        return []


def clear_logs() -> None:
    log_path = get_log_file_path()
    if not log_path.exists():
        return

    log_path.write_text("", encoding="utf-8")

    for backup in sorted(log_path.parent.glob(f"{log_path.name}.*")):
        with contextlib.suppress(Exception):
            backup.unlink()
