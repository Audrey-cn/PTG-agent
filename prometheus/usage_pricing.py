from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from prometheus.config import get_prometheus_home
from prometheus.model_metadata import get_model_metadata

PRICING_TIERS: Dict[str, Dict[str, Any]] = {
    "openai": {
        "tier1": {"input_multiplier": 1.0, "output_multiplier": 1.0},
        "tier2": {"input_multiplier": 0.8, "output_multiplier": 0.8},
        "tier3": {"input_multiplier": 0.6, "output_multiplier": 0.6},
    },
    "anthropic": {
        "tier1": {"input_multiplier": 1.0, "output_multiplier": 1.0},
        "tier2": {"input_multiplier": 0.85, "output_multiplier": 0.85},
        "tier3": {"input_multiplier": 0.7, "output_multiplier": 0.7},
    },
    "google": {
        "tier1": {"input_multiplier": 1.0, "output_multiplier": 1.0},
        "tier2": {"input_multiplier": 0.75, "output_multiplier": 0.75},
    },
    "deepseek": {
        "tier1": {"input_multiplier": 1.0, "output_multiplier": 1.0},
    },
    "xai": {
        "tier1": {"input_multiplier": 1.0, "output_multiplier": 1.0},
    },
    "meta": {
        "tier1": {"input_multiplier": 1.0, "output_multiplier": 1.0},
    },
    "mistral": {
        "tier1": {"input_multiplier": 1.0, "output_multiplier": 1.0},
    },
    "cohere": {
        "tier1": {"input_multiplier": 1.0, "output_multiplier": 1.0},
    },
}


class UsagePricer:
    def __init__(self) -> None:
        self._usage_dir = get_prometheus_home() / "usage"
        self._usage_dir.mkdir(parents=True, exist_ok=True)
        self._current_tier: str = "tier1"

    def set_pricing_tier(self, tier: str) -> None:
        self._current_tier = tier

    def calculate_cost(self, tokens_in: int, tokens_out: int, model: str) -> float:
        metadata = get_model_metadata(model)
        if not metadata:
            return 0.0

        provider = metadata.provider
        tier_multipliers = PRICING_TIERS.get(provider, {}).get(
            self._current_tier, {"input_multiplier": 1.0, "output_multiplier": 1.0}
        )

        input_multiplier = tier_multipliers.get("input_multiplier", 1.0)
        output_multiplier = tier_multipliers.get("output_multiplier", 1.0)

        input_cost = (tokens_in / 1_000_000) * metadata.pricing_input * input_multiplier
        output_cost = (tokens_out / 1_000_000) * metadata.pricing_output * output_multiplier

        return round(input_cost + output_cost, 6)

    def estimate_session_cost(self, session_id: str) -> float:
        session_file = self._usage_dir / f"{session_id}.json"
        if not session_file.exists():
            return 0.0

        try:
            with open(session_file) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return 0.0

        total_cost = 0.0
        for entry in data.get("requests", []):
            tokens_in = entry.get("tokens_in", 0)
            tokens_out = entry.get("tokens_out", 0)
            model = entry.get("model", "")
            total_cost += self.calculate_cost(tokens_in, tokens_out, model)

        return round(total_cost, 6)

    def get_pricing_tier(self, model: str) -> Dict[str, Any]:
        metadata = get_model_metadata(model)
        if not metadata:
            return {"tier": self._current_tier, "multipliers": {"input": 1.0, "output": 1.0}}

        provider = metadata.provider
        tier_data = PRICING_TIERS.get(provider, {}).get(
            self._current_tier, {"input_multiplier": 1.0, "output_multiplier": 1.0}
        )

        return {
            "tier": self._current_tier,
            "multipliers": {
                "input": tier_data.get("input_multiplier", 1.0),
                "output": tier_data.get("output_multiplier", 1.0),
            },
            "base_pricing": {
                "input": metadata.pricing_input,
                "output": metadata.pricing_output,
            },
        }

    def format_cost(self, cost: float) -> str:
        if cost < 0.0001:
            return f"${cost:.8f}"
        elif cost < 0.01:
            return f"${cost:.6f}"
        elif cost < 1.0:
            return f"${cost:.4f}"
        else:
            return f"${cost:.2f}"

    def record_usage(self, session_id: str, model: str, tokens_in: int, tokens_out: int) -> float:
        session_file = self._usage_dir / f"{session_id}.json"

        cost = self.calculate_cost(tokens_in, tokens_out, model)

        try:
            if session_file.exists():
                with open(session_file) as f:
                    data = json.load(f)
            else:
                data = {
                    "session_id": session_id,
                    "created_at": datetime.now().isoformat(),
                    "requests": [],
                }

            data["requests"].append(
                {
                    "model": model,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "cost": cost,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            data["total_cost"] = sum(r.get("cost", 0) for r in data["requests"])
            data["updated_at"] = datetime.now().isoformat()

            with open(session_file, "w") as f:
                json.dump(data, f, indent=2)

        except (OSError, json.JSONDecodeError):
            pass

        return cost

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        session_file = self._usage_dir / f"{session_id}.json"
        if not session_file.exists():
            return {"session_id": session_id, "total_cost": 0.0, "requests": []}

        try:
            with open(session_file) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"session_id": session_id, "total_cost": 0.0, "requests": []}
