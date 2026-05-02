"""Resolve PROMETHEUS_HOME for standalone skill scripts.

Skill scripts may run outside the Prometheus process (e.g. system Python,
nix env, CI) where ``prometheus.constants_core`` is not importable.  This module
provides the same ``get_prometheus_home()`` and ``display_prometheus_home()``
contracts as ``prometheus.constants_core`` without requiring it on ``sys.path``.

When ``prometheus.constants_core`` IS available it is used directly so that any
future enhancements (profile resolution, Docker detection, etc.) are
picked up automatically.  The fallback path replicates the core logic
from ``prometheus.constants_core.py`` using only the stdlib.

All scripts under ``google-workspace/scripts/`` should import from here
instead of duplicating the ``PROMETHEUS_HOME = Path(os.getenv(...))`` pattern.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from prometheus.constants_core import display_prometheus_home as display_prometheus_home
    from prometheus.constants_core import get_prometheus_home as get_prometheus_home
except (ModuleNotFoundError, ImportError):

    def get_prometheus_home() -> Path:
        """Return the Prometheus home directory (default: ~/.prometheus).

        Mirrors ``prometheus.constants_core.get_prometheus_home()``."""
        val = os.environ.get("PROMETHEUS_HOME", "").strip()
        return Path(val) if val else Path.home() / ".prometheus"

    def display_prometheus_home() -> str:
        """Return a user-friendly ``~/``-shortened display string.

        Mirrors ``prometheus.constants_core.display_prometheus_home()``."""
        home = get_prometheus_home()
        try:
            return "~/" + str(home.relative_to(Path.home()))
        except ValueError:
            return str(home)
