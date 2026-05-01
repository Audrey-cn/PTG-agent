"""Shared utility functions for Prometheus tools."""

import os
from pathlib import Path


def atomic_replace(src: Path, dst: Path) -> None:
    """Atomically replace dst with src using os.replace (atomic on POSIX)."""
    os.replace(src, dst)
