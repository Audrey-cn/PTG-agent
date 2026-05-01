from __future__ import annotations

import os
import re
from pathlib import Path

from prometheus.config import get_env_path


def _parse_env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    lines = path.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("#"):
            i += 1
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if not match:
            i += 1
            continue
        key = match.group(1)
        raw_value = match.group(2).strip()
        if raw_value.startswith('"') and raw_value.endswith('"') and len(raw_value) >= 2:
            result[key] = raw_value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
            i += 1
            continue
        if raw_value.startswith("'") and raw_value.endswith("'") and len(raw_value) >= 2:
            result[key] = raw_value[1:-1]
            i += 1
            continue
        if raw_value.startswith('"'):
            collected = [raw_value[1:]]
            i += 1
            while i < len(lines):
                inner = lines[i]
                if inner.rstrip().endswith('"'):
                    collected.append(inner.rstrip()[:-1])
                    break
                collected.append(inner)
                i += 1
            result[key] = "\n".join(collected).replace('\\"', '"').replace("\\\\", "\\")
            i += 1
            continue
        if raw_value.startswith("'"):
            collected = [raw_value[1:]]
            i += 1
            while i < len(lines):
                inner = lines[i]
                if inner.rstrip().endswith("'"):
                    collected.append(inner.rstrip()[:-1])
                    break
                collected.append(inner)
                i += 1
            result[key] = "\n".join(collected)
            i += 1
            continue
        result[key] = raw_value
        i += 1
    return result


def load_env(env_path: Path | None = None) -> dict[str, str]:
    path = Path(env_path) if env_path is not None else get_env_path()
    parsed = _parse_env_file(path)
    loaded: dict[str, str] = {}
    for key, value in parsed.items():
        os.environ[key] = value
        loaded[key] = value
    return loaded


def reload_env() -> dict[str, str]:
    return load_env()


def get_env_diff() -> dict[str, dict[str, str]]:
    parsed = _parse_env_file(get_env_path())
    diff: dict[str, dict[str, str]] = {}
    for key, file_value in parsed.items():
        current = os.environ.get(key)
        if current != file_value:
            diff[key] = {
                "current": current if current is not None else "",
                "file": file_value,
            }
    for key in os.environ:
        if key not in parsed and key.startswith(("PROMETHEUS_", "OPENAI_", "ANTHROPIC_")):
            diff[key] = {
                "current": os.environ[key],
                "file": "",
            }
    return diff


def list_env_vars(prefix: str = "") -> list[Tuple[str, str]]:
    if prefix:
        return [(k, v) for k, v in sorted(os.environ.items()) if k.startswith(prefix)]
    return [(k, v) for k, v in sorted(os.environ.items())]
