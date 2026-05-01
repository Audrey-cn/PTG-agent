"""Unified self-relaunch for Prometheus CLI."""

import os
import shutil
import sys
from collections.abc import Sequence

from prometheus.cli._parser import (
    PRE_ARGPARSE_INHERITED_FLAGS,
    build_top_level_parser,
)


def _build_inherited_flag_table() -> list[Tuple[str, bool]]:
    """Build the ``(option_string, takes_value)`` table of flags that must
    survive a self-relaunch, by introspecting the real parser used by
    ``prometheus`` itself.

    A flag participates if its argparse Action carries
    ``inherit_on_relaunch = True`` — set by ``_parser._inherited_flag``.
    """
    parser, _subparsers, chat_parser = build_top_level_parser()

    table: list[Tuple[str, bool]] = []
    seen: Set[Tuple[str, bool]] = set()
    for p in (parser, chat_parser):
        for action in p._actions:
            if not action.option_strings:
                continue
            if not getattr(action, "inherit_on_relaunch", False):
                continue
            takes_value = action.nargs != 0
            for opt in action.option_strings:
                key = (opt, takes_value)
                if key not in seen:
                    seen.add(key)
                    table.append(key)

    table.extend(PRE_ARGPARSE_INHERITED_FLAGS)
    return table


_INHERITED_FLAGS_TABLE = _build_inherited_flag_table()


def _extract_inherited_flags(argv: Sequence[str]) -> List[str]:
    """Pull out flags that should carry over into a self-relaunched prometheus."""
    flags: List[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if "=" in arg:
            key = arg.split("=", 1)[0]
            for flag, _ in _INHERITED_FLAGS_TABLE:
                if key == flag:
                    flags.append(arg)
                    break
            i += 1
            continue

        for flag, takes_value in _INHERITED_FLAGS_TABLE:
            if arg == flag:
                flags.append(arg)
                if takes_value and i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                    flags.append(argv[i + 1])
                    i += 1
                break
        i += 1
    return flags


def resolve_prometheus_bin() -> str | None:
    """Find the prometheus entry point.

    Priority:
      1. ``sys.argv[0]`` if it resolves to a real executable.
      2. ``shutil.which("prometheus")`` on PATH.
      3. ``None`` → caller should fall back to ``python -m prometheus_cli.main``.
    """
    argv0 = sys.argv[0]

    if os.path.isabs(argv0) and os.path.isfile(argv0) and os.access(argv0, os.X_OK):
        return argv0

    if not argv0.startswith("-") and os.path.isfile(argv0):
        abs_path = os.path.abspath(argv0)
        if os.access(abs_path, os.X_OK):
            return abs_path

    path_bin = shutil.which("prometheus")
    if path_bin:
        return path_bin

    return None


def build_relaunch_argv(
    extra_args: Sequence[str],
    *,
    preserve_inherited: bool = True,
    original_argv: Sequence[str] | None = None,
) -> List[str]:
    """Construct an argv list for replacing the current process with prometheus.

    Args:
        extra_args: Arguments to append (e.g. ``["--resume", id]``).
        preserve_inherited: Whether to carry over UI / behaviour flags
            tagged with ``inherit_on_relaunch`` in the parser.
        original_argv: The original argv to scan for flags (defaults to
            ``sys.argv[1:]``).
    """
    bin_path = resolve_prometheus_bin()

    if bin_path:
        argv = [bin_path]
    else:
        argv = [sys.executable, "-m", "prometheus_cli.main"]

    src = list(original_argv) if original_argv is not None else list(sys.argv[1:])

    if preserve_inherited:
        argv.extend(_extract_inherited_flags(src))

    argv.extend(extra_args)
    return argv


def relaunch(
    extra_args: Sequence[str],
    *,
    preserve_inherited: bool = True,
    original_argv: Sequence[str] | None = None,
) -> None:
    """Replace the current process with a fresh prometheus invocation."""
    new_argv = build_relaunch_argv(
        extra_args, preserve_inherited=preserve_inherited, original_argv=original_argv
    )
    os.execvp(new_argv[0], new_argv)
