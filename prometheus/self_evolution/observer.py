#!/usr/bin/env python3
"""
观察者模块 - 记录观察到的模式
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class Observer:
    """观察者类"""

    def __init__(self, memory_dir: Path):
        self.memory_dir = memory_dir
        self.observations_file = memory_dir / "observations.jsonl"

    def record(
        self, pattern_type: str, content: str, context: str = "", confidence: float = 0.5
    ) -> dict[str, Any]:
        """记录一个观察"""
        observation = {
            "timestamp": datetime.now(UTC).isoformat(),
            "type": pattern_type,
            "content": content,
            "context": context,
            "confidence": confidence,
        }

        # 追加到文件
        with open(self.observations_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(observation, ensure_ascii=False) + "\n")

        return {"success": True, "observation": observation}

    def get_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        """获取最近的观察"""
        if not self.observations_file.exists():
            return []

        observations = []
        with open(self.observations_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        observations.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        return observations[-limit:]

    def count(self) -> int:
        """统计观察数量"""
        if not self.observations_file.exists():
            return 0

        count = 0
        with open(self.observations_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1

        return count
