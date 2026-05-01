"""Tool execution utilities for Prometheus."""

import concurrent.futures
import contextlib
import json
import logging
import os
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Tools that must never run concurrently (interactive / user-facing)
_NEVER_PARALLEL_TOOLS = frozenset({"clarify", "confirm"})

# Read-only tools with no shared mutable session state
_PARALLEL_SAFE_TOOLS = frozenset(
    {
        "ha_get_state",
        "ha_list_entities",
        "ha_list_services",
        "read_file",
        "search_files",
        "session_search",
        "skill_view",
        "skills_list",
        "vision_analyze",
        "web_extract",
        "web_search",
        "dir_search",
        "file_glob",
        "grep",
    }
)

# File tools can run concurrently when they target independent paths
_PATH_SCOPED_TOOLS = frozenset({"read_file", "write_file", "patch", "edit_file"})

# Maximum number of concurrent worker threads for parallel tool execution
_MAX_TOOL_WORKERS = 8

# Patterns that indicate a terminal command may modify/delete files
_DESTRUCTIVE_PATTERNS = re.compile(
    r"""(?:^|\s|&&|\|\||;|`)(?:
        rm\s|rmdir\s|
        cp\s|install\s|
        mv\s|
        sed\s+-i|
        truncate\s|
        dd\s|
        shred\s|
        git\s+(?:reset|clean|checkout)\s
    )""",
    re.VERBOSE,
)

# Output redirects that overwrite files (> but not >>)
_REDIRECT_OVERWRITE = re.compile(r"[^>]>[^>]|^>[^>]")


def _is_destructive_command(cmd: str) -> bool:
    """Heuristic: does this terminal command look like it modifies/deletes files?"""
    if not cmd:
        return False
    if _DESTRUCTIVE_PATTERNS.search(cmd):
        return True
    return bool(_REDIRECT_OVERWRITE.search(cmd))


def _extract_parallel_scope_path(tool_name: str, function_args: dict) -> Path | None:
    """Return the normalized file target for path-scoped tools."""
    if tool_name not in _PATH_SCOPED_TOOLS:
        return None

    raw_path = function_args.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None

    expanded = Path(raw_path).expanduser()
    if expanded.is_absolute():
        return Path(os.path.abspath(str(expanded)))

    return Path(os.path.abspath(str(Path.cwd() / expanded)))


def _paths_overlap(left: Path, right: Path) -> bool:
    """Return True when two paths may refer to the same subtree."""
    left_parts = left.parts
    right_parts = right.parts
    if not left_parts or not right_parts:
        return bool(left_parts) == bool(right_parts) and bool(left_parts)
    common_len = min(len(left_parts), len(right_parts))
    return left_parts[:common_len] == right_parts[:common_len]


def should_parallelize_tool_batch(tool_calls: list[dict[str, Any]]) -> bool:
    """Return True when a tool-call batch is safe to run concurrently.

    Args:
        tool_calls: List of tool call dictionaries with 'function.name' and 'function.arguments'

    Returns:
        True if the batch can be executed in parallel, False for sequential execution
    """
    if len(tool_calls) <= 1:
        return False

    tool_names = [tc.get("function", {}).get("name", "") for tc in tool_calls]

    # Check for never-parallel tools
    if any(name in _NEVER_PARALLEL_TOOLS for name in tool_names):
        return False

    reserved_paths: list[Path] = []

    for tool_call in tool_calls:
        tool_name = tool_call.get("function", {}).get("name", "")
        try:
            raw_args = tool_call.get("function", {}).get("arguments", "{}")
            if isinstance(raw_args, str):
                function_args = json.loads(raw_args)
            else:
                function_args = raw_args or {}
        except (json.JSONDecodeError, TypeError):
            logger.debug(
                "Could not parse args for %s — defaulting to sequential; raw=%s",
                tool_name,
                str(tool_call.get("function", {}).get("arguments", ""))[:200],
            )
            return False

        if not isinstance(function_args, dict):
            logger.debug(
                "Non-dict args for %s (%s) — defaulting to sequential",
                tool_name,
                type(function_args).__name__,
            )
            return False

        # Check path-scoped tools for conflicts
        if tool_name in _PATH_SCOPED_TOOLS:
            scoped_path = _extract_parallel_scope_path(tool_name, function_args)
            if scoped_path is None:
                return False
            if any(_paths_overlap(scoped_path, existing) for existing in reserved_paths):
                return False
            reserved_paths.append(scoped_path)
            continue

        # Check if tool is known to be parallel-safe
        if tool_name not in _PARALLEL_SAFE_TOOLS:
            return False

    return True


class ParallelToolExecutor:
    """Executor for running multiple tools in parallel when safe.

    Propagates approval/sudo callbacks to worker threads for ACP sessions
    running concurrently in a ThreadPoolExecutor. This mirrors the pattern
    in Hermes's run_agent.py to avoid GHSA-qg5c-hvr5-hjgr (approval
    callback leakage between concurrent ACP sessions).
    """

    def __init__(self, max_workers: int = _MAX_TOOL_WORKERS):
        self._max_workers = max_workers
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None

    def execute_batch(
        self,
        tool_calls: list[dict[str, Any]],
        handler: Callable[[dict[str, Any]], Any],
    ) -> list[tuple[int, Any]]:
        """Execute a batch of tool calls in parallel if safe.

        Args:
            tool_calls: List of tool call dictionaries
            handler: Function to call for each tool

        Returns:
            List of (index, result) tuples in original order
        """
        if not should_parallelize_tool_batch(tool_calls):
            results = []
            for i, tool_call in enumerate(tool_calls):
                try:
                    result = handler(tool_call)
                    results.append((i, result))
                except Exception as e:
                    logger.error(
                        f"Tool {tool_call.get('function', {}).get('name', 'unknown')} failed: {e}"
                    )
                    results.append((i, {"error": str(e)}))
            return results

        parent_approval_cb = None
        parent_sudo_cb = None
        try:
            from prometheus.tools.terminal_tool import (
                _get_approval_callback,
                _get_sudo_password_callback,
            )

            parent_approval_cb = _get_approval_callback()
            parent_sudo_cb = _get_sudo_password_callback()
        except Exception:
            pass

        def _run_with_callbacks(tool_call: dict[str, Any]) -> Any:
            if parent_approval_cb is not None or parent_sudo_cb is not None:
                try:
                    from prometheus.tools.terminal_tool import (
                        set_approval_callback,
                        set_sudo_password_callback,
                    )

                    if parent_approval_cb is not None:
                        with contextlib.suppress(Exception):
                            set_approval_callback(parent_approval_cb)
                    if parent_sudo_cb is not None:
                        with contextlib.suppress(Exception):
                            set_sudo_password_callback(parent_sudo_cb)
                except Exception:
                    pass
            try:
                return handler(tool_call)
            finally:
                try:
                    from prometheus.tools.terminal_tool import (
                        set_approval_callback,
                        set_sudo_password_callback,
                    )

                    set_approval_callback(None)
                    set_sudo_password_callback(None)
                except Exception:
                    pass

        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_index = {
                executor.submit(_run_with_callbacks, tool_call): i
                for i, tool_call in enumerate(tool_calls)
            }

            results = []
            for future in concurrent.futures.as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()
                    results.append((index, result))
                except Exception as e:
                    logger.error(f"Tool execution failed: {e}")
                    results.append((index, {"error": str(e)}))

        results.sort(key=lambda x: x[0])
        return results


# ── Surrogate Character Cleaning ──────────────────────────────────────────

_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")


def sanitize_surrogates(text: str) -> str:
    """Replace lone surrogate code points with U+FFFD (replacement character).

    Surrogates are invalid in UTF-8 and will crash ``json.dumps()``.
    This is a fast no-op when the text contains no surrogates.
    """
    if _SURROGATE_RE.search(text):
        return _SURROGATE_RE.sub("\ufffd", text)
    return text


def sanitize_structure_surrogates(payload: Any) -> bool:
    """Replace surrogate code points in nested dict/list payloads in-place.

    Returns True if any surrogates were replaced.
    """
    found = False

    def walk(node):
        nonlocal found
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str):
                    if _SURROGATE_RE.search(value):
                        node[key] = _SURROGATE_RE.sub("\ufffd", value)
                        found = True
                elif isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(node, list):
            for idx, value in enumerate(node):
                if isinstance(value, str):
                    if _SURROGATE_RE.search(value):
                        node[idx] = _SURROGATE_RE.sub("\ufffd", value)
                        found = True
                elif isinstance(value, (dict, list)):
                    walk(value)

    walk(payload)
    return found


def sanitize_messages_surrogates(messages: list[dict[str, Any]]) -> bool:
    """Sanitize surrogate characters from all string content in a messages list.

    Walks message dicts in-place. Returns True if any surrogates were found.
    """
    found = False
    for msg in messages:
        if not isinstance(msg, dict):
            continue

        content = msg.get("content")
        if isinstance(content, str) and _SURROGATE_RE.search(content):
            msg["content"] = _SURROGATE_RE.sub("\ufffd", content)
            found = True
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str) and _SURROGATE_RE.search(text):
                        part["text"] = _SURROGATE_RE.sub("\ufffd", text)
                        found = True

        name = msg.get("name")
        if isinstance(name, str) and _SURROGATE_RE.search(name):
            msg["name"] = _SURROGATE_RE.sub("\ufffd", name)
            found = True

        tool_calls = msg.get("tool_calls")
        if isinstance(tool_calls, list):
            for tc in tool_calls:
                if not isinstance(tc, dict):
                    continue
                tc_id = tc.get("id")
                if isinstance(tc_id, str) and _SURROGATE_RE.search(tc_id):
                    tc["id"] = _SURROGATE_RE.sub("\ufffd", tc_id)
                    found = True
                fn = tc.get("function")
                if isinstance(fn, dict):
                    fn_name = fn.get("name")
                    if isinstance(fn_name, str) and _SURROGATE_RE.search(fn_name):
                        fn["name"] = _SURROGATE_RE.sub("\ufffd", fn_name)
                        found = True
                    fn_args = fn.get("arguments")
                    if isinstance(fn_args, str) and _SURROGATE_RE.search(fn_args):
                        fn["arguments"] = _SURROGATE_RE.sub("\ufffd", fn_args)
                        found = True

        # Walk additional string/nested fields (reasoning, reasoning_content, etc.)
        for key, value in msg.items():
            if key in {"content", "name", "tool_calls", "role"}:
                continue
            if isinstance(value, str) and _SURROGATE_RE.search(value):
                msg[key] = _SURROGATE_RE.sub("\ufffd", value)
                found = True
            elif isinstance(value, (dict, list)):
                sanitize_structure_surrogates(value)

    return found


# ── Safe STDIO Wrapper ─────────────────────────────────────────────────────


class SafeWriter:
    """Wrap a stream so best-effort console output cannot crash the agent.

    Handles broken pipes when stdout/stderr is redirected to a closed pipe.
    """

    def __init__(self, inner):
        self._inner = inner

    def write(self, data):
        try:
            return self._inner.write(data)
        except (OSError, ValueError):
            pass

    def flush(self):
        with contextlib.suppress(OSError, ValueError):
            self._inner.flush()

    def fileno(self):
        return self._inner.fileno()

    def isatty(self):
        try:
            return self._inner.isatty()
        except (OSError, ValueError):
            return False

    def __getattr__(self, name):
        return getattr(self._inner, name)


def install_safe_stdio():
    """Wrap stdout/stderr so best-effort console output cannot crash the agent."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and not isinstance(stream, SafeWriter):
            setattr(sys, stream_name, SafeWriter(stream))


# ── Tool Result Storage ────────────────────────────────────────────────────


class ToolResultStorage:
    """Persistent storage for tool execution results."""

    def __init__(self, storage_dir: Path | None = None):
        self._storage_dir = storage_dir or Path.home() / ".prometheus" / "tool_results"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._turn_budget = 100
        self._current_turn = 0

    def persist_result(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any,
        turn: int | None = None,
    ) -> str | None:
        """Persist a tool result to disk.

        Returns the path to the stored result, or None if not stored.
        """
        if turn is None:
            turn = self._current_turn

        if turn > self._turn_budget:
            return None

        try:
            result_id = f"{tool_name}_{turn}_{int(time.time() * 1000)}"
            storage_path = self._storage_dir / f"{result_id}.json"

            payload = {
                "id": result_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
                "turn": turn,
                "timestamp": time.time(),
            }

            with open(storage_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            return str(storage_path)

        except Exception as e:
            logger.error(f"Failed to persist tool result: {e}")
            return None

    def enforce_turn_budget(self, turn: int) -> bool:
        """Check if the turn is within budget.

        Returns True if turns should be persisted, False otherwise.
        """
        return turn <= self._turn_budget

    def set_turn(self, turn: int):
        """Set the current turn number."""
        self._current_turn = turn

    def get_stored_result(self, result_id: str) -> dict[str, Any] | None:
        """Retrieve a stored result by ID."""
        storage_path = self._storage_dir / f"{result_id}.json"
        if not storage_path.exists():
            return None

        try:
            with open(storage_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load stored result: {e}")
            return None

    def cleanup_old_results(self, max_age_seconds: int = 86400):
        """Remove results older than max_age_seconds."""
        try:
            cutoff = time.time() - max_age_seconds
            for path in self._storage_dir.glob("*.json"):
                if path.stat().st_mtime < cutoff:
                    path.unlink()
        except Exception as e:
            logger.error(f"Failed to cleanup old results: {e}")


# Global storage instance
_tool_result_storage: ToolResultStorage | None = None


def get_tool_result_storage() -> ToolResultStorage:
    """Get the global tool result storage instance."""
    global _tool_result_storage
    if _tool_result_storage is None:
        _tool_result_storage = ToolResultStorage()
    return _tool_result_storage


def maybe_persist_tool_result(
    tool_name: str,
    arguments: dict[str, Any],
    result: Any,
    turn: int | None = None,
) -> str | None:
    """Persist a tool result if within budget.

    Returns the storage path or None.
    """
    storage = get_tool_result_storage()
    if not storage.enforce_turn_budget(turn or 0):
        return None
    return storage.persist_result(tool_name, arguments, result, turn)


def enforce_turn_budget(turn: int) -> bool:
    """Check if a turn should persist its results."""
    return get_tool_result_storage().enforce_turn_budget(turn)
