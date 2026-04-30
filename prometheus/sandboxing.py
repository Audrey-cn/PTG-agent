#!/usr/bin/env python3
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional


def _find_python() -> str:
    for name in ("python3", "python"):
        p = shutil.which(name)
        if p:
            return p
    return sys.executable


def _find_node() -> Optional[str]:
    return shutil.which("node")


def _find_bash() -> str:
    for name in ("bash", "sh"):
        p = shutil.which(name)
        if p:
            return p
    return "/bin/sh"


TIMEOUT_DEFAULT = 30
MAX_OUTPUT_BYTES = 50_000


def _truncate(text: str) -> str:
    b = text.encode("utf-8", errors="replace")[:MAX_OUTPUT_BYTES]
    return b.decode("utf-8", errors="replace")


class SandboxResult:
    def __init__(self):
        self.stdout = ""
        self.stderr = ""
        self.exit_code = 0
        self.timed_out = False
        self.wall_time_s: float = 0.0


def _run_subprocess_sandbox(
    cmd: list[str],
    cwd: Path,
    env: dict,
    timeout_s: int,
) -> SandboxResult:
    res = SandboxResult()
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            timeout=timeout_s,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        res.exit_code = proc.returncode
        res.stdout = _truncate(proc.stdout or "")
        res.stderr = _truncate(proc.stderr or "")
    except subprocess.TimeoutExpired:
        res.timed_out = True
        res.exit_code = -1
        res.stderr = "Process timed out."
    except Exception as e:
        res.exit_code = -1
        res.stderr = str(e)
    res.wall_time_s = time.monotonic() - t0
    return res


def run_python(code: str, timeout_s: int = TIMEOUT_DEFAULT) -> SandboxResult:
    python = _find_python()
    with tempfile.TemporaryDirectory(prefix="prometheus_sandbox_") as td:
        work = Path(td)
        script = work / "user_script.py"
        script.write_text(code, encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return _run_subprocess_sandbox(
            [python, "-u", str(script)],
            cwd=work,
            env=env,
            timeout_s=timeout_s,
        )


def run_javascript(code: str, timeout_s: int = TIMEOUT_DEFAULT) -> SandboxResult:
    node = _find_node()
    if node is None:
        res = SandboxResult()
        res.exit_code = -1
        res.stderr = "Node.js not found."
        return res

    with tempfile.TemporaryDirectory(prefix="prometheus_sandbox_") as td:
        work = Path(td)
        script = work / "user_script.js"
        script.write_text(code, encoding="utf-8")
        env = os.environ.copy()
        return _run_subprocess_sandbox(
            [node, str(script)],
            cwd=work,
            env=env,
            timeout_s=timeout_s,
        )


def run_bash(cmd: str, timeout_s: int = TIMEOUT_DEFAULT) -> SandboxResult:
    bash = _find_bash()
    with tempfile.TemporaryDirectory(prefix="prometheus_sandbox_") as td:
        work = Path(td)
        env = os.environ.copy()
        return _run_subprocess_sandbox(
            [bash, "-c", cmd],
            cwd=work,
            env=env,
            timeout_s=timeout_s,
        )


def run_command(args: list[str], cwd: Optional[Path] = None, timeout_s: int = TIMEOUT_DEFAULT) -> SandboxResult:
    cwd = cwd or Path.cwd()
    env = os.environ.copy()
    return _run_subprocess_sandbox(args, cwd=cwd, env=env, timeout_s=timeout_s)


def check_sandbox_available() -> bool:
    try:
        result = run_python("print('ok')", timeout_s=5)
        return result.exit_code == 0
    except Exception:
        return False
