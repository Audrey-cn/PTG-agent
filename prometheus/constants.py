#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from typing import Optional

def get_prometheus_home() -> Path:
    env = os.getenv("PROMETHEUS_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / ".prometheus"

def get_prometheus_home_display() -> str:
    home = get_prometheus_home()
    try:
        return "~/" + str(home.relative_to(Path.home()))
    except ValueError:
        return str(home)

VALID_REASONING_EFFORTS = ("minimal", "low", "medium", "high", "xhigh")

def parse_reasoning_effort(effort: str) -> Optional[dict]:
    if not effort or not effort.strip():
        return None
    effort = effort.strip().lower()
    if effort == "none":
        return {"enabled": False}
    if effort in VALID_REASONING_EFFORTS:
        return {"enabled": True, "effort": effort}
    return None

def is_termux() -> bool:
    prefix = os.getenv("PREFIX", "")
    return bool(os.getenv("TERMUX_VERSION") or "com.termux/files/usr" in prefix)

_WSL_DETECTED: Optional[bool] = None

def is_wsl() -> bool:
    global _WSL_DETECTED
    if _WSL_DETECTED is not None:
        return _WSL_DETECTED
    try:
        with open("/proc/version", "r") as f:
            _WSL_DETECTED = "microsoft" in f.read().lower()
    except Exception:
        _WSL_DETECTED = False
    return _WSL_DETECTED

_CONTAINER_DETECTED: Optional[bool] = None

def is_container() -> bool:
    global _CONTAINER_DETECTED
    if _CONTAINER_DETECTED is not None:
        return _CONTAINER_DETECTED
    _CONTAINER_DETECTED = os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv")
    return _CONTAINER_DETECTED

PROMETHEUS_VERSION = "0.8.0"
PROMETHEUS_CODENAME = "Prometheus"
