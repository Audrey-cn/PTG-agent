#!/usr/bin/env python3
import os
import sys
import json
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional

GATEWAY_PID_FILE = Path.home() / ".prometheus" / "gateway.pid"
GATEWAY_LOG_FILE = Path.home() / ".prometheus" / "gateway.log"


def _get_pid() -> Optional[int]:
    if not GATEWAY_PID_FILE.exists():
        return None
    try:
        pid = int(GATEWAY_PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (ValueError, OSError):
        return None


def start_gateway(platform: str = "cli") -> bool:
    existing = _get_pid()
    if existing:
        print(f"Gateway 已在运行 (pid={existing})")
        return False

    GATEWAY_PID_FILE.parent.mkdir(parents=True, exist_ok=True)

    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cli", "main.py")
    args = [sys.executable, script, "gateway", "serve", "--platform", platform]

    log = open(str(GATEWAY_LOG_FILE), "a")
    proc = subprocess.Popen(args, stdout=log, stderr=log, start_new_session=True)
    GATEWAY_PID_FILE.write_text(str(proc.pid))
    print(f"Gateway 已启动 (pid={proc.pid}, platform={platform})")
    return True


def stop_gateway() -> bool:
    pid = _get_pid()
    if pid is None:
        print("Gateway 未运行")
        return False

    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(10):
            time.sleep(0.3)
            try:
                os.kill(pid, 0)
            except OSError:
                break
        else:
            os.kill(pid, signal.SIGKILL)
    except OSError:
        pass

    GATEWAY_PID_FILE.unlink(missing_ok=True)
    print(f"Gateway 已停止 (pid={pid})")
    return True


def gateway_status() -> dict:
    pid = _get_pid()
    if pid is None:
        return {"running": False, "pid": None}

    return {
        "running": True,
        "pid": pid,
        "log_file": str(GATEWAY_LOG_FILE),
    }
