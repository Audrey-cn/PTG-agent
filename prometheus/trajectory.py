from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def convert_to_sharegpt(messages: list[Dict[str, Any]]) -> list[Dict[str, str]]:
    result = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            result.append({"from": "human", "value": content})
        elif role == "assistant":
            result.append({"from": "gpt", "value": content})
        elif role == "system":
            result.append({"from": "system", "value": content})
    return result


def save_trajectory(
    trajectory: list[Dict[str, Any]],
    model: str,
    completed: bool,
    filename: Optional[str] = None,
) -> Path:
    if filename is None:
        filename = f"trajectory_{model}_{id(trajectory)}.json"
    path = Path(filename)
    data = {
        "model": model,
        "completed": completed,
        "messages": trajectory,
        "sharegpt": convert_to_sharegpt(trajectory),
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return path


def load_trajectory(filename: str) -> list[Dict[str, Any]]:
    path = Path(filename)
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return data.get("messages", [])


def merge_trajectories(files: List[str]) -> list[Dict[str, Any]]:
    merged = []
    seen = set()
    for f in files:
        trajectory = load_trajectory(f)
        for msg in trajectory:
            key = (msg.get("role"), msg.get("content"))
            if key not in seen:
                seen.add(key)
                merged.append(msg)
    return merged


def filter_trajectory(
    trajectory: list[Dict[str, Any]],
    role: Optional[str] = None,
) -> list[Dict[str, Any]]:
    if role is None:
        return trajectory
    return [msg for msg in trajectory if msg.get("role") == role]
