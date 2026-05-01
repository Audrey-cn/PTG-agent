from __future__ import annotations

import json
import time
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from collections import defaultdict

from prometheus.config import get_prometheus_home


@dataclass
class UsageRecord:
    timestamp: float
    model: str
    provider: str
    tokens_in: int = 0
    tokens_out: int = 0
    tool_calls: int = 0
    session_id: str = ""


class UsageTracker:
    def __init__(self, storage_dir: Path | None = None):
        self.storage_dir = storage_dir or get_prometheus_home() / "usage"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._records: list[UsageRecord] = []
        self._lock = threading.Lock()
        self._session_totals: dict[str, dict] = defaultdict(lambda: {
            "tokens_in": 0, "tokens_out": 0, "tool_calls": 0, "requests": 0,
        })

    def record(self, model: str, provider: str = "", tokens_in: int = 0,
               tokens_out: int = 0, tool_calls: int = 0, session_id: str = ""):
        rec = UsageRecord(
            timestamp=time.time(),
            model=model,
            provider=provider,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            tool_calls=tool_calls,
            session_id=session_id,
        )
        with self._lock:
            self._records.append(rec)
            key = session_id or "default"
            self._session_totals[key]["tokens_in"] += tokens_in
            self._session_totals[key]["tokens_out"] += tokens_out
            self._session_totals[key]["tool_calls"] += tool_calls
            self._session_totals[key]["requests"] += 1

    def get_session_usage(self, session_id: str = "default") -> dict:
        with self._lock:
            return dict(self._session_totals.get(session_id, {
                "tokens_in": 0, "tokens_out": 0, "tool_calls": 0, "requests": 0,
            }))

    def get_total_usage(self) -> dict:
        with self._lock:
            total = {"tokens_in": 0, "tokens_out": 0, "tool_calls": 0, "requests": 0, "sessions": 0}
            for sid, data in self._session_totals.items():
                for k in ("tokens_in", "tokens_out", "tool_calls", "requests"):
                    total[k] += data[k]
                total["sessions"] += 1
            return total

    def get_daily_usage(self, days: int = 7) -> list[dict]:
        now = time.time()
        cutoff = now - (days * 86400)
        with self._lock:
            daily: dict[str, dict] = {}
            for rec in self._records:
                if rec.timestamp < cutoff:
                    continue
                day = time.strftime("%Y-%m-%d", time.localtime(rec.timestamp))
                if day not in daily:
                    daily[day] = {"date": day, "tokens_in": 0, "tokens_out": 0, "tool_calls": 0, "requests": 0}
                daily[day]["tokens_in"] += rec.tokens_in
                daily[day]["tokens_out"] += rec.tokens_out
                daily[day]["tool_calls"] += rec.tool_calls
                daily[day]["requests"] += 1
            return sorted(daily.values(), key=lambda x: x["date"])

    def estimate_cost(self, model: str = "", provider: str = "") -> dict:
        PRICING = {
            "gpt-4o": {"in": 2.50, "out": 10.00},
            "gpt-4o-mini": {"in": 0.15, "out": 0.60},
            "gpt-4-turbo": {"in": 10.00, "out": 30.00},
            "claude-3.5-sonnet": {"in": 3.00, "out": 15.00},
            "claude-3-opus": {"in": 15.00, "out": 75.00},
            "deepseek-chat": {"in": 0.14, "out": 0.28},
            "deepseek-v3": {"in": 0.27, "out": 1.10},
        }
        total = self.get_total_usage()
        pricing = PRICING.get(model, PRICING.get("gpt-4o", {"in": 2.50, "out": 10.00}))
        cost_in = (total["tokens_in"] / 1_000_000) * pricing["in"]
        cost_out = (total["tokens_out"] / 1_000_000) * pricing["out"]
        return {
            "total_tokens": total["tokens_in"] + total["tokens_out"],
            "estimated_cost_usd": round(cost_in + cost_out, 4),
            "breakdown": {
                "input_cost": round(cost_in, 4),
                "output_cost": round(cost_out, 4),
                "pricing_per_mtok": pricing,
            },
        }

    def save(self):
        with self._lock:
            filepath = self.storage_dir / f"usage_{time.strftime('%Y%m%d')}.json"
            data = {
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total": self.get_total_usage(),
                "records": [
                    {
                        "timestamp": r.timestamp,
                        "model": r.model,
                        "provider": r.provider,
                        "tokens_in": r.tokens_in,
                        "tokens_out": r.tokens_out,
                        "tool_calls": r.tool_calls,
                    }
                    for r in self._records[-1000:]
                ],
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)


_global_tracker: UsageTracker | None = None


def get_usage_tracker() -> UsageTracker:
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = UsageTracker()
    return _global_tracker
