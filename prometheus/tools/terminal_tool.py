from __future__ import annotations

#!/usr/bin/env python3
"""Terminal Tool Module."""

import atexit
import importlib.util
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


from prometheus.tools.environments.singularity import _get_scratch_dir
from prometheus.tools.security.interrupt import _interrupt_event, is_interrupted  # noqa: F401 — re-exported
from prometheus.tools.security.tool_backend_helpers import (
    coerce_modal_mode,
    has_direct_modal_credentials,
    managed_nous_tools_enabled,
    resolve_modal_backend_state,
)


def _safe_parse_import_env(
    name: str,
    default: Any,
    converter,
    type_label: str,
):
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return converter(raw)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid value for %s: %r (expected %s). Falling back to %r.",
            name,
            raw,
            type_label,
            default,
        )
        return default


FOREGROUND_MAX_TIMEOUT = _safe_parse_import_env(
    "TERMINAL_MAX_FOREGROUND_TIMEOUT",
    600,
    int,
    "integer",
)

DISK_USAGE_WARNING_THRESHOLD_GB = _safe_parse_import_env(
    "TERMINAL_DISK_WARNING_GB",
    500.0,
    float,
    "number",
)
_VERCEL_SANDBOX_DEFAULT_CWD = "/vercel/sandbox"
_SUPPORTED_VERCEL_RUNTIMES = ("node24", "node22", "python3.13")


def _is_supported_vercel_runtime(runtime: str) -> bool:
    return not runtime or runtime in _SUPPORTED_VERCEL_RUNTIMES


def _check_vercel_sandbox_requirements(config: dict[str, Any]) -> bool:
    runtime = (config.get("vercel_runtime") or "").strip()
    if not _is_supported_vercel_runtime(runtime):
        supported = ", ".join(_SUPPORTED_VERCEL_RUNTIMES)
        logger.error(
            "Vercel Sandbox runtime %r is not supported. "
            "Set TERMINAL_VERCEL_RUNTIME to one of: %s.",
            runtime,
            supported,
        )
        return False

    disk = config.get("container_disk", 51200)
    if disk not in (0, 51200):
        logger.error(
            "Vercel Sandbox does not support custom TERMINAL_CONTAINER_DISK=%s. "
            "Use the default shared setting (51200 MB).",
            disk,
        )
        return False

    if importlib.util.find_spec("vercel") is None:
        logger.error(
            "vercel is required for the Vercel Sandbox terminal backend: pip install vercel"
        )
        return False

    has_oidc = bool(os.getenv("VERCEL_OIDC_TOKEN"))
    has_token = bool(os.getenv("VERCEL_TOKEN"))
    has_project = bool(os.getenv("VERCEL_PROJECT_ID"))
    has_team = bool(os.getenv("VERCEL_TEAM_ID"))

    if has_oidc:
        return True

    if has_token or has_project or has_team:
        if has_token and has_project and has_team:
            return True
        logger.error(
            "Vercel Sandbox backend selected with token auth, but "
            "VERCEL_TOKEN, VERCEL_PROJECT_ID, and VERCEL_TEAM_ID must all "
            "be set together. VERCEL_OIDC_TOKEN is supported for one-off "
            "local development only."
        )
        return False

    logger.error(
        "Vercel Sandbox backend selected but no supported auth configuration "
        "was found. Set VERCEL_TOKEN, VERCEL_PROJECT_ID, and VERCEL_TEAM_ID "
        "for normal use. VERCEL_OIDC_TOKEN is supported for one-off local "
        "development only."
    )
    return False


def _check_disk_usage_warning():
    try:
        scratch_dir = _get_scratch_dir()

        total_bytes = 0
        import glob

        for path in glob.glob(str(scratch_dir / "prometheus-*")):
            for f in Path(path).rglob("*"):
                if f.is_file():
                    try:
                        total_bytes += f.stat().st_size
                    except OSError as e:
                        logger.debug("Could not stat file %s: %s", f, e)

        total_gb = total_bytes / (1024**3)

        if total_gb > DISK_USAGE_WARNING_THRESHOLD_GB:
            logger.warning(
                "Disk usage (%.1fGB) exceeds threshold (%.0fGB). Consider running cleanup_all_environments().",
                total_gb,
                DISK_USAGE_WARNING_THRESHOLD_GB,
            )
            return True

        return False
    except Exception as e:
        logger.debug("Disk usage warning check failed: %s", e, exc_info=True)
        return False


_sudo_password_cache: dict[str, str] = {}
_sudo_password_cache_lock = threading.Lock()

import threading

_callback_tls = threading.local()


def _get_sudo_password_callback():
    return getattr(_callback_tls, "sudo_password", None)


def _get_approval_callback():
    return getattr(_callback_tls, "approval", None)


def set_sudo_password_callback(cb):
    _callback_tls.sudo_password = cb


def set_approval_callback(cb):
    _callback_tls.approval = cb


def _get_sudo_password_cache_scope() -> str:
    try:
        from prometheus.gateway.session_context import get_session_env

        session_key = get_session_env("PROMETHEUS_SESSION_KEY", "")
    except Exception:
        session_key = os.getenv("PROMETHEUS_SESSION_KEY", "")
    if session_key:
        return f"session:{session_key}"

    callback = _get_sudo_password_callback()
    if callback is not None:
        owner = getattr(callback, "__self__", None)
        func = getattr(callback, "__func__", None)
        if owner is not None and func is not None:
            return f"callback-owner:{id(owner)}:{id(func)}"
        return f"callback:{id(callback)}"

    return f"thread:{threading.get_ident()}"


def _get_cached_sudo_password() -> str:
    scope = _get_sudo_password_cache_scope()
    with _sudo_password_cache_lock:
        return _sudo_password_cache.get(scope, "")


def _set_cached_sudo_password(password: str) -> None:
    scope = _get_sudo_password_cache_scope()
    with _sudo_password_cache_lock:
        if password:
            _sudo_password_cache[scope] = password
        else:
            _sudo_password_cache.pop(scope, None)


def _reset_cached_sudo_passwords() -> None:
    with _sudo_password_cache_lock:
        _sudo_password_cache.clear()


from prometheus.tools.security.approval import (
    check_all_command_guards as _check_all_guards_impl,
)


def _check_all_guards(command: str, env_type: str) -> dict:
    return _check_all_guards_impl(command, env_type, approval_callback=_get_approval_callback())


_WORKDIR_SAFE_RE = re.compile(r"^[A-Za-z0-9/\\:_\-.~ +@=,]+$")


def _validate_workdir(workdir: str) -> str | None:
    if not workdir:
        return None
    if not _WORKDIR_SAFE_RE.match(workdir):
        for ch in workdir:
            if not _WORKDIR_SAFE_RE.match(ch):
                return (
                    f"Blocked: workdir contains disallowed character {repr(ch)}. "
                    "Use a simple filesystem path without shell metacharacters."
                )
        return "Blocked: workdir contains disallowed characters."
    return None


def _handle_sudo_failure(output: str, env_type: str) -> str:
    is_gateway = os.getenv("PROMETHEUS_GATEWAY_SESSION")

    if not is_gateway:
        return output

    sudo_failures = [
        "sudo: a password is required",
        "sudo: no tty present",
        "sudo: a terminal is required",
    ]

    for failure in sudo_failures:
        if failure in output:
            from prometheus.constants_core import display_prometheus_home as _dhh

            return (
                output
                + f"\n\nTip: To enable sudo over messaging, add SUDO_PASSWORD to {_dhh()}/.env on the agent machine."
            )

    return output


def _prompt_for_sudo_password(timeout_seconds: int = 45) -> str:
    import sys

    _sudo_cb = _get_sudo_password_callback()
    if _sudo_cb is not None:
        try:
            return _sudo_cb() or ""
        except Exception:
            return ""

    result = {"password": None, "done": False}

    def read_password_thread():
        tty_fd = None
        old_attrs = None
        try:
            if platform.system() == "Windows":
                import msvcrt

                chars = []
                while True:
                    c = msvcrt.getwch()
                    if c in ("\r", "\n"):
                        break
                    if c == "\x03":
                        raise KeyboardInterrupt
                    chars.append(c)
                result["password"] = "".join(chars)
            else:
                import termios

                tty_fd = os.open("/dev/tty", os.O_RDONLY)
                old_attrs = termios.tcgetattr(tty_fd)
                new_attrs = termios.tcgetattr(tty_fd)
                new_attrs[3] = new_attrs[3] & ~termios.ECHO
                termios.tcsetattr(tty_fd, termios.TCSAFLUSH, new_attrs)
                chars = []
                while True:
                    b = os.read(tty_fd, 1)
                    if not b or b in (b"\n", b"\r"):
                        break
                    chars.append(b)
                result["password"] = b"".join(chars).decode("utf-8", errors="replace")
        except (EOFError, KeyboardInterrupt, OSError):
            result["password"] = ""
        except Exception:
            result["password"] = ""
        finally:
            if tty_fd is not None and old_attrs is not None:
                try:
                    import termios as _termios

                    _termios.tcsetattr(tty_fd, _termios.TCSAFLUSH, old_attrs)
                except Exception as e:
                    logger.debug("Failed to restore terminal attributes: %s", e)
            if tty_fd is not None:
                try:
                    os.close(tty_fd)
                except Exception as e:
                    logger.debug("Failed to close tty fd: %s", e)
            result["done"] = True

    try:
        os.environ["PROMETHEUS_SPINNER_PAUSE"] = "1"
        time.sleep(0.2)

        print()
        print("+" + "-" * 58 + "+")
        print("|  SUDO PASSWORD REQUIRED" + " " * 30 + "|")
        print("+" + "-" * 58 + "+")
        print("|  Enter password below (input is hidden), or:            |")
        print("|    - Press Enter to skip (command fails gracefully)     |")
        print(f"|    - Wait {timeout_seconds}s to auto-skip" + " " * 27 + "|")
        print("+" + "-" * 58 + "+")
        print()
        print("  Password (hidden): ", end="", flush=True)

        password_thread = threading.Thread(target=read_password_thread, daemon=True)
        password_thread.start()
        password_thread.join(timeout=timeout_seconds)

        if result["done"]:
            password = result["password"] or ""
            print()
            if password:
                print("  Password received (cached for this session)")
            else:
                print("  Skipped - continuing without sudo")
            print()
            sys.stdout.flush()
            return password
        else:
            print("\n  Timeout - continuing without sudo")
            print("    (Press Enter to dismiss)")
            print()
            sys.stdout.flush()
            return ""

    except (EOFError, KeyboardInterrupt):
        print()
        print("  Cancelled - continuing without sudo")
        print()
        sys.stdout.flush()
        return ""
    except Exception as e:
        print(f"\n  [sudo prompt error: {e}] - continuing without sudo\n")
        sys.stdout.flush()
        return ""
    finally:
        if "PROMETHEUS_SPINNER_PAUSE" in os.environ:
            del os.environ["PROMETHEUS_SPINNER_PAUSE"]


def _safe_command_preview(command: Any, limit: int = 200) -> str:
    if command is None:
        return "<None>"
    if isinstance(command, str):
        return command[:limit]
    try:
        return repr(command)[:limit]
    except Exception:
        return f"<{type(command).__name__}>"


def _looks_like_env_assignment(token: str) -> bool:
    if "=" not in token or token.startswith("="):
        return False
    name, _value = token.split("=", 1)
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name))


def _read_shell_token(command: str, start: int) -> Tuple[str, int]:
    i = start
    n = len(command)

    while i < n:
        ch = command[i]
        if ch.isspace() or ch in ";|&()":
            break
        if ch == "'":
            i += 1
            while i < n and command[i] != "'":
                i += 1
            if i < n:
                i += 1
            continue
        if ch == '"':
            i += 1
            while i < n:
                inner = command[i]
                if inner == "\\" and i + 1 < n:
                    i += 2
                    continue
                if inner == '"':
                    i += 1
                    break
                i += 1
            continue
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        i += 1

    return command[start:i], i


def _rewrite_real_sudo_invocations(command: str) -> Tuple[str, bool]:
    out: list[str] = []
    i = 0
    n = len(command)
    command_start = True
    found = False

    while i < n:
        ch = command[i]

        if ch.isspace():
            out.append(ch)
            if ch == "\n":
                command_start = True
            i += 1
            continue

        if ch == "#" and command_start:
            comment_end = command.find("\n", i)
            if comment_end == -1:
                out.append(command[i:])
                break
            out.append(command[i:comment_end])
            i = comment_end
            continue

        if (
            command.startswith("&&", i)
            or command.startswith("||", i)
            or command.startswith(";;", i)
        ):
            out.append(command[i : i + 2])
            i += 2
            command_start = True
            continue

        if ch in ";|&(":
            out.append(ch)
            i += 1
            command_start = True
            continue

        if ch == ")":
            out.append(ch)
            i += 1
            command_start = False
            continue

        token, next_i = _read_shell_token(command, i)
        if command_start and token == "sudo":
            out.append("sudo -S -p ''")
            found = True
        else:
            out.append(token)

        if command_start and _looks_like_env_assignment(token):
            command_start = True
        else:
            command_start = False
        i = next_i

    return "".join(out), found


def _rewrite_compound_background(command: str) -> str:
    n = len(command)
    i = 0
    paren_depth = 0
    brace_depth = 0
    last_chain_op_end = -1
    rewrites: list[Tuple[int, int]] = []

    while i < n:
        ch = command[i]

        if ch == "\n" and paren_depth == 0 and brace_depth == 0:
            last_chain_op_end = -1
            i += 1
            continue

        if ch.isspace():
            i += 1
            continue

        if ch == "#":
            nl = command.find("\n", i)
            if nl == -1:
                break
            i = nl
            continue

        if ch == "\\" and i + 1 < n:
            i += 2
            continue

        if ch in ("'", '"'):
            _, next_i = _read_shell_token(command, i)
            i = max(next_i, i + 1)
            continue

        if ch == "(":
            paren_depth += 1
            i += 1
            continue

        if ch == ")":
            paren_depth = max(0, paren_depth - 1)
            i += 1
            continue

        if ch == "{" and i + 1 < n and (command[i + 1].isspace() or command[i + 1] == "\n"):
            brace_depth += 1
            i += 1
            continue
        if ch == "}" and brace_depth > 0:
            brace_depth -= 1
            last_chain_op_end = -1
            i += 1
            continue

        if paren_depth > 0 or brace_depth > 0:
            i += 1
            continue

        if command.startswith("&&", i) or command.startswith("||", i):
            last_chain_op_end = i + 2
            i += 2
            continue

        if ch == ";":
            last_chain_op_end = -1
            i += 1
            continue

        if ch == "|":
            last_chain_op_end = -1
            i += 1
            continue

        if ch == "&":
            if i + 1 < n and command[i + 1] == ">":
                i += 2
                continue
            j = i - 1
            while j >= 0 and command[j].isspace():
                j -= 1
            if j >= 0 and command[j] in "<>":
                i += 1
                continue
            if last_chain_op_end >= 0:
                rewrites.append((last_chain_op_end, i))
            last_chain_op_end = -1
            i += 1
            continue

        _, next_i = _read_shell_token(command, i)
        i = max(next_i, i + 1)

    if not rewrites:
        return command

    result = command
    for chain_end, amp_pos in reversed(rewrites):
        insert_pos = chain_end
        while insert_pos < amp_pos and result[insert_pos].isspace():
            insert_pos += 1
        prefix = result[:insert_pos]
        middle = result[insert_pos:amp_pos]
        suffix = result[amp_pos + 1 :]
        result = prefix + "{ " + middle + "& }" + suffix

    return result


def _transform_sudo_command(command: str | None) -> Tuple[str | None, str | None]:
    if command is None:
        return None, None
    transformed, has_real_sudo = _rewrite_real_sudo_invocations(command)
    if not has_real_sudo:
        return command, None

    has_configured_password = "SUDO_PASSWORD" in os.environ
    sudo_password = (
        os.environ.get("SUDO_PASSWORD", "")
        if has_configured_password
        else _get_cached_sudo_password()
    )

    if not has_configured_password and not sudo_password and os.getenv("PROMETHEUS_INTERACTIVE"):
        sudo_password = _prompt_for_sudo_password(timeout_seconds=45)
        if sudo_password:
            _set_cached_sudo_password(sudo_password)

    if has_configured_password or sudo_password:
        return transformed, sudo_password + "\n"

    return command, None


import contextlib

from prometheus.tools.environments.docker import DockerEnvironment as _DockerEnvironment
from prometheus.tools.environments.local import LocalEnvironment as _LocalEnvironment
from prometheus.tools.environments.managed_modal import (
    ManagedModalEnvironment as _ManagedModalEnvironment,
)
from prometheus.tools.environments.modal import ModalEnvironment as _ModalEnvironment
from prometheus.tools.environments.singularity import (
    SingularityEnvironment as _SingularityEnvironment,
)
from prometheus.tools.environments.ssh import SSHEnvironment as _SSHEnvironment
from prometheus.tools.managed_tool_gateway import is_managed_tool_gateway_ready

TERMINAL_TOOL_DESCRIPTION = """Execute shell commands on a Linux environment. Filesystem usually persists between calls.

Do NOT use cat/head/tail to read files — use read_file instead.
Do NOT use grep/rg/find to search — use search_files instead.
Do NOT use ls to list directories — use search_files(target='files') instead.
Do NOT use sed/awk to edit files — use patch instead.
Do NOT use echo/cat heredoc to create files — use write_file instead.
Reserve terminal for: builds, installs, git, processes, scripts, network, package managers, and anything that needs a shell.

Foreground (default): Commands return INSTANTLY when done, even if the timeout is high. Set timeout=300 for long builds/scripts — you'll still get the result in seconds if it's fast. Prefer foreground for short commands.
Background: Set background=true to get a session_id. Two patterns:
  (1) Long-lived processes that never exit (servers, watchers).
  (2) Long-running tasks with notify_on_complete=true — you can keep working on other things and the system auto-notifies you when the task finishes. Great for test suites, builds, deployments, or anything that takes more than a minute.
For servers/watchers, do NOT use shell-level background wrappers (nohup/disown/setsid/trailing '&') in foreground mode. Use background=true so Prometheus can track lifecycle and output.
After starting a server, verify readiness with a health check or log signal, then run tests in a separate terminal() call. Avoid blind sleep loops.
Use process(action="poll") for progress checks, process(action="wait") to block until done.
Working directory: Use 'workdir' for per-command cwd.
PTY mode: Set pty=true for interactive CLI tools (Codex, Claude Code, Python REPL).

Do NOT use vim/nano/interactive tools without pty=true — they hang without a pseudo-terminal. Pipe git output to cat if it might page.
"""

_active_environments: dict[str, Any] = {}
_last_activity: dict[str, float] = {}
_env_lock = threading.Lock()
_creation_locks: dict[str, threading.Lock] = {}
_creation_locks_lock = threading.Lock()
_cleanup_thread = None
_cleanup_running = False

_task_env_overrides: dict[str, dict[str, Any]] = {}


def register_task_env_overrides(task_id: str, overrides: dict[str, Any]):
    _task_env_overrides[task_id] = overrides


def clear_task_env_overrides(task_id: str):
    _task_env_overrides.pop(task_id, None)


def _resolve_container_task_id(task_id: str | None) -> str:
    if task_id and task_id in _task_env_overrides:
        return task_id
    return "default"


def _parse_env_var(name: str, default: str, converter=int, type_label: str = "integer"):
    raw = os.getenv(name, default)
    try:
        return converter(raw)
    except (ValueError, json.JSONDecodeError):
        raise ValueError(
            f"Invalid value for {name}: {raw!r} (expected {type_label}). "
            f"Check ~/.prometheus/.env or environment variables."
        )


def _get_env_config() -> dict[str, Any]:
    default_image = "nikolaik/python-nodejs:python3.11-nodejs20"
    env_type = os.getenv("TERMINAL_ENV", "local")

    mount_docker_cwd = os.getenv("TERMINAL_DOCKER_MOUNT_CWD_TO_WORKSPACE", "false").lower() in (
        "true",
        "1",
        "yes",
    )

    if env_type == "local":
        default_cwd = os.getcwd()
    elif env_type == "ssh":
        default_cwd = "~"
    elif env_type == "vercel_sandbox":
        default_cwd = _VERCEL_SANDBOX_DEFAULT_CWD
    else:
        default_cwd = "/root"

    cwd = os.getenv("TERMINAL_CWD", default_cwd)
    if cwd:
        cwd = os.path.expanduser(cwd)
    host_cwd = None
    host_prefixes = ("/Users/", "/home/", "C:\\", "C:/")
    if env_type == "docker" and mount_docker_cwd:
        docker_cwd_source = os.getenv("TERMINAL_CWD") or os.getcwd()
        candidate = os.path.abspath(os.path.expanduser(docker_cwd_source))
        if any(candidate.startswith(p) for p in host_prefixes) or (
            os.path.isabs(candidate)
            and os.path.isdir(candidate)
            and not candidate.startswith(("/workspace", "/root"))
        ):
            host_cwd = candidate
            cwd = "/workspace"
    elif env_type in ("modal", "docker", "singularity", "daytona", "vercel_sandbox") and cwd:
        is_host_path = any(cwd.startswith(p) for p in host_prefixes)
        is_relative = not os.path.isabs(cwd)
        if (is_host_path or is_relative) and cwd != default_cwd:
            logger.info(
                "Ignoring TERMINAL_CWD=%r for %s backend "
                "(host/relative path won't work in sandbox). Using %r instead.",
                cwd,
                env_type,
                default_cwd,
            )
            cwd = default_cwd

    return {
        "env_type": env_type,
        "modal_mode": coerce_modal_mode(os.getenv("TERMINAL_MODAL_MODE", "auto")),
        "docker_image": os.getenv("TERMINAL_DOCKER_IMAGE", default_image),
        "docker_forward_env": _parse_env_var(
            "TERMINAL_DOCKER_FORWARD_ENV", "[]", json.loads, "valid JSON"
        ),
        "singularity_image": os.getenv("TERMINAL_SINGULARITY_IMAGE", f"docker://{default_image}"),
        "modal_image": os.getenv("TERMINAL_MODAL_IMAGE", default_image),
        "daytona_image": os.getenv("TERMINAL_DAYTONA_IMAGE", default_image),
        "vercel_runtime": os.getenv("TERMINAL_VERCEL_RUNTIME", "").strip(),
        "cwd": cwd,
        "host_cwd": host_cwd,
        "docker_mount_cwd_to_workspace": mount_docker_cwd,
        "timeout": _parse_env_var("TERMINAL_TIMEOUT", "180"),
        "lifetime_seconds": _parse_env_var("TERMINAL_LIFETIME_SECONDS", "300"),
        "ssh_host": os.getenv("TERMINAL_SSH_HOST", ""),
        "ssh_user": os.getenv("TERMINAL_SSH_USER", ""),
        "ssh_port": _parse_env_var("TERMINAL_SSH_PORT", "22"),
        "ssh_key": os.getenv("TERMINAL_SSH_KEY", ""),
        "ssh_persistent": os.getenv(
            "TERMINAL_SSH_PERSISTENT",
            os.getenv("TERMINAL_PERSISTENT_SHELL", "true"),
        ).lower()
        in ("true", "1", "yes"),
        "local_persistent": os.getenv("TERMINAL_LOCAL_PERSISTENT", "false").lower()
        in ("true", "1", "yes"),
        "container_cpu": _parse_env_var("TERMINAL_CONTAINER_CPU", "1", float, "number"),
        "container_memory": _parse_env_var("TERMINAL_CONTAINER_MEMORY", "5120"),
        "container_disk": _parse_env_var("TERMINAL_CONTAINER_DISK", "51200"),
        "container_persistent": os.getenv("TERMINAL_CONTAINER_PERSISTENT", "true").lower()
        in ("true", "1", "yes"),
        "docker_volumes": _parse_env_var("TERMINAL_DOCKER_VOLUMES", "[]", json.loads, "valid JSON"),
        "docker_run_as_host_user": os.getenv("TERMINAL_DOCKER_RUN_AS_HOST_USER", "false").lower()
        in ("true", "1", "yes"),
    }


def _get_modal_backend_state(modal_mode: object | None) -> dict[str, Any]:
    return resolve_modal_backend_state(
        modal_mode,
        has_direct=has_direct_modal_credentials(),
        managed_ready=is_managed_tool_gateway_ready("modal"),
    )


def _create_environment(
    env_type: str,
    image: str,
    cwd: str,
    timeout: int,
    ssh_config: dict = None,
    container_config: dict = None,
    local_config: dict = None,
    task_id: str = "default",
    host_cwd: str = None,
):
    cc = container_config or {}
    cpu = cc.get("container_cpu", 1)
    memory = cc.get("container_memory", 5120)
    disk = cc.get("container_disk", 51200)
    persistent = cc.get("container_persistent", True)
    volumes = cc.get("docker_volumes", [])
    docker_forward_env = cc.get("docker_forward_env", [])
    docker_env = cc.get("docker_env", {})

    if env_type == "local":
        return _LocalEnvironment()

    elif env_type == "docker":
        return _DockerEnvironment(
            image=image,
            cwd=cwd,
            timeout=timeout,
            cpu=cpu,
            memory=memory,
            disk=disk,
            persistent_filesystem=persistent,
            task_id=task_id,
            volumes=volumes,
            host_cwd=host_cwd,
            auto_mount_cwd=cc.get("docker_mount_cwd_to_workspace", False),
            forward_env=docker_forward_env,
            env=docker_env,
            run_as_host_user=cc.get("docker_run_as_host_user", False),
        )

    elif env_type == "singularity":
        return _SingularityEnvironment(
            image=image,
            cwd=cwd,
            timeout=timeout,
            cpu=cpu,
            memory=memory,
            disk=disk,
            persistent_filesystem=persistent,
            task_id=task_id,
        )

    elif env_type == "modal":
        sandbox_kwargs = {}
        if cpu > 0:
            sandbox_kwargs["cpu"] = cpu
        if memory > 0:
            sandbox_kwargs["memory"] = memory
        if disk > 0:
            try:
                import inspect

                import modal

                if "ephemeral_disk" in inspect.signature(modal.Sandbox.create).parameters:
                    sandbox_kwargs["ephemeral_disk"] = disk
            except Exception:
                pass

        modal_state = _get_modal_backend_state(cc.get("modal_mode"))

        if modal_state["selected_backend"] == "managed":
            return _ManagedModalEnvironment(
                image=image,
                cwd=cwd,
                timeout=timeout,
                modal_sandbox_kwargs=sandbox_kwargs,
                persistent_filesystem=persistent,
                task_id=task_id,
            )

        if modal_state["selected_backend"] != "direct":
            if modal_state["managed_mode_blocked"]:
                raise ValueError(
                    "Modal backend is configured for managed mode, but "
                    "a paid Nous subscription is required for the Tool Gateway and no direct "
                    "Modal credentials/config were found. Log in with `prometheus model` or "
                    "choose TERMINAL_MODAL_MODE=direct/auto."
                )
            if modal_state["mode"] == "managed":
                raise ValueError(
                    "Modal backend is configured for managed mode, but the managed tool gateway is unavailable."
                )
            if modal_state["mode"] == "direct":
                raise ValueError(
                    "Modal backend is configured for direct mode, but no direct Modal credentials/config were found."
                )
            message = "Modal backend selected but no direct Modal credentials/config was found."
            if managed_nous_tools_enabled():
                message = "Modal backend selected but no direct Modal credentials/config or managed tool gateway was found."
            raise ValueError(message)

        return _ModalEnvironment(
            image=image,
            cwd=cwd,
            timeout=timeout,
            modal_sandbox_kwargs=sandbox_kwargs,
            persistent_filesystem=persistent,
            task_id=task_id,
        )

    elif env_type == "daytona":
        from prometheus.tools.environments.daytona import DaytonaEnvironment as _DaytonaEnvironment

        return _DaytonaEnvironment(
            image=image,
            cwd=cwd,
            timeout=timeout,
            cpu=int(cpu),
            memory=memory,
            disk=disk,
            persistent_filesystem=persistent,
            task_id=task_id,
        )

    elif env_type == "vercel_sandbox":
        from prometheus.tools.environments.vercel_sandbox import (
            VercelSandboxEnvironment as _VercelSandboxEnvironment,
        )

        return _VercelSandboxEnvironment(
            runtime=cc.get("vercel_runtime") or None,
            cwd=cwd,
            timeout=timeout,
            cpu=cpu,
            memory=memory,
            disk=disk,
            persistent_filesystem=persistent,
            task_id=task_id,
        )

    elif env_type == "ssh":
        if not ssh_config or not ssh_config.get("host") or not ssh_config.get("user"):
            raise ValueError("SSH environment requires ssh_host and ssh_user to be configured")
        return _SSHEnvironment(
            host=ssh_config["host"],
            user=ssh_config["user"],
            port=ssh_config.get("port", 22),
            key_path=ssh_config.get("key", ""),
            cwd=cwd,
            timeout=timeout,
        )

    else:
        raise ValueError(
            f"Unknown environment type: {env_type}. Use 'local', 'docker', "
            f"'singularity', 'modal', 'daytona', 'vercel_sandbox', or 'ssh'"
        )


def _cleanup_inactive_envs(lifetime_seconds: int = 300):
    current_time = time.time()

    try:
        # 临时注释掉 process_registry 导入，避免 platform.system() 错误
        # from prometheus.tools.security.process_registry import process_registry
        
        # 简化处理：只清理没有活跃任务的环境
        for task_id in list(_last_activity.keys()):
            # 临时跳过 process_registry 检查
            # if process_registry.has_active_processes(task_id):
            #     _last_activity[task_id] = current_time
            pass
    except ImportError:
        pass

    envs_to_stop = []

    with _env_lock:
        for task_id, last_time in list(_last_activity.items()):
            if current_time - last_time > lifetime_seconds:
                env = _active_environments.pop(task_id, None)
                _last_activity.pop(task_id, None)
                if env is not None:
                    envs_to_stop.append((task_id, env))

        with _creation_locks_lock:
            for task_id, _ in envs_to_stop:
                _creation_locks.pop(task_id, None)

    for task_id, env in envs_to_stop:
        try:
            from prometheus.tools.file_tools import clear_file_ops_cache

            clear_file_ops_cache(task_id)
        except ImportError:
            pass

        try:
            if hasattr(env, "cleanup"):
                env.cleanup()
            elif hasattr(env, "stop"):
                env.stop()
            elif hasattr(env, "terminate"):
                env.terminate()

            logger.info("Cleaned up inactive environment for task: %s", task_id)

        except Exception as e:
            error_str = str(e)
            if "404" in error_str or "not found" in error_str.lower():
                logger.info("Environment for task %s already cleaned up", task_id)
            else:
                logger.warning("Error cleaning up environment for task %s: %s", task_id, e)


def _cleanup_thread_worker():
    while _cleanup_running:
        try:
            config = _get_env_config()
            _cleanup_inactive_envs(config["lifetime_seconds"])
        except Exception as e:
            logger.warning("Error in cleanup thread: %s", e, exc_info=True)

        for _ in range(60):
            if not _cleanup_running:
                break
            time.sleep(1)


def _start_cleanup_thread():
    global _cleanup_thread, _cleanup_running

    with _env_lock:
        if _cleanup_thread is None or not _cleanup_thread.is_alive():
            _cleanup_running = True
            _cleanup_thread = threading.Thread(target=_cleanup_thread_worker, daemon=True)
            _cleanup_thread.start()


def _stop_cleanup_thread():
    global _cleanup_running
    _cleanup_running = False
    if _cleanup_thread is not None:
        with contextlib.suppress(SystemExit, KeyboardInterrupt):
            _cleanup_thread.join(timeout=5)


def get_active_env(task_id: str):
    lookup = _resolve_container_task_id(task_id)
    with _env_lock:
        return _active_environments.get(lookup) or _active_environments.get(task_id)


def is_persistent_env(task_id: str) -> bool:
    env = get_active_env(task_id)
    if env is None:
        return False
    return bool(getattr(env, "_persistent", False))


def cleanup_all_environments():
    task_ids = list(_active_environments.keys())
    cleaned = 0

    for task_id in task_ids:
        try:
            cleanup_vm(task_id)
            cleaned += 1
        except Exception as e:
            logger.error("Error cleaning %s: %s", task_id, e, exc_info=True)

    scratch_dir = _get_scratch_dir()
    if scratch_dir is None:
        return cleaned
    import glob

    for path in glob.glob(str(scratch_dir / "prometheus-*")):
        try:
            shutil.rmtree(path, ignore_errors=True)
            logger.info("Removed orphaned: %s", path)
        except OSError as e:
            logger.debug("Failed to remove orphaned path %s: %s", path, e)

    if cleaned > 0:
        logger.info("Cleaned %d environments", cleaned)
    return cleaned


def cleanup_vm(task_id: str):
    env = None
    with _env_lock:
        env = _active_environments.pop(task_id, None)
        _last_activity.pop(task_id, None)

    with _creation_locks_lock:
        _creation_locks.pop(task_id, None)

    try:
        from prometheus.tools.file_tools import clear_file_ops_cache

        clear_file_ops_cache(task_id)
    except ImportError:
        pass

    if env is None:
        return

    try:
        if hasattr(env, "cleanup"):
            env.cleanup()
        elif hasattr(env, "stop"):
            env.stop()
        elif hasattr(env, "terminate"):
            env.terminate()

        logger.info("Manually cleaned up environment for task: %s", task_id)

    except Exception as e:
        error_str = str(e)
        if "404" in error_str or "not found" in error_str.lower():
            logger.info("Environment for task %s already cleaned up", task_id)
        else:
            logger.warning("Error cleaning up environment for task %s: %s", task_id, e)


def _atexit_cleanup():
    _stop_cleanup_thread()
    if _active_environments:
        count = len(_active_environments)
        logger.info("Shutting down %d remaining sandbox(es)...", count)
        cleanup_all_environments()


atexit.register(_atexit_cleanup)


def _interpret_exit_code(command: str, exit_code: int) -> str | None:
    if exit_code == 0:
        return None

    segments = re.split(r"\s*(?:\|\||&&|[|;])\s*", command)
    last_segment = (segments[-1] if segments else command).strip()

    words = last_segment.split()
    base_cmd = ""
    for w in words:
        if "=" in w and not w.startswith("-"):
            continue
        base_cmd = w.split("/")[-1]
        break

    if not base_cmd:
        return None

    semantics: dict[str, dict[int, str]] = {
        "grep": {1: "No matches found (not an error)"},
        "egrep": {1: "No matches found (not an error)"},
        "fgrep": {1: "No matches found (not an error)"},
        "rg": {1: "No matches found (not an error)"},
        "ag": {1: "No matches found (not an error)"},
        "ack": {1: "No matches found (not an error)"},
        "diff": {1: "Files differ (expected, not an error)"},
        "colordiff": {1: "Files differ (expected, not an error)"},
        "find": {1: "Some directories were inaccessible (partial results may still be valid)"},
        "test": {1: "Condition evaluated to false (expected, not an error)"},
        "[": {1: "Condition evaluated to false (expected, not an error)"},
        "curl": {
            6: "Could not resolve host",
            7: "Failed to connect to host",
            22: "HTTP response code indicated error (e.g. 404, 500)",
            28: "Operation timed out",
        },
        "git": {1: "Non-zero exit (often normal — e.g. 'git diff' returns 1 when files differ)"},
    }

    cmd_semantics = semantics.get(base_cmd)
    if cmd_semantics and exit_code in cmd_semantics:
        return cmd_semantics[exit_code]

    return None


def _command_requires_pipe_stdin(command: str) -> bool:
    normalized = " ".join(command.lower().split())
    return normalized.startswith("gh auth login") and "--with-token" in normalized


_SHELL_LEVEL_BACKGROUND_RE = re.compile(r"\b(?:nohup|disown|setsid)\b", re.IGNORECASE)
_INLINE_BACKGROUND_AMP_RE = re.compile(r"\s&\s")
_TRAILING_BACKGROUND_AMP_RE = re.compile(r"\s&\s*(?:#.*)?$")
_LONG_LIVED_FOREGROUND_PATTERNS = (
    re.compile(r"\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?(?:dev|start|serve|watch)\b", re.IGNORECASE),
    re.compile(r"\bdocker\s+compose\s+up\b", re.IGNORECASE),
    re.compile(r"\bnext\s+dev\b", re.IGNORECASE),
    re.compile(r"\bvite(?:\s|$)", re.IGNORECASE),
    re.compile(r"\bnodemon\b", re.IGNORECASE),
    re.compile(r"\buvicorn\b", re.IGNORECASE),
    re.compile(r"\bgunicorn\b", re.IGNORECASE),
    re.compile(r"\bpython(?:3)?\s+-m\s+http\.server\b", re.IGNORECASE),
)


def _looks_like_help_or_version_command(command: str) -> bool:
    normalized = " ".join(command.lower().split())
    return (
        " --help" in normalized
        or normalized.endswith(" -h")
        or " --version" in normalized
        or normalized.endswith(" -v")
    )


def _foreground_background_guidance(command: str) -> str | None:
    if _looks_like_help_or_version_command(command):
        return None

    if _SHELL_LEVEL_BACKGROUND_RE.search(command):
        return (
            "Foreground command uses shell-level background wrappers (nohup/disown/setsid). "
            "Use terminal(background=true) so Prometheus can track the process, then run "
            "readiness checks and tests in separate commands."
        )

    if _INLINE_BACKGROUND_AMP_RE.search(command) or _TRAILING_BACKGROUND_AMP_RE.search(command):
        return (
            "Foreground command uses '&' backgrounding. Use terminal(background=true) for long-lived "
            "processes, then run health checks and tests in follow-up terminal calls."
        )

    for pattern in _LONG_LIVED_FOREGROUND_PATTERNS:
        if pattern.search(command):
            return (
                "This foreground command appears to start a long-lived server/watch process. "
                "Run it with background=true, verify readiness (health endpoint/log signal), "
                "then execute tests in a separate command."
            )

    return None


def _resolve_notification_flag_conflict(
    *,
    notify_on_complete: bool,
    watch_patterns,
    background: bool,
) -> tuple:
    if background and notify_on_complete and watch_patterns:
        note = (
            "watch_patterns ignored because notify_on_complete=True; "
            "these two flags produce duplicate notifications when combined"
        )
        return None, note
    return watch_patterns, ""


def terminal_tool(
    command: str,
    background: bool = False,
    timeout: int | None = None,
    task_id: str | None = None,
    force: bool = False,
    workdir: str | None = None,
    pty: bool = False,
    notify_on_complete: bool = False,
    watch_patterns: list[str] | None = None,
) -> str:
    try:
        if not isinstance(command, str):
            logger.warning(
                "Rejected invalid terminal command value: %s",
                type(command).__name__,
            )
            return json.dumps(
                {
                    "output": "",
                    "exit_code": -1,
                    "error": f"Invalid command: expected string, got {type(command).__name__}",
                    "status": "error",
                },
                ensure_ascii=False,
            )

        config = _get_env_config()
        env_type = config["env_type"]

        effective_task_id = _resolve_container_task_id(task_id)

        overrides = _task_env_overrides.get(effective_task_id, {})

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
        default_timeout = config["timeout"]
        effective_timeout = timeout or default_timeout

        if not background and timeout and timeout > FOREGROUND_MAX_TIMEOUT:
            return json.dumps(
                {
                    "error": (
                        f"Foreground timeout {timeout}s exceeds the maximum of "
                        f"{FOREGROUND_MAX_TIMEOUT}s. Use background=true with "
                        f"notify_on_complete=true for long-running commands."
                    ),
                },
                ensure_ascii=False,
            )

        if not background:
            guidance = _foreground_background_guidance(command)
            if guidance:
                return json.dumps(
                    {
                        "output": "",
                        "exit_code": -1,
                        "error": guidance,
                        "status": "error",
                    },
                    ensure_ascii=False,
                )

        _start_cleanup_thread()

        with _env_lock:
            if effective_task_id in _active_environments:
                _last_activity[effective_task_id] = time.time()
                env = _active_environments[effective_task_id]
                needs_creation = False
            else:
                needs_creation = True

        if needs_creation:
            with _creation_locks_lock:
                if effective_task_id not in _creation_locks:
                    _creation_locks[effective_task_id] = threading.Lock()
                task_lock = _creation_locks[effective_task_id]

            with task_lock:
                with _env_lock:
                    if effective_task_id in _active_environments:
                        _last_activity[effective_task_id] = time.time()
                        env = _active_environments[effective_task_id]
                        needs_creation = False

                if needs_creation:
                    if env_type == "singularity":
                        _check_disk_usage_warning()
                    logger.info(
                        "Creating new %s environment for task %s...",
                        env_type,
                        effective_task_id[:8],
                    )
                    try:
                        ssh_config = None
                        if env_type == "ssh":
                            ssh_config = {
                                "host": config.get("ssh_host", ""),
                                "user": config.get("ssh_user", ""),
                                "port": config.get("ssh_port", 22),
                                "key": config.get("ssh_key", ""),
                                "persistent": config.get("ssh_persistent", False),
                            }

                        container_config = None
                        if env_type in (
                            "docker",
                            "singularity",
                            "modal",
                            "daytona",
                            "vercel_sandbox",
                        ):
                            container_config = {
                                "container_cpu": config.get("container_cpu", 1),
                                "container_memory": config.get("container_memory", 5120),
                                "container_disk": config.get("container_disk", 51200),
                                "container_persistent": config.get("container_persistent", True),
                                "modal_mode": config.get("modal_mode", "auto"),
                                "vercel_runtime": config.get("vercel_runtime", ""),
                                "docker_volumes": config.get("docker_volumes", []),
                                "docker_mount_cwd_to_workspace": config.get(
                                    "docker_mount_cwd_to_workspace", False
                                ),
                                "docker_forward_env": config.get("docker_forward_env", []),
                                "docker_env": config.get("docker_env", {}),
                                "docker_run_as_host_user": config.get(
                                    "docker_run_as_host_user", False
                                ),
                            }

                        local_config = None
                        if env_type == "local":
                            local_config = {
                                "persistent": config.get("local_persistent", False),
                            }

                        new_env = _create_environment(
                            env_type=env_type,
                            image=image,
                            cwd=cwd,
                            timeout=effective_timeout,
                            ssh_config=ssh_config,
                            container_config=container_config,
                            local_config=local_config,
                            task_id=effective_task_id,
                            host_cwd=config.get("host_cwd"),
                        )
                    except ImportError as e:
                        return json.dumps(
                            {
                                "output": "",
                                "exit_code": -1,
                                "error": f"Terminal tool disabled: environment creation failed ({e})",
                                "status": "disabled",
                            },
                            ensure_ascii=False,
                        )

                    with _env_lock:
                        _active_environments[effective_task_id] = new_env
                        _last_activity[effective_task_id] = time.time()
                        env = new_env
                    logger.info("%s environment ready for task %s", env_type, effective_task_id[:8])

        approval_note = None
        if not force:
            approval = _check_all_guards(command, env_type)
            if not approval["approved"]:
                if approval.get("status") == "approval_required":
                    return json.dumps(
                        {
                            "output": "",
                            "exit_code": -1,
                            "error": approval.get("message", "Waiting for user approval"),
                            "status": "approval_required",
                            "command": approval.get("command", command),
                            "description": approval.get("description", "command flagged"),
                            "pattern_key": approval.get("pattern_key", ""),
                        },
                        ensure_ascii=False,
                    )
                desc = approval.get("description", "command flagged")
                fallback_msg = (
                    f"Command denied: {desc}. "
                    "Use the approval prompt to allow it, or rephrase the command."
                )
                return json.dumps(
                    {
                        "output": "",
                        "exit_code": -1,
                        "error": approval.get("message", fallback_msg),
                        "status": "blocked",
                    },
                    ensure_ascii=False,
                )
            if approval.get("user_approved"):
                desc = approval.get("description", "flagged as dangerous")
                approval_note = f"Command required approval ({desc}) and was approved by the user."
            elif approval.get("smart_approved"):
                desc = approval.get("description", "flagged as dangerous")
                approval_note = f"Command was flagged ({desc}) and auto-approved by smart approval."

        if workdir:
            workdir_error = _validate_workdir(workdir)
            if workdir_error:
                logger.warning(
                    "Blocked dangerous workdir: %s (command: %s)",
                    workdir[:200],
                    _safe_command_preview(command),
                )
                return json.dumps(
                    {"output": "", "exit_code": -1, "error": workdir_error, "status": "blocked"},
                    ensure_ascii=False,
                )

        pty_disabled_reason = None
        effective_pty = pty
        if pty and _command_requires_pipe_stdin(command):
            effective_pty = False
            pty_disabled_reason = (
                "PTY disabled for this command because it expects piped stdin/EOF "
                "(for example gh auth login --with-token). For local background "
                "processes, call process(action='close') after writing so it receives "
                "EOF."
            )

        if background:
            from prometheus.tools.security.approval import get_current_session_key
            from prometheus.tools.security.process_registry import process_registry

            session_key = get_current_session_key(default="")
            effective_cwd = workdir or cwd
            try:
                if env_type == "local":
                    proc_session = process_registry.spawn_local(
                        command=command,
                        cwd=effective_cwd,
                        task_id=effective_task_id,
                        session_key=session_key,
                        env_vars=env.env if hasattr(env, "env") else None,
                        use_pty=effective_pty,
                    )
                else:
                    proc_session = process_registry.spawn_via_env(
                        env=env,
                        command=command,
                        cwd=effective_cwd,
                        task_id=effective_task_id,
                        session_key=session_key,
                    )

                result_data = {
                    "output": "Background process started",
                    "session_id": proc_session.id,
                    "pid": proc_session.pid,
                    "exit_code": 0,
                    "error": None,
                }
                if approval_note:
                    result_data["approval"] = approval_note
                if pty_disabled_reason:
                    result_data["pty_note"] = pty_disabled_reason

                if background and (notify_on_complete or watch_patterns):
                    from prometheus.gateway.session_context import get_session_env as _gse

                    _gw_platform = _gse("PROMETHEUS_SESSION_PLATFORM", "")
                    if _gw_platform:
                        _gw_chat_id = _gse("PROMETHEUS_SESSION_CHAT_ID", "")
                        _gw_thread_id = _gse("PROMETHEUS_SESSION_THREAD_ID", "")
                        _gw_user_id = _gse("PROMETHEUS_SESSION_USER_ID", "")
                        _gw_user_name = _gse("PROMETHEUS_SESSION_USER_NAME", "")
                        proc_session.watcher_platform = _gw_platform
                        proc_session.watcher_chat_id = _gw_chat_id
                        proc_session.watcher_user_id = _gw_user_id
                        proc_session.watcher_user_name = _gw_user_name
                        proc_session.watcher_thread_id = _gw_thread_id

                watch_patterns, conflict_note = _resolve_notification_flag_conflict(
                    notify_on_complete=bool(notify_on_complete),
                    watch_patterns=watch_patterns,
                    background=bool(background),
                )
                if conflict_note:
                    logger.warning("background proc %s: %s", proc_session.id, conflict_note)
                    result_data["watch_patterns_ignored"] = conflict_note

                if notify_on_complete and background:
                    proc_session.notify_on_complete = True
                    result_data["notify_on_complete"] = True

                    if proc_session.watcher_platform:
                        proc_session.watcher_interval = 5
                        process_registry.pending_watchers.append(
                            {
                                "session_id": proc_session.id,
                                "check_interval": 5,
                                "session_key": session_key,
                                "platform": proc_session.watcher_platform,
                                "chat_id": proc_session.watcher_chat_id,
                                "user_id": proc_session.watcher_user_id,
                                "user_name": proc_session.watcher_user_name,
                                "thread_id": proc_session.watcher_thread_id,
                                "notify_on_complete": True,
                            }
                        )

                if watch_patterns and background:
                    proc_session.watch_patterns = list(watch_patterns)
                    result_data["watch_patterns"] = proc_session.watch_patterns

                return json.dumps(result_data, ensure_ascii=False)
            except Exception as e:
                return json.dumps(
                    {
                        "output": "",
                        "exit_code": -1,
                        "error": f"Failed to start background process: {str(e)}",
                    },
                    ensure_ascii=False,
                )
        else:
            max_retries = 3
            retry_count = 0
            result = None

            while retry_count <= max_retries:
                try:
                    execute_kwargs = {"timeout": effective_timeout}
                    if workdir:
                        execute_kwargs["cwd"] = workdir
                    result = env.execute(command, **execute_kwargs)
                except Exception as e:
                    error_str = str(e).lower()
                    if "timeout" in error_str:
                        return json.dumps(
                            {
                                "output": "",
                                "exit_code": 124,
                                "error": f"Command timed out after {effective_timeout} seconds",
                            },
                            ensure_ascii=False,
                        )

                    if retry_count < max_retries:
                        retry_count += 1
                        wait_time = 2**retry_count
                        logger.warning(
                            "Execution error, retrying in %ds (attempt %d/%d) - Command: %s - Error: %s: %s - Task: %s, Backend: %s",
                            wait_time,
                            retry_count,
                            max_retries,
                            _safe_command_preview(command),
                            type(e).__name__,
                            e,
                            effective_task_id,
                            env_type,
                        )
                        time.sleep(wait_time)
                        continue

                    logger.error(
                        "Execution failed after %d retries - Command: %s - Error: %s: %s - Task: %s, Backend: %s",
                        max_retries,
                        _safe_command_preview(command),
                        type(e).__name__,
                        e,
                        effective_task_id,
                        env_type,
                    )
                    return json.dumps(
                        {
                            "output": "",
                            "exit_code": -1,
                            "error": f"Command execution failed: {type(e).__name__}: {str(e)}",
                        },
                        ensure_ascii=False,
                    )

                break

            output = result.output if hasattr(result, 'output') else result.get("output", "")
            returncode = result.exit_code if hasattr(result, 'exit_code') else result.get("returncode", 0)

            output = _handle_sudo_failure(output, env_type)

            try:
                from prometheus.cli.plugins import invoke_hook

                hook_results = invoke_hook(
                    "transform_terminal_output",
                    command=command,
                    output=output,
                    returncode=returncode,
                    task_id=effective_task_id or "",
                    env_type=env_type,
                )
                for hook_result in hook_results:
                    if isinstance(hook_result, str):
                        output = hook_result
                        break
            except Exception:
                pass

            from prometheus.tools.security.tool_output_limits import get_max_bytes

            MAX_OUTPUT_CHARS = get_max_bytes()
            if len(output) > MAX_OUTPUT_CHARS:
                head_chars = int(MAX_OUTPUT_CHARS * 0.4)
                tail_chars = MAX_OUTPUT_CHARS - head_chars
                omitted = len(output) - head_chars - tail_chars
                truncated_notice = (
                    f"\n\n... [OUTPUT TRUNCATED - {omitted} chars omitted "
                    f"out of {len(output)} total] ...\n\n"
                )
                output = output[:head_chars] + truncated_notice + output[-tail_chars:]

            from prometheus.tools.ansi_strip import strip_ansi

            output = strip_ansi(output)

            from prometheus.agent.redact import redact_sensitive_text

            output = redact_sensitive_text(output.strip()) if output else ""

            exit_note = _interpret_exit_code(command, returncode)

            result_dict = {
                "output": output,
                "exit_code": returncode,
                "error": None,
            }
            if approval_note:
                result_dict["approval"] = approval_note
            if exit_note:
                result_dict["exit_code_meaning"] = exit_note

            return json.dumps(result_dict, ensure_ascii=False)

    except Exception as e:
        import traceback

        tb_str = traceback.format_exc()
        logger.error("terminal_tool exception:\n%s", tb_str)
        return json.dumps(
            {
                "output": "",
                "exit_code": -1,
                "error": f"Failed to execute command: {str(e)}",
                "traceback": tb_str,
                "status": "error",
            },
            ensure_ascii=False,
        )


def check_terminal_requirements() -> bool:
    try:
        config = _get_env_config()
        env_type = config["env_type"]

        if env_type == "local":
            return True

        elif env_type == "docker":
            from prometheus.tools.environments.docker import find_docker

            docker = find_docker()
            if not docker:
                logger.error("Docker executable not found in PATH or common install locations")
                return False
            result = subprocess.run([docker, "version"], capture_output=True, timeout=5)
            return result.returncode == 0

        elif env_type == "singularity":
            executable = shutil.which("apptainer") or shutil.which("singularity")
            if executable:
                result = subprocess.run([executable, "--version"], capture_output=True, timeout=5)
                return result.returncode == 0
            return False

        elif env_type == "ssh":
            if not config.get("ssh_host") or not config.get("ssh_user"):
                logger.error(
                    "SSH backend selected but TERMINAL_SSH_HOST and TERMINAL_SSH_USER "
                    "are not both set. Configure both or switch TERMINAL_ENV to 'local'."
                )
                return False
            return True

        elif env_type == "modal":
            modal_state = _get_modal_backend_state(config.get("modal_mode"))
            if modal_state["selected_backend"] == "managed":
                return True

            if modal_state["selected_backend"] != "direct":
                if modal_state["managed_mode_blocked"]:
                    logger.error(
                        "Modal backend selected with TERMINAL_MODAL_MODE=managed, but "
                        "a paid Nous subscription is required for the Tool Gateway and no direct "
                        "Modal credentials/config were found. Log in with `prometheus model` "
                        "or choose TERMINAL_MODAL_MODE=direct/auto."
                    )
                    return False
                if modal_state["mode"] == "managed":
                    logger.error(
                        "Modal backend selected with TERMINAL_MODAL_MODE=managed, but the managed "
                        "tool gateway is unavailable. Configure the managed gateway or choose "
                        "TERMINAL_MODAL_MODE=direct/auto."
                    )
                    return False
                elif modal_state["mode"] == "direct":
                    if managed_nous_tools_enabled():
                        logger.error(
                            "Modal backend selected with TERMINAL_MODAL_MODE=direct, but no direct "
                            "Modal credentials/config were found. Configure Modal or choose "
                            "TERMINAL_MODAL_MODE=managed/auto."
                        )
                    else:
                        logger.error(
                            "Modal backend selected with TERMINAL_MODAL_MODE=direct, but no direct "
                            "Modal credentials/config was found. Configure Modal or choose "
                            "TERMINAL_MODAL_MODE=auto."
                        )
                    return False
                else:
                    if managed_nous_tools_enabled():
                        logger.error(
                            "Modal backend selected but no direct Modal credentials/config or managed "
                            "tool gateway was found. Configure Modal, set up the managed gateway, "
                            "or choose a different TERMINAL_ENV."
                        )
                    else:
                        logger.error(
                            "Modal backend selected but no direct Modal credentials/config was found. "
                            "Configure Modal or choose a different TERMINAL_ENV."
                        )
                    return False

            if importlib.util.find_spec("modal") is None:
                logger.error(
                    "modal is required for direct modal terminal backend: pip install modal"
                )
                return False

            return True

        elif env_type == "vercel_sandbox":
            return _check_vercel_sandbox_requirements(config)

        elif env_type == "daytona":
            from daytona import Daytona  # noqa: F401

            return os.getenv("DAYTONA_API_KEY") is not None

        else:
            logger.error(
                "Unknown TERMINAL_ENV '%s'. Use one of: local, docker, singularity, "
                "modal, daytona, vercel_sandbox, ssh.",
                env_type,
            )
            return False
    except Exception as e:
        logger.error("Terminal requirements check failed: %s", e, exc_info=True)
        return False


if __name__ == "__main__":
    print("Terminal Tool Module")
    print("=" * 50)

    config = _get_env_config()
    print("\nCurrent Configuration:")
    print(f"  Environment type: {config['env_type']}")
    print(f"  Docker image: {config['docker_image']}")
    print(f"  Modal image: {config['modal_image']}")
    print(f"  Working directory: {config['cwd']}")
    print(f"  Default timeout: {config['timeout']}s")
    print(f"  Lifetime: {config['lifetime_seconds']}s")

    if not check_terminal_requirements():
        print("\nRequirements not met. Please check the messages above.")
        exit(1)

    print("\nAll requirements met!")
    print("\nAvailable Tool:")
    print("  - terminal_tool: Execute commands in sandboxed environments")

    print("\nUsage Examples:")
    print("  # Execute a command")
    print("  result = terminal_tool(command='ls -la')")
    print("  ")
    print("  # Run a background task")
    print("  result = terminal_tool(command='python server.py', background=True)")

    print("\nEnvironment Variables:")
    default_img = "nikolaik/python-nodejs:python3.11-nodejs20"
    print(
        "  TERMINAL_ENV: "
        f"{os.getenv('TERMINAL_ENV', 'local')} "
        "(local/docker/singularity/modal/daytona/vercel_sandbox/ssh)"
    )
    print(f"  TERMINAL_DOCKER_IMAGE: {os.getenv('TERMINAL_DOCKER_IMAGE', default_img)}")
    print(
        f"  TERMINAL_SINGULARITY_IMAGE: {os.getenv('TERMINAL_SINGULARITY_IMAGE', f'docker://{default_img}')}"
    )
    print(f"  TERMINAL_MODAL_IMAGE: {os.getenv('TERMINAL_MODAL_IMAGE', default_img)}")
    print(f"  TERMINAL_DAYTONA_IMAGE: {os.getenv('TERMINAL_DAYTONA_IMAGE', default_img)}")
    print(f"  TERMINAL_CWD: {os.getenv('TERMINAL_CWD', os.getcwd())}")
    from prometheus.constants_core import display_prometheus_home as _dhh

    print(f"  TERMINAL_SANDBOX_DIR: {os.getenv('TERMINAL_SANDBOX_DIR', f'{_dhh()}/sandboxes')}")
    print(f"  TERMINAL_TIMEOUT: {os.getenv('TERMINAL_TIMEOUT', '60')}")
    print(f"  TERMINAL_LIFETIME_SECONDS: {os.getenv('TERMINAL_LIFETIME_SECONDS', '300')}")


from prometheus.tools.security.registry import registry

TERMINAL_SCHEMA = {
    "name": "terminal",
    "description": TERMINAL_TOOL_DESCRIPTION,
    "parameters": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The command to execute on the VM"},
            "background": {
                "type": "boolean",
                "description": "Run the command in the background. Two patterns: (1) Long-lived processes that never exit (servers, watchers). (2) Long-running tasks paired with notify_on_complete=true — you can keep working and get notified when the task finishes. For short commands, prefer foreground with a generous timeout instead.",
                "default": False,
            },
            "timeout": {
                "type": "integer",
                "description": f"Max seconds to wait (default: 180, foreground max: {FOREGROUND_MAX_TIMEOUT}). Returns INSTANTLY when command finishes — set high for long tasks, you won't wait unnecessarily. Foreground timeout above {FOREGROUND_MAX_TIMEOUT}s is rejected; use background=true for longer commands.",
                "minimum": 1,
            },
            "workdir": {
                "type": "string",
                "description": "Working directory for this command (absolute path). Defaults to the session working directory.",
            },
            "pty": {
                "type": "boolean",
                "description": "Run in pseudo-terminal (PTY) mode for interactive CLI tools like Codex, Claude Code, or Python REPL. Only works with local and SSH backends. Default: false.",
                "default": False,
            },
            "notify_on_complete": {
                "type": "boolean",
                "description": "When true (and background=true), you'll be automatically notified exactly once when the process finishes. **This is the right choice for almost every long-running task** — tests, builds, deployments, multi-item batch jobs, anything that takes over a minute and has a defined end. Use this and keep working on other things; the system notifies you on exit. MUTUALLY EXCLUSIVE with watch_patterns — when both are set, watch_patterns is dropped.",
                "default": False,
            },
            "watch_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Strings to watch for in background process output. HARD RATE LIMIT: at most 1 notification per 15 seconds per process — matches arriving inside the cooldown are dropped. After 3 consecutive 15-second windows with dropped matches, watch_patterns is automatically disabled for that process and promoted to notify_on_complete behavior (one notification on exit, no more mid-process spam). USE ONLY for truly rare, one-shot mid-process signals on LONG-LIVED processes that will never exit on their own — e.g. ['Application startup complete'] on a server so you know when to hit its endpoint, or ['migration done'] on a daemon. DO NOT use for: (1) end-of-run markers like 'DONE'/'PASS' — use notify_on_complete instead; (2) error patterns like 'ERROR'/'Traceback' in loops or multi-item batch jobs — they fire on every iteration and you'll hit the strike limit fast; (3) anything you'd ever combine with notify_on_complete. When in doubt, choose notify_on_complete. MUTUALLY EXCLUSIVE with notify_on_complete — set one, not both.",
            },
        },
        "required": ["command"],
    },
}


def _handle_terminal(args, **kw):
    return terminal_tool(
        command=args.get("command"),
        background=args.get("background", False),
        timeout=args.get("timeout"),
        task_id=kw.get("task_id"),
        workdir=args.get("workdir"),
        pty=args.get("pty", False),
        notify_on_complete=args.get("notify_on_complete", False),
        watch_patterns=args.get("watch_patterns"),
    )


registry.register(
    name="terminal",
    toolset="terminal",
    schema=TERMINAL_SCHEMA,
    handler=_handle_terminal,
    check_fn=check_terminal_requirements,
    emoji="💻",
    max_result_size_chars=100_000,
)
