"""Session Insights Engine for Prometheus."""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from prometheus._paths import get_paths
from prometheus.agent.usage_pricing import (
    DEFAULT_PRICING,
    CanonicalUsage,
    estimate_usage_cost,
    format_duration_compact,
    has_known_pricing,
)

_DEFAULT_PRICING = DEFAULT_PRICING


def _has_known_pricing(model_name: str, provider: str = None, base_url: str = None) -> bool:
    """Check if a model has known pricing (vs unknown/custom endpoint)."""
    return has_known_pricing(model_name, provider=provider, base_url=base_url)


def _estimate_cost(
    session_or_model: dict[str, Any] | str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    *,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    provider: str = None,
    base_url: str = None,
) -> Tuple[float, str]:
    """Estimate the USD cost for a session row or a model/token tuple."""
    if isinstance(session_or_model, dict):
        session = session_or_model
        model = session.get("model") or ""
        usage = CanonicalUsage(
            input_tokens=session.get("input_tokens") or 0,
            output_tokens=session.get("output_tokens") or 0,
            cache_read_tokens=session.get("cache_read_tokens") or 0,
            cache_write_tokens=session.get("cache_write_tokens") or 0,
        )
        provider = session.get("billing_provider")
        base_url = session.get("billing_base_url")
    else:
        model = session_or_model or ""
        usage = CanonicalUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
        )
    result = estimate_usage_cost(
        model,
        usage,
        provider=provider,
        base_url=base_url,
    )
    return float(result.amount_usd or 0.0), result.status


def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    return format_duration_compact(seconds)


def _bar_chart(values: list[int], max_width: int = 20) -> list[str]:
    """Create simple horizontal bar chart strings from values."""
    peak = max(values) if values else 1
    if peak == 0:
        return ["" for _ in values]
    return ["█" * max(1, int(v / peak * max_width)) if v > 0 else "" for v in values]


class InsightsEngine:
    """
    Analyzes session history and produces usage insights.

    Works with session data stored in the Prometheus data directory.
    """

    def __init__(self, db_path: str | None = None):
        """
        Initialize the insights engine.

        Args:
            db_path: Optional path to the session database
        """
        self._db_path = db_path or str(get_paths().data / "sessions.db")
        self._sessions: list[dict[str, Any]] = []
        self._load_sessions()

    def _load_sessions(self):
        """Load sessions from storage."""
        try:
            import sqlite3

            if not self._db_path or not sqlite3.connect(self._db_path):
                self._sessions = []
                return

            conn = sqlite3.connect(self._db_path)
            cursor = conn.execute(
                "SELECT id, source, model, started_at, ended_at, message_count, "
                "tool_call_count, input_tokens, output_tokens, cache_read_tokens, "
                "cache_write_tokens FROM sessions ORDER BY started_at DESC LIMIT 1000"
            )

            self._sessions = []
            for row in cursor.fetchall():
                self._sessions.append(
                    {
                        "id": row[0],
                        "source": row[1],
                        "model": row[2],
                        "started_at": row[3],
                        "ended_at": row[4],
                        "message_count": row[5],
                        "tool_call_count": row[6],
                        "input_tokens": row[7],
                        "output_tokens": row[8],
                        "cache_read_tokens": row[9],
                        "cache_write_tokens": row[10],
                    }
                )
            conn.close()
        except Exception:
            self._sessions = []

    def generate(self, days: int = 30, source: str = None) -> dict[str, Any]:
        """
        Generate a complete insights report.

        Args:
            days: Number of days to look back (default: 30)
            source: Optional filter by source platform

        Returns:
            Dict with all computed insights
        """
        cutoff = time.time() - (days * 86400)

        sessions = self._get_sessions(cutoff, source)

        if not sessions:
            return {
                "days": days,
                "source_filter": source,
                "empty": True,
                "overview": {},
                "models": [],
                "platforms": [],
                "tools": [],
                "skills": {
                    "summary": {
                        "total_skill_loads": 0,
                        "total_skill_edits": 0,
                        "total_skill_actions": 0,
                        "distinct_skills_used": 0,
                    },
                    "top_skills": [],
                },
                "activity": {},
                "top_sessions": [],
            }

        overview = self._compute_overview(sessions)
        models = self._compute_model_breakdown(sessions)
        platforms = self._compute_platform_breakdown(sessions)
        tools = self._compute_tool_breakdown(sessions)
        skills = self._compute_skill_breakdown(sessions)
        activity = self._compute_activity_patterns(sessions)
        top_sessions = self._compute_top_sessions(sessions)

        return {
            "days": days,
            "source_filter": source,
            "empty": False,
            "generated_at": time.time(),
            "overview": overview,
            "models": models,
            "platforms": platforms,
            "tools": tools,
            "skills": skills,
            "activity": activity,
            "top_sessions": top_sessions,
        }

    def _get_sessions(self, cutoff: float, source: str = None) -> list[dict]:
        """Fetch sessions within the time window."""
        if source:
            return [
                s
                for s in self._sessions
                if s.get("source") == source and s.get("started_at", 0) >= cutoff
            ]
        return [s for s in self._sessions if s.get("started_at", 0) >= cutoff]

    def _compute_overview(self, sessions: list[dict]) -> dict[str, Any]:
        """Compute overall statistics."""
        total_tokens = sum(
            (s.get("input_tokens", 0) or 0) + (s.get("output_tokens", 0) or 0) for s in sessions
        )
        total_cost = sum(_estimate_cost(s)[0] for s in sessions)
        total_duration = sum(
            (s.get("ended_at", 0) or 0) - (s.get("started_at", 0) or 0) for s in sessions
        )

        return {
            "session_count": len(sessions),
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(total_cost, 4),
            "total_duration_seconds": total_duration,
            "avg_tokens_per_session": total_tokens // len(sessions) if sessions else 0,
            "avg_cost_per_session": round(total_cost / len(sessions), 4) if sessions else 0,
        }

    def _compute_model_breakdown(self, sessions: list[dict]) -> list[dict]:
        """Compute per-model statistics."""
        model_stats: dict[str, dict] = defaultdict(
            lambda: {
                "sessions": 0,
                "tokens": 0,
                "cost": 0.0,
            }
        )

        for s in sessions:
            model = s.get("model") or "unknown"
            tokens = (s.get("input_tokens", 0) or 0) + (s.get("output_tokens", 0) or 0)
            cost, _ = _estimate_cost(s)

            model_stats[model]["sessions"] += 1
            model_stats[model]["tokens"] += tokens
            model_stats[model]["cost"] += cost

        return [
            {
                "model": model,
                "sessions": stats["sessions"],
                "tokens": stats["tokens"],
                "estimated_cost_usd": round(stats["cost"], 4),
            }
            for model, stats in sorted(
                model_stats.items(), key=lambda x: x[1]["tokens"], reverse=True
            )
        ]

    def _compute_platform_breakdown(self, sessions: list[dict]) -> list[dict]:
        """Compute per-platform statistics."""
        platform_stats: dict[str, dict] = defaultdict(
            lambda: {
                "sessions": 0,
                "tokens": 0,
            }
        )

        for s in sessions:
            platform = s.get("source") or "unknown"
            tokens = (s.get("input_tokens", 0) or 0) + (s.get("output_tokens", 0) or 0)

            platform_stats[platform]["sessions"] += 1
            platform_stats[platform]["tokens"] += tokens

        return [
            {
                "platform": platform,
                "sessions": stats["sessions"],
                "tokens": stats["tokens"],
            }
            for platform, stats in sorted(
                platform_stats.items(), key=lambda x: x[1]["sessions"], reverse=True
            )
        ]

    def _compute_tool_breakdown(self, sessions: list[dict]) -> list[dict]:
        """Compute tool usage statistics."""
        tool_counts: dict[str, int] = Counter()

        for s in sessions:
            tool_calls = s.get("tool_call_count", 0) or 0
            if tool_calls > 0:
                tool_counts["tool_call"] += tool_calls

        return [{"tool": tool, "count": count} for tool, count in tool_counts.most_common(20)]

    def _compute_skill_breakdown(self, sessions: list[dict]) -> dict[str, Any]:
        """Compute skill usage statistics."""
        return {
            "summary": {
                "total_skill_loads": 0,
                "total_skill_edits": 0,
                "total_skill_actions": 0,
                "distinct_skills_used": 0,
            },
            "top_skills": [],
        }

    def _compute_activity_patterns(self, sessions: list[dict]) -> dict[str, Any]:
        """Compute activity patterns over time."""
        daily_counts: dict[str, int] = defaultdict(int)

        for s in sessions:
            started = s.get("started_at")
            if started:
                day = datetime.fromtimestamp(started).strftime("%Y-%m-%d")
                daily_counts[day] += 1

        return {
            "daily_sessions": dict(sorted(daily_counts.items())),
        }

    def _compute_top_sessions(self, sessions: list[dict]) -> list[dict]:
        """Compute top sessions by token usage."""
        sorted_sessions = sorted(
            sessions,
            key=lambda s: (s.get("input_tokens", 0) or 0) + (s.get("output_tokens", 0) or 0),
            reverse=True,
        )

        return [
            {
                "id": s.get("id"),
                "model": s.get("model"),
                "tokens": (s.get("input_tokens", 0) or 0) + (s.get("output_tokens", 0) or 0),
                "duration_seconds": (s.get("ended_at", 0) or 0) - (s.get("started_at", 0) or 0),
            }
            for s in sorted_sessions[:10]
        ]

    def format_terminal(self, report: dict[str, Any]) -> str:
        """Format insights report for terminal display."""
        if report.get("empty"):
            return "No session data available for the specified period."

        lines = []
        lines.append("\n" + "=" * 60)
        lines.append("PROMETHEUS INSIGHTS REPORT")
        lines.append("=" * 60)

        overview = report.get("overview", {})
        lines.append(f"\n📊 OVERVIEW (Last {report['days']} days)")
        lines.append(f"  Sessions: {overview.get('session_count', 0)}")
        lines.append(f"  Total Tokens: {overview.get('total_tokens', 0):,}")
        lines.append(f"  Estimated Cost: ${overview.get('estimated_cost_usd', 0):.4f}")
        lines.append(f"  Avg Tokens/Session: {overview.get('avg_tokens_per_session', 0):,}")

        models = report.get("models", [])
        if models:
            lines.append("\n🤖 TOP MODELS")
            for m in models[:5]:
                lines.append(
                    f"  {m['model']}: {m['tokens']:,} tokens, ${m.get('estimated_cost_usd', 0):.4f}"
                )

        platforms = report.get("platforms", [])
        if platforms:
            lines.append("\n💻 PLATFORMS")
            for p in platforms[:5]:
                lines.append(f"  {p['platform']}: {p['sessions']} sessions")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)
