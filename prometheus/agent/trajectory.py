"""Trajectory Storage and Analysis for Prometheus."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from prometheus._paths import get_paths

logger = logging.getLogger("prometheus.trajectory")


def _normalize_scratchpad_tags(content: str) -> str:
    """Normalize scratchpad tags between formats.

    Converts between <REASONING_SCRATCHPAD> and <think> tags.
    """
    if not content or "<REASONING_SCRATCHPAD>" not in content:
        return content
    return content.replace("<REASONING_SCRATCHPAD>", "<think>").replace(
        "</REASONING_SCRATCHPAD>", "</think>"
    )


def has_incomplete_scratchpad(content: str) -> bool:
    """Check if content has an opening <REASONING_SCRATCHPAD> without a closing tag."""
    if not content:
        return False
    return "<REASONING_SCRATCHPAD>" in content and "</REASONING_SCRATCHPAD>" not in content


def save_trajectory(
    trajectory: list[dict[str, Any]], model: str, completed: bool, filename: str = None
):
    """Append a trajectory entry to a JSONL file.

    Args:
        trajectory: The ShareGPT-format conversation list.
        model: Model name for metadata.
        completed: Whether the conversation completed successfully.
        filename: Override output filename. Defaults to trajectory_samples.jsonl
                  or failed_trajectories.jsonl based on ``completed``.
    """
    if filename is None:
        filename = "trajectory_samples.jsonl" if completed else "failed_trajectories.jsonl"

    entry = {
        "conversations": trajectory,
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "completed": completed,
    }

    try:
        traj_dir = get_paths().trajectories
        traj_dir.mkdir(parents=True, exist_ok=True)
        filepath = traj_dir / filename

        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info("Trajectory saved to %s", filepath)
    except Exception as e:
        logger.warning("Failed to save trajectory: %s", e)


def load_trajectories(
    filename: str = "trajectory_samples.jsonl", limit: int = 100
) -> list[dict[str, Any]]:
    """Load trajectories from a JSONL file.

    Args:
        filename: The trajectory file to load.
        limit: Maximum number of trajectories to load.

    Returns:
        List of trajectory entries.
    """
    try:
        filepath = get_paths().trajectories / filename
        if not filepath.exists():
            return []

        trajectories = []
        with open(filepath, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= limit:
                    break
                try:
                    trajectories.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue

        return trajectories

    except Exception as e:
        logger.warning("Failed to load trajectories: %s", e)
        return []


def load_failed_trajectories(limit: int = 50) -> list[dict[str, Any]]:
    """Load failed trajectories for analysis."""
    return load_trajectories(filename="failed_trajectories.jsonl", limit=limit)


def analyze_trajectory(trajectory: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze a single trajectory for statistics.

    Args:
        trajectory: The ShareGPT-format conversation list.

    Returns:
        Dict containing trajectory statistics.
    """
    if not trajectory:
        return {
            "turn_count": 0,
            "total_messages": 0,
            "tool_calls": 0,
            "total_tokens_estimate": 0,
            "has_reasoning": False,
            "has_incomplete_scratchpad": False,
        }

    turn_count = 0
    total_messages = len(trajectory)
    tool_calls = 0
    total_chars = 0
    has_reasoning = False
    has_incomplete_scratchpad = False

    for msg in trajectory:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if isinstance(content, str):
            total_chars += len(content)

            if "<think>" in content or "<REASONING_SCRATCHPAD>" in content:
                has_reasoning = True

            if has_incomplete_scratchpad(content):
                has_incomplete_scratchpad = True

        if role == "assistant":
            turn_count += 1

            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_calls += 1

    return {
        "turn_count": turn_count,
        "total_messages": total_messages,
        "tool_calls": tool_calls,
        "total_tokens_estimate": total_chars // 4,
        "has_reasoning": has_reasoning,
        "has_incomplete_scratchpad": has_incomplete_scratchpad,
    }


def get_trajectory_stats() -> dict[str, Any]:
    """Get overall trajectory statistics.

    Returns:
        Dict with aggregated statistics across all trajectories.
    """
    successful = load_trajectories(limit=1000)
    failed = load_failed_trajectories(limit=1000)

    stats = {
        "successful_count": len(successful),
        "failed_count": len(failed),
        "total_count": len(successful) + len(failed),
    }

    if successful:
        sample_analysis = analyze_trajectory(successful[0])
        stats["sample_analysis"] = sample_analysis

    return stats


class TrajectoryRecorder:
    """Context manager for recording trajectories."""

    def __init__(self, model: str, completed: bool = True, output_file: str | None = None):
        self.model = model
        self.completed = completed
        self.output_file = output_file
        self.trajectory: list[dict[str, Any]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.completed = False

        if self.trajectory:
            save_trajectory(self.trajectory, self.model, self.completed, self.output_file)

        return False

    def add_turn(self, role: str, content: Any):
        """Add a turn to the trajectory."""
        if isinstance(content, list):
            self.trajectory.append({"role": role, "content": content})
        else:
            self.trajectory.append({"role": role, "content": str(content)})

    def add_message(self, message: dict[str, Any]):
        """Add a complete message to the trajectory."""
        self.trajectory.append(message)
