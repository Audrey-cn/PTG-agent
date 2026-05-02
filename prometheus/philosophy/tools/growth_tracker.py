#!/usr/bin/env python3
"""
生长追踪器

三阶段培育追踪：rooting → sprouting → blooming。
记录使用日志、创新、自动评分。
"""

from __future__ import annotations

import json
import os
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class GrowthTracker:
    """追踪种子从生根到开花的过程"""

    PHASES = ["rooting", "sprouting", "blooming"]

    def __init__(self, seed_id: str, log_dir: str = "~/.prometheus/seedling-logs"):
        self.seed_id = seed_id
        self.log_dir = os.path.expanduser(log_dir)
        self.current_phase = "rooting"
        self.phase_start_dates = {"rooting": datetime.datetime.now().isoformat()}
        os.makedirs(self.log_dir, exist_ok=True)

    def log_usage(self, context: str, felt_good: List[str] = None,
                  felt_awkward: List[str] = None, wish_for: List[str] = None,
                  satisfaction: int = 5) -> dict:
        entry = {
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "phase": self.current_phase,
            "usage_context": context,
            "felt_good": felt_good or [],
            "felt_awkward": felt_awkward or [],
            "wish_for": wish_for or [],
            "satisfaction": satisfaction,
        }
        self._save_entry(entry)
        self._check_phase_transition()
        return entry

    def log_innovation(self, name: str, reason: str,
                       implementation: str, effect: str) -> dict:
        innovation = {
            "id": self._gen_innovation_id(),
            "name": name,
            "reason": reason,
            "implementation": implementation,
            "effect": effect,
            "date": datetime.datetime.now().isoformat(),
            "phase": self.current_phase,
        }
        self._save_innovation(innovation)
        return innovation

    def calculate_score(self) -> dict:
        logs = self._load_logs()
        if not logs:
            return {"score": 0, "phase": self.current_phase, "message": "暂无使用记录"}

        avg = sum(l.get("satisfaction", 5) for l in logs) / len(logs)
        adapt = sum(1 for l in logs if l.get("felt_good")) / max(len(logs), 1)
        innovations = len(self._load_innovations())
        score = avg * 40 + adapt * 40 + min(innovations * 5, 20)

        if score < 40:
            hint = "建议回到生根阶段，重新理解技能灵魂"
        elif score < 70:
            hint = "生长良好，可以尝试个性化调整"
        elif score < 90:
            hint = "技能已融入环境，鼓励创新尝试"
        else:
            hint = "技能生长旺盛，请考虑打包新种子分享"

        return {
            "score": round(score, 1),
            "phase": self.current_phase,
            "avg_satisfaction": round(avg, 1),
            "total_logs": len(logs),
            "innovations": innovations,
            "suggestion": hint,
        }

    def advance_phase(self) -> str:
        idx = self.PHASES.index(self.current_phase)
        if idx < len(self.PHASES) - 1:
            self.current_phase = self.PHASES[idx + 1]
            self.phase_start_dates[self.current_phase] = datetime.datetime.now().isoformat()
        return self.current_phase

    def _check_phase_transition(self):
        logs = self._load_logs()
        innovs = self._load_innovations()
        if self.current_phase == "rooting" and len(logs) >= 5:
            self.advance_phase()
        elif self.current_phase == "sprouting" and len(innovs) >= 1:
            self.advance_phase()

    def _save_entry(self, entry: dict):
        fp = os.path.join(self.log_dir, f"{self.seed_id}_log.jsonl")
        with open(fp, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def _save_innovation(self, innovation: dict):
        fp = os.path.join(self.log_dir, f"{self.seed_id}_innov.jsonl")
        with open(fp, 'a', encoding='utf-8') as f:
            f.write(json.dumps(innovation, ensure_ascii=False) + '\n')

    def _load_logs(self) -> list:
        fp = os.path.join(self.log_dir, f"{self.seed_id}_log.jsonl")
        if not os.path.exists(fp):
            return []
        logs = []
        with open(fp, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    logs.append(json.loads(line.strip()))
                except Exception:
                    pass
        return logs

    def _load_innovations(self) -> list:
        fp = os.path.join(self.log_dir, f"{self.seed_id}_innov.jsonl")
        if not os.path.exists(fp):
            return []
        innovs = []
        with open(fp, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    innovs.append(json.loads(line.strip()))
                except Exception:
                    pass
        return innovs

    def _gen_innovation_id(self) -> str:
        return f"INNOV-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
