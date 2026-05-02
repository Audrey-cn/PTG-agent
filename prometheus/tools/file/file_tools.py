#!/usr/bin/env python3
"""File Tools Module - LLM agent file manipulation tools."""

from __future__ import annotations

import errno
import json
import logging
import os
import threading
from pathlib import Path

from prometheus.agent.redact import redact_sensitive_text
from prometheus.tools import file_state
from prometheus.tools.file.binary_extensions import has_binary_extension
from prometheus.tools.file.file_operations import (
    ShellFileOperations,
    normalize_read_pagination,
    normalize_search_pagination,
)

logger = logging.getLogger(__name__)


_EXPECTED_WRITE_ERRNOS = {errno.EACCES, errno.EPERM, errno.EROFS}

_DEFAULT_MAX_READ_CHARS = 100_000
_max_read_chars_cached: int | None = None


def _get_max_read_chars() -> int:
    global _max_read_chars_cached
    if _max_read_chars_cached is not None:
        return _max_read_chars_cached
    try:
        from prometheus.config import PrometheusConfig

        cfg = PrometheusConfig.load()
        val = cfg.get("file_read_max_chars")
        if isinstance(val, (int, float)) and val > 0:
            _max_read_chars_cached = int(val)
            return _max_read_chars_cached
    except Exception:
        pass
    _max_read_chars_cached = _DEFAULT_MAX_READ_CHARS
    return _max_read_chars_cached


_LARGE_FILE_HINT_BYTES = 512_000

_BLOCKED_DEVICE_PATHS = frozenset(
    {
        "/dev/zero",
        "/dev/random",
        "/dev/urandom",
        "/dev/full",
        "/dev/stdin",
        "/dev/tty",
        "/dev/console",
        "/dev/stdout",
        "/dev/stderr",
        "/dev/fd/0",
        "/dev/fd/1",
        "/dev/fd/2",
    }
)


def _resolve_path(filepath: str, task_id: str = "default") -> Path:
    return _resolve_path_for_task(filepath, task_id)


def _get_live_tracking_cwd(task_id: str = "default") -> str | None:
    try:
        from prometheus.tools.terminal_tool import _resolve_container_task_id

        container_key = _resolve_container_task_id(task_id)
    except Exception:
        container_key = task_id

    with _file_ops_lock:
        cached = _file_ops_cache.get(container_key) or _file_ops_cache.get(task_id)
    if cached is not None:
        live_cwd = getattr(getattr(cached, "env", None), "cwd", None) or getattr(
            cached, "cwd", None
        )
        if live_cwd:
            return live_cwd

    try:
        from prometheus.tools.terminal_tool import _active_environments, _env_lock

        with _env_lock:
            env = _active_environments.get(container_key) or _active_environments.get(task_id)
            live_cwd = getattr(env, "cwd", None) if env is not None else None
        if live_cwd:
            return live_cwd
    except Exception:
        pass

    return None


def _resolve_path_for_task(filepath: str, task_id: str = "default") -> Path:
    p = Path(filepath).expanduser()
    if not p.is_absolute():
        base = _get_live_tracking_cwd(task_id) or os.environ.get("TERMINAL_CWD", os.getcwd())
        p = Path(base) / p
    return p.resolve()


def _is_blocked_device(filepath: str) -> bool:
    normalized = os.path.expanduser(filepath)
    if normalized in _BLOCKED_DEVICE_PATHS:
        return True
    return bool(
        normalized.startswith("/proc/") and normalized.endswith(("/fd/0", "/fd/1", "/fd/2"))
    )


_SENSITIVE_PATH_PREFIXES = (
    "/etc/",
    "/boot/",
    "/usr/lib/systemd/",
    "/private/etc/",
    "/private/var/",
)
_SENSITIVE_EXACT_PATHS = {"/var/run/docker.sock", "/run/docker.sock"}


def _check_sensitive_path(filepath: str, task_id: str = "default") -> str | None:
    try:
        resolved = str(_resolve_path_for_task(filepath, task_id))
    except (OSError, ValueError):
        resolved = filepath
    normalized = os.path.normpath(os.path.expanduser(filepath))
    _err = (
        f"Refusing to write to sensitive system path: {filepath}\n"
        "Use the terminal tool with sudo if you need to modify system files."
    )
    for prefix in _SENSITIVE_PATH_PREFIXES:
        if resolved.startswith(prefix) or normalized.startswith(prefix):
            return _err
    if resolved in _SENSITIVE_EXACT_PATHS or normalized in _SENSITIVE_EXACT_PATHS:
        return _err
    return None


def _is_expected_write_exception(exc: Exception) -> bool:
    if isinstance(exc, PermissionError):
        return True
    return bool(isinstance(exc, OSError) and exc.errno in _EXPECTED_WRITE_ERRNOS)


_file_ops_lock = threading.Lock()
_file_ops_cache: dict = {}

_read_tracker_lock = threading.Lock()
_read_tracker: dict = {}

_READ_HISTORY_CAP = 500
_DEDUP_CAP = 1000
_READ_TIMESTAMPS_CAP = 1000
_READ_DEDUP_STATUS_MESSAGE = (
    "File unchanged since last read. The content from "
    "the earlier read_file result in this conversation is "
    "still current — refer to that instead of re-reading."
)


def _cap_read_tracker_data(task_data: dict) -> None:
    rh = task_data.get("read_history")
    if rh is not None and len(rh) > _READ_HISTORY_CAP:
        excess = len(rh) - _READ_HISTORY_CAP
        for _ in range(excess):
            try:
                rh.pop()
            except KeyError:
                break

    dedup = task_data.get("dedup")
    if dedup is not None and len(dedup) > _DEDUP_CAP:
        excess = len(dedup) - _DEDUP_CAP
        for _ in range(excess):
            try:
                dedup.pop(next(iter(dedup)))
            except (StopIteration, KeyError):
                break

    dedup_hits = task_data.get("dedup_hits")
    if dedup_hits is not None and len(dedup_hits) > _DEDUP_CAP:
        excess = len(dedup_hits) - _DEDUP_CAP
        for _ in range(excess):
            try:
                dedup_hits.pop(next(iter(dedup_hits)))
            except (StopIteration, KeyError):
                break

    ts = task_data.get("read_timestamps")
    if ts is not None and len(ts) > _READ_TIMESTAMPS_CAP:
        excess = len(ts) - _READ_TIMESTAMPS_CAP
        for _ in range(excess):
            try:
                ts.pop(next(iter(ts)))
            except (StopIteration, KeyError):
                break


def _is_internal_file_status_text(content: str) -> bool:
    if not isinstance(content, str):
        return False
    stripped = content.strip()
    if not stripped:
        return False
    if stripped == _READ_DEDUP_STATUS_MESSAGE:
        return True
    return bool(
        _READ_DEDUP_STATUS_MESSAGE in stripped
        and len(stripped) <= 2 * len(_READ_DEDUP_STATUS_MESSAGE)
    )


def _get_file_ops(task_id: str = "default") -> ShellFileOperations:
    import time

    from prometheus.tools.terminal_tool import (
        _active_environments,
        _create_environment,
        _creation_locks,
        _creation_locks_lock,
        _env_lock,
        _get_env_config,
        _last_activity,
        _resolve_container_task_id,
        _start_cleanup_thread,
    )

    task_id = _resolve_container_task_id(task_id)

    with _file_ops_lock:
        cached = _file_ops_cache.get(task_id)
    if cached is not None:
        with _env_lock:
            if task_id in _active_environments:
                _last_activity[task_id] = time.time()
                return cached
            else:
                with _file_ops_lock:
                    _file_ops_cache.pop(task_id, None)

    with _creation_locks_lock:
        if task_id not in _creation_locks:
            _creation_locks[task_id] = threading.Lock()
        task_lock = _creation_locks[task_id]

    with task_lock:
        with _env_lock:
            if task_id in _active_environments:
                _last_activity[task_id] = time.time()
                terminal_env = _active_environments[task_id]
            else:
                terminal_env = None

        if terminal_env is None:
            from prometheus.tools.terminal_tool import _task_env_overrides

            config = _get_env_config()
            env_type = config["env_type"]
            overrides = _task_env_overrides.get(task_id, {})

            if env_type == "docker":
                image = overrides.get("docker_image") or config["docker_image"]
            elif env_type == "singularity":
                image = overrides.get("singularity_image") or config["singularity_image"]
            elif env_type == "modal":
                image = overrides.get("modal_image") or config["modal_image"]
            elif env_type == "daytona":
                image = overrides.get("daytona_image") or config["daytona_image"]
            else:
                image = ""

            cwd = overrides.get("cwd") or config["cwd"]
            logger.info("Creating new %s environment for task %s...", env_type, task_id[:8])

            container_config = None
            if env_type in ("docker", "singularity", "modal", "daytona", "vercel_sandbox"):
                container_config = {
                    "container_cpu": config.get("container_cpu", 1),
                    "container_memory": config.get("container_memory", 5120),
                    "container_disk": config.get("container_disk", 51200),
                    "container_persistent": config.get("container_persistent", True),
                    "vercel_runtime": config.get("vercel_runtime", ""),
                    "docker_volumes": config.get("docker_volumes", []),
                    "docker_mount_cwd_to_workspace": config.get(
                        "docker_mount_cwd_to_workspace", False
                    ),
                    "docker_forward_env": config.get("docker_forward_env", []),
                    "docker_run_as_host_user": config.get("docker_run_as_host_user", False),
                }

            ssh_config = None
            if env_type == "ssh":
                ssh_config = {
                    "host": config.get("ssh_host", ""),
                    "user": config.get("ssh_user", ""),
                    "port": config.get("ssh_port", 22),
                    "key": config.get("ssh_key", ""),
                    "persistent": config.get("ssh_persistent", False),
                }

            local_config = None
            if env_type == "local":
                local_config = {
                    "persistent": config.get("local_persistent", False),
                }

            terminal_env = _create_environment(
                env_type=env_type,
                image=image,
                cwd=cwd,
                timeout=config["timeout"],
                ssh_config=ssh_config,
                container_config=container_config,
                local_config=local_config,
                task_id=task_id,
                host_cwd=config.get("host_cwd"),
            )

            with _env_lock:
                _active_environments[task_id] = terminal_env
                _last_activity[task_id] = time.time()

            _start_cleanup_thread()
            logger.info("%s environment ready for task %s", env_type, task_id[:8])

    file_ops = ShellFileOperations(terminal_env)
    with _file_ops_lock:
        _file_ops_cache[task_id] = file_ops
    return file_ops


def clear_file_ops_cache(task_id: str = None):
    with _file_ops_lock:
        if task_id:
            _file_ops_cache.pop(task_id, None)
        else:
            _file_ops_cache.clear()


def read_file_tool(path: str, offset: int = 1, limit: int = 500, task_id: str = "default") -> str:
    try:
        offset, limit = normalize_read_pagination(offset, limit)

        if _is_blocked_device(path):
            return json.dumps(
                {
                    "error": (
                        f"Cannot read '{path}': this is a device file that would "
                        "block or produce infinite output."
                    ),
                }
            )

        _resolved = _resolve_path_for_task(path, task_id)

        if has_binary_extension(str(_resolved)):
            _ext = _resolved.suffix.lower()
            return json.dumps(
                {
                    "error": (
                        f"Cannot read binary file '{path}' ({_ext}). "
                        "Use vision_analyze for images, or terminal to inspect binary files."
                    ),
                }
            )

        # Note: block error check removed - function not defined
        # block_error = _check_block_error(path)
        # if block_error:
        #     return json.dumps({"error": block_error})

        resolved_str = str(_resolved)
        dedup_key = (resolved_str, offset, limit)
        with _read_tracker_lock:
            task_data = _read_tracker.setdefault(
                task_id,
                {
                    "last_key": None,
                    "consecutive": 0,
                    "read_history": set(),
                    "dedup": {},
                    "dedup_hits": {},
                    "read_timestamps": {},
                },
            )
            if "dedup_hits" not in task_data:
                task_data["dedup_hits"] = {}
            if "read_timestamps" not in task_data:
                task_data["read_timestamps"] = {}
            cached_mtime = task_data.get("dedup", {}).get(dedup_key)

        if cached_mtime is not None:
            try:
                current_mtime = os.path.getmtime(resolved_str)
                if current_mtime == cached_mtime:
                    with _read_tracker_lock:
                        hits = task_data["dedup_hits"].get(dedup_key, 0) + 1
                        task_data["dedup_hits"][dedup_key] = hits
                        _cap_read_tracker_data(task_data)

                    if hits >= 2:
                        return json.dumps(
                            {
                                "error": (
                                    f"BLOCKED: You have called read_file on this "
                                    f"exact region {hits + 1} times and the file "
                                    "has NOT changed. STOP calling read_file for "
                                    "this path — the content from your earlier "
                                    "read_file result in this conversation is "
                                    "still current. Proceed with your task using "
                                    "the information you already have."
                                ),
                                "path": path,
                                "already_read": hits + 1,
                            },
                            ensure_ascii=False,
                        )

                    return json.dumps(
                        {
                            "status": "unchanged",
                            "message": _READ_DEDUP_STATUS_MESSAGE,
                            "path": path,
                            "dedup": True,
                            "content_returned": False,
                        },
                        ensure_ascii=False,
                    )
            except OSError:
                pass

        file_ops = _get_file_ops(task_id)
        result = file_ops.read_file(path, offset, limit)
        result_dict = result.to_dict()

        content_len = len(result.content or "")
        file_size = result_dict.get("file_size", 0)
        max_chars = _get_max_read_chars()
        if content_len > max_chars:
            total_lines = result_dict.get("total_lines", "unknown")
            return json.dumps(
                {
                    "error": (
                        f"Read produced {content_len:,} characters which exceeds "
                        f"the safety limit ({max_chars:,} chars). "
                        "Use offset and limit to read a smaller range. "
                        f"The file has {total_lines} lines total."
                    ),
                    "path": path,
                    "total_lines": total_lines,
                    "file_size": file_size,
                },
                ensure_ascii=False,
            )

        if result.content:
            result.content = redact_sensitive_text(result.content)
            result_dict["content"] = result.content

        if (
            file_size
            and file_size > _LARGE_FILE_HINT_BYTES
            and limit > 200
            and result_dict.get("truncated")
        ):
            result_dict.setdefault(
                "_hint",
                (
                    f"This file is large ({file_size:,} bytes). "
                    "Consider reading only the section you need with offset and limit "
                    "to keep context usage efficient."
                ),
            )

        read_key = ("read", path, offset, limit)
        with _read_tracker_lock:
            if "dedup" not in task_data:
                task_data["dedup"] = {}
            if "dedup_hits" not in task_data:
                task_data["dedup_hits"] = {}
            task_data["dedup_hits"].pop(dedup_key, None)
            task_data["read_history"].add((path, offset, limit))
            if task_data["last_key"] == read_key:
                task_data["consecutive"] += 1
            else:
                task_data["last_key"] = read_key
                task_data["consecutive"] = 1
            count = task_data["consecutive"]

            try:
                _mtime_now = os.path.getmtime(resolved_str)
                task_data["dedup"][dedup_key] = _mtime_now
                task_data.setdefault("read_timestamps", {})[resolved_str] = _mtime_now
            except OSError:
                pass

            _cap_read_tracker_data(task_data)

        try:
            _partial = (offset > 1) or bool(result_dict.get("truncated"))
            file_state.record_read(task_id, resolved_str, partial=_partial)
        except Exception:
            logger.debug("file_state.record_read failed", exc_info=True)

        if count >= 4:
            return json.dumps(
                {
                    "error": (
                        f"BLOCKED: You have read this exact file region {count} times in a row. "
                        "The content has NOT changed. You already have this information. "
                        "STOP re-reading and proceed with your task."
                    ),
                    "path": path,
                    "already_read": count,
                },
                ensure_ascii=False,
            )
        elif count >= 3:
            result_dict["_warning"] = (
                f"You have read this exact file region {count} times consecutively. "
                "The content has not changed since your last read. Use the information you already have. "
                "If you are stuck in a loop, stop reading and proceed with writing or responding."
            )

        return json.dumps(result_dict, ensure_ascii=False)
    except Exception as e:
        return tool_error(str(e))


def reset_file_dedup(task_id: str = None):
    with _read_tracker_lock:
        if task_id:
            task_data = _read_tracker.get(task_id)
            if task_data:
                if "dedup" in task_data:
                    task_data["dedup"].clear()
                if "dedup_hits" in task_data:
                    task_data["dedup_hits"].clear()
        else:
            for task_data in _read_tracker.values():
                if "dedup" in task_data:
                    task_data["dedup"].clear()
                if "dedup_hits" in task_data:
                    task_data["dedup_hits"].clear()


def notify_other_tool_call(task_id: str = "default"):
    with _read_tracker_lock:
        task_data = _read_tracker.get(task_id)
        if task_data:
            task_data["last_key"] = None
            task_data["consecutive"] = 0
            if "dedup_hits" in task_data:
                task_data["dedup_hits"].clear()


def _invalidate_dedup_for_path(filepath: str, task_id: str) -> None:
    try:
        resolved = str(_resolve_path(filepath))
    except (OSError, ValueError):
        return
    with _read_tracker_lock:
        task_data = _read_tracker.get(task_id)
        if task_data is None:
            return
        dedup = task_data.get("dedup")
        if not dedup:
            return
        stale_keys = [k for k in dedup if k[0] == resolved]
        for k in stale_keys:
            del dedup[k]


def _update_read_timestamp(filepath: str, task_id: str) -> None:
    _invalidate_dedup_for_path(filepath, task_id)
    try:
        resolved = str(_resolve_path_for_task(filepath, task_id))
        current_mtime = os.path.getmtime(resolved)
    except (OSError, ValueError):
        return
    with _read_tracker_lock:
        task_data = _read_tracker.get(task_id)
        if task_data is not None:
            task_data.setdefault("read_timestamps", {})[resolved] = current_mtime
            _cap_read_tracker_data(task_data)


def _check_file_staleness(filepath: str, task_id: str) -> str | None:
    try:
        resolved = str(_resolve_path_for_task(filepath, task_id))
    except (OSError, ValueError):
        return None
    with _read_tracker_lock:
        task_data = _read_tracker.get(task_id)
        if not task_data:
            return None
        read_mtime = task_data.get("read_timestamps", {}).get(resolved)
    if read_mtime is None:
        return None
    try:
        current_mtime = os.path.getmtime(resolved)
    except OSError:
        return None
    if current_mtime != read_mtime:
        return (
            f"Warning: {filepath} was modified since you last read it "
            "(external edit or concurrent agent). The content you read may be "
            "stale. Consider re-reading the file to verify before writing."
        )
    return None


def write_file_tool(path: str, content: str, task_id: str = "default") -> str:
    sensitive_err = _check_sensitive_path(path, task_id)
    if sensitive_err:
        return tool_error(sensitive_err)
    if _is_internal_file_status_text(content):
        return tool_error(
            "Refusing to write internal read_file status text as file content. "
            "Re-read the file or reconstruct the intended file contents before writing."
        )
    try:
        try:
            _resolved = str(_resolve_path_for_task(path, task_id))
        except Exception:
            _resolved = None

        if _resolved is None:
            stale_warning = _check_file_staleness(path, task_id)
            file_ops = _get_file_ops(task_id)
            result = file_ops.write_file(path, content)
            result_dict = result.to_dict()
            if stale_warning:
                result_dict["_warning"] = stale_warning
            _update_read_timestamp(path, task_id)
            return json.dumps(result_dict, ensure_ascii=False)

        with file_state.lock_path(_resolved):
            cross_warning = file_state.check_stale(task_id, _resolved)
            stale_warning = _check_file_staleness(path, task_id)
            file_ops = _get_file_ops(task_id)
            result = file_ops.write_file(path, content)
            result_dict = result.to_dict()
            effective_warning = cross_warning or stale_warning
            if effective_warning:
                result_dict["_warning"] = effective_warning
            _update_read_timestamp(path, task_id)
            if not result_dict.get("error"):
                file_state.note_write(task_id, _resolved)
        return json.dumps(result_dict, ensure_ascii=False)
    except Exception as e:
        if _is_expected_write_exception(e):
            logger.debug("write_file expected denial: %s: %s", type(e).__name__, e)
        else:
            logger.error("write_file error: %s: %s", type(e).__name__, e, exc_info=True)
        return tool_error(str(e))


def patch_tool(
    mode: str = "replace",
    path: str = None,
    old_string: str = None,
    new_string: str = None,
    replace_all: bool = False,
    patch: str = None,
    task_id: str = "default",
) -> str:
    _paths_to_check = []
    if path:
        _paths_to_check.append(path)
    if mode == "patch" and patch:
        import re as _re

        for _m in _re.finditer(
            r"^\*\*\*\s+(?:Update|Add|Delete)\s+File:\s*(.+)$", patch, _re.MULTILINE
        ):
            _paths_to_check.append(_m.group(1).strip())
    for _p in _paths_to_check:
        sensitive_err = _check_sensitive_path(_p, task_id)
        if sensitive_err:
            return tool_error(sensitive_err)
    try:
        _resolved_paths: list[str] = []
        _seen: Set[str] = set()
        for _p in _paths_to_check:
            try:
                _r = str(_resolve_path_for_task(_p, task_id))
            except Exception:
                _r = None
            if _r and _r not in _seen:
                _resolved_paths.append(_r)
                _seen.add(_r)
        _resolved_paths.sort()

        from contextlib import ExitStack

        with ExitStack() as _locks:
            for _r in _resolved_paths:
                _locks.enter_context(file_state.lock_path(_r))

            stale_warnings: list[str] = []
            _path_to_resolved: dict[str, str] = {}
            for _p in _paths_to_check:
                try:
                    _r = str(_resolve_path_for_task(_p, task_id))
                except Exception:
                    _r = None
                _path_to_resolved[_p] = _r
                _cross = file_state.check_stale(task_id, _r) if _r else None
                _sw = _cross or _check_file_staleness(_p, task_id)
                if _sw:
                    stale_warnings.append(_sw)

            file_ops = _get_file_ops(task_id)

            if mode == "replace":
                if not path:
                    return tool_error("path required")
                if old_string is None or new_string is None:
                    return tool_error("old_string and new_string required")
                result = file_ops.patch_replace(path, old_string, new_string, replace_all)
            elif mode == "patch":
                if not patch:
                    return tool_error("patch content required")
                result = file_ops.patch_v4a(patch)
            else:
                return tool_error(f"Unknown mode: {mode}")

            result_dict = result.to_dict()
            if stale_warnings:
                result_dict["_warning"] = (
                    stale_warnings[0] if len(stale_warnings) == 1 else " | ".join(stale_warnings)
                )
            if not result_dict.get("error"):
                for _p in _paths_to_check:
                    _update_read_timestamp(_p, task_id)
                    _r = _path_to_resolved.get(_p)
                    if _r:
                        file_state.note_write(task_id, _r)
        if result_dict.get("error") and "Could not find" in str(result_dict["error"]):
            if "Did you mean one of these sections?" not in str(result_dict["error"]):
                result_dict["_hint"] = (
                    "old_string not found. Use read_file to verify the current "
                    "content, or search_files to locate the text."
                )
        return json.dumps(result_dict, ensure_ascii=False)
    except Exception as e:
        return tool_error(str(e))


def search_tool(
    pattern: str,
    target: str = "content",
    path: str = ".",
    file_glob: str = None,
    limit: int = 50,
    offset: int = 0,
    output_mode: str = "content",
    context: int = 0,
    task_id: str = "default",
) -> str:
    try:
        offset, limit = normalize_search_pagination(offset, limit)

        search_key = (
            "search",
            pattern,
            target,
            str(path),
            file_glob or "",
            limit,
            offset,
        )
        with _read_tracker_lock:
            task_data = _read_tracker.setdefault(
                task_id,
                {
                    "last_key": None,
                    "consecutive": 0,
                    "read_history": set(),
                },
            )
            if task_data["last_key"] == search_key:
                task_data["consecutive"] += 1
            else:
                task_data["last_key"] = search_key
                task_data["consecutive"] = 1
            count = task_data["consecutive"]

        if count >= 4:
            return json.dumps(
                {
                    "error": (
                        f"BLOCKED: You have run this exact search {count} times in a row. "
                        "The results have NOT changed. You already have this information. "
                        "STOP re-searching and proceed with your task."
                    ),
                    "pattern": pattern,
                    "already_searched": count,
                },
                ensure_ascii=False,
            )

        file_ops = _get_file_ops(task_id)
        result = file_ops.search(
            pattern=pattern,
            path=path,
            target=target,
            file_glob=file_glob,
            limit=limit,
            offset=offset,
            output_mode=output_mode,
            context=context,
        )
        if hasattr(result, "matches"):
            for m in result.matches:
                if hasattr(m, "content") and m.content:
                    m.content = redact_sensitive_text(m.content)
        result_dict = result.to_dict()

        if count >= 3:
            result_dict["_warning"] = (
                f"You have run this exact search {count} times consecutively. "
                "The results have not changed. Use the information you already have."
            )

        result_json = json.dumps(result_dict, ensure_ascii=False)
        if result_dict.get("truncated"):
            next_offset = offset + limit
            result_json += f"\n\n[Hint: Results truncated. Use offset={next_offset} to see more, or narrow with a more specific pattern or file_glob.]"
        return result_json
    except Exception as e:
        return tool_error(str(e))


from prometheus.tools.security.registry import registry, tool_error


def _check_file_reqs():
    from tools import check_file_requirements

    return check_file_requirements()


READ_FILE_SCHEMA = {
    "name": "read_file",
    "description": "Read a text file with line numbers and pagination. Use this instead of cat/head/tail in terminal. Output format: 'LINE_NUM|CONTENT'. Suggests similar filenames if not found. Use offset and limit for large files. Reads exceeding ~100K characters are rejected; use offset and limit to read specific sections of large files. NOTE: Cannot read images or binary files — use vision_analyze for images.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read (absolute, relative, or ~/path)",
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (1-indexed, default: 1)",
                "default": 1,
                "minimum": 1,
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read (default: 500, max: 2000)",
                "default": 500,
                "maximum": 2000,
            },
        },
        "required": ["path"],
    },
}

WRITE_FILE_SCHEMA = {
    "name": "write_file",
    "description": "Write content to a file, completely replacing existing content. Use this instead of echo/cat heredoc in terminal. Creates parent directories automatically. OVERWRITES the entire file — use 'patch' for targeted edits.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write (will be created if it doesn't exist, overwritten if it does)",
            },
            "content": {"type": "string", "description": "Complete content to write to the file"},
        },
        "required": ["path", "content"],
    },
}

PATCH_SCHEMA = {
    "name": "patch",
    "description": "Targeted find-and-replace edits in files. Use this instead of sed/awk in terminal. Uses fuzzy matching (9 strategies) so minor whitespace/indentation differences won't break it. Returns a unified diff. Auto-runs syntax checks after editing.\n\nReplace mode (default): find a unique string and replace it.\nPatch mode: apply V4A multi-file patches for bulk changes.",
    "parameters": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["replace", "patch"],
                "description": "Edit mode: 'replace' for targeted find-and-replace, 'patch' for V4A multi-file patches",
                "default": "replace",
            },
            "path": {
                "type": "string",
                "description": "File path to edit (required for 'replace' mode)",
            },
            "old_string": {
                "type": "string",
                "description": "Text to find in the file (required for 'replace' mode). Must be unique in the file unless replace_all=true. Include enough surrounding context to ensure uniqueness.",
            },
            "new_string": {
                "type": "string",
                "description": "Replacement text (required for 'replace' mode). Can be empty string to delete the matched text.",
            },
            "replace_all": {
                "type": "boolean",
                "description": "Replace all occurrences instead of requiring a unique match (default: false)",
                "default": False,
            },
            "patch": {
                "type": "string",
                "description": "V4A format patch content (required for 'patch' mode). Format:\n*** Begin Patch\n*** Update File: path/to/file\n@@ context hint @@\n context line\n-removed line\n+added line\n*** End Patch",
            },
        },
        "required": ["mode"],
    },
}

SEARCH_FILES_SCHEMA = {
    "name": "search_files",
    "description": "Search file contents or find files by name. Use this instead of grep/rg/find/ls in terminal. Ripgrep-backed, faster than shell equivalents.\n\nContent search (target='content'): Regex search inside files. Output modes: full matches with line numbers, file paths only, or match counts.\n\nFile search (target='files'): Find files by glob pattern (e.g., '*.py', '*config*'). Also use this instead of ls — results sorted by modification time.",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regex pattern for content search, or glob pattern (e.g., '*.py') for file search",
            },
            "target": {
                "type": "string",
                "enum": ["content", "files"],
                "description": "'content' searches inside file contents, 'files' searches for files by name",
                "default": "content",
            },
            "path": {
                "type": "string",
                "description": "Directory or file to search in (default: current working directory)",
                "default": ".",
            },
            "file_glob": {
                "type": "string",
                "description": "Filter files by pattern in grep mode (e.g., '*.py' to only search Python files)",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 50)",
                "default": 50,
            },
            "offset": {
                "type": "integer",
                "description": "Skip first N results for pagination (default: 0)",
                "default": 0,
            },
            "output_mode": {
                "type": "string",
                "enum": ["content", "files_only", "count"],
                "description": "Output format for grep mode: 'content' shows matching lines with line numbers, 'files_only' lists file paths, 'count' shows match counts per file",
                "default": "content",
            },
            "context": {
                "type": "integer",
                "description": "Number of context lines before and after each match (grep mode only)",
                "default": 0,
            },
        },
        "required": ["pattern"],
    },
}


def _handle_read_file(args, **kw):
    tid = kw.get("task_id") or "default"
    return read_file_tool(
        path=args.get("path", ""),
        offset=args.get("offset", 1),
        limit=args.get("limit", 500),
        task_id=tid,
    )


def _handle_write_file(args, **kw):
    tid = kw.get("task_id") or "default"
    return write_file_tool(path=args.get("path", ""), content=args.get("content", ""), task_id=tid)


def _handle_patch(args, **kw):
    tid = kw.get("task_id") or "default"
    return patch_tool(
        mode=args.get("mode", "replace"),
        path=args.get("path"),
        old_string=args.get("old_string"),
        new_string=args.get("new_string"),
        replace_all=args.get("replace_all", False),
        patch=args.get("patch"),
        task_id=tid,
    )


def _handle_search_files(args, **kw):
    tid = kw.get("task_id") or "default"
    target_map = {"grep": "content", "find": "files"}
    raw_target = args.get("target", "content")
    target = target_map.get(raw_target, raw_target)
    return search_tool(
        pattern=args.get("pattern", ""),
        target=target,
        path=args.get("path", "."),
        file_glob=args.get("file_glob"),
        limit=args.get("limit", 50),
        offset=args.get("offset", 0),
        output_mode=args.get("output_mode", "content"),
        context=args.get("context", 0),
        task_id=tid,
    )


registry.register(
    name="read_file",
    toolset="file",
    schema=READ_FILE_SCHEMA,
    handler=_handle_read_file,
    check_fn=_check_file_reqs,
    emoji="📖",
    max_result_size_chars=float("inf"),
)
registry.register(
    name="write_file",
    toolset="file",
    schema=WRITE_FILE_SCHEMA,
    handler=_handle_write_file,
    check_fn=_check_file_reqs,
    emoji="✍️",
    max_result_size_chars=100_000,
)
registry.register(
    name="patch",
    toolset="file",
    schema=PATCH_SCHEMA,
    handler=_handle_patch,
    check_fn=_check_file_reqs,
    emoji="🔧",
    max_result_size_chars=100_000,
)
registry.register(
    name="search_files",
    toolset="file",
    schema=SEARCH_FILES_SCHEMA,
    handler=_handle_search_files,
    check_fn=_check_file_reqs,
    emoji="🔎",
    max_result_size_chars=100_000,
)
