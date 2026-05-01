from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta
from typing import Any

from prometheus.config import get_prometheus_home


class Insights:
    def __init__(self) -> None:
        self._insights_dir = get_prometheus_home() / "insights"
        self._insights_dir.mkdir(parents=True, exist_ok=True)
        self._current_session: Dict[str, Any] = {
            "requests": [],
            "start_time": datetime.now().isoformat(),
        }

    def record_request(
        self,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency: float,
        success: bool,
        cost: float | None = None,
    ) -> None:
        from prometheus.usage_pricing import UsagePricer

        if cost is None:
            pricer = UsagePricer()
            cost = pricer.calculate_cost(tokens_in, tokens_out, model)

        request_data = {
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency": latency,
            "success": success,
            "cost": cost,
            "timestamp": datetime.now().isoformat(),
        }

        self._current_session["requests"].append(request_data)
        self._persist_request(request_data)

    def _persist_request(self, request_data: Dict[str, Any]) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        daily_file = self._insights_dir / f"{today}.json"

        try:
            if daily_file.exists():
                with open(daily_file) as f:
                    data = json.load(f)
            else:
                data = {"date": today, "requests": []}

            data["requests"].append(request_data)
            data["updated_at"] = datetime.now().isoformat()

            with open(daily_file, "w") as f:
                json.dump(data, f, indent=2)
        except (OSError, json.JSONDecodeError):
            pass

    def get_daily_summary(self, date: Optional[str] = None) -> Dict[str, Any]:
        target_date = date or datetime.now().strftime("%Y-%m-%d")
        daily_file = self._insights_dir / f"{target_date}.json"

        if not daily_file.exists():
            return {
                "date": target_date,
                "total_requests": 0,
                "successful_requests": 0,
                "total_tokens_in": 0,
                "total_tokens_out": 0,
                "total_cost": 0.0,
                "avg_latency": 0.0,
            }

        try:
            with open(daily_file) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {
                "date": target_date,
                "total_requests": 0,
                "successful_requests": 0,
                "total_tokens_in": 0,
                "total_tokens_out": 0,
                "total_cost": 0.0,
                "avg_latency": 0.0,
            }

        requests = data.get("requests", [])
        if not requests:
            return {
                "date": target_date,
                "total_requests": 0,
                "successful_requests": 0,
                "total_tokens_in": 0,
                "total_tokens_out": 0,
                "total_cost": 0.0,
                "avg_latency": 0.0,
            }

        successful = [r for r in requests if r.get("success", False)]
        latencies = [r.get("latency", 0) for r in requests]

        return {
            "date": target_date,
            "total_requests": len(requests),
            "successful_requests": len(successful),
            "total_tokens_in": sum(r.get("tokens_in", 0) for r in requests),
            "total_tokens_out": sum(r.get("tokens_out", 0) for r in requests),
            "total_cost": sum(r.get("cost", 0) for r in requests),
            "avg_latency": round(statistics.mean(latencies), 3) if latencies else 0.0,
        }

    def get_model_distribution(self, days: int = 7) -> Dict[str, Any]:
        distribution: Dict[str, Dict[str, Any]] = {}
        start_date = datetime.now() - timedelta(days=days)

        for i in range(days):
            date = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
            daily_file = self._insights_dir / f"{date}.json"

            if not daily_file.exists():
                continue

            try:
                with open(daily_file) as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue

            for request in data.get("requests", []):
                model = request.get("model", "unknown")
                if model not in distribution:
                    distribution[model] = {
                        "count": 0,
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "cost": 0.0,
                    }

                distribution[model]["count"] += 1
                distribution[model]["tokens_in"] += request.get("tokens_in", 0)
                distribution[model]["tokens_out"] += request.get("tokens_out", 0)
                distribution[model]["cost"] += request.get("cost", 0)

        return distribution

    def get_cost_trend(self, days: int = 7) -> list[Dict[str, Any]]:
        trend = []
        start_date = datetime.now() - timedelta(days=days - 1)

        for i in range(days):
            date = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
            summary = self.get_daily_summary(date)
            trend.append(
                {
                    "date": date,
                    "cost": summary["total_cost"],
                    "requests": summary["total_requests"],
                }
            )

        return trend

    def get_latency_stats(self, days: int = 7) -> Dict[str, Any]:
        latencies: list[float] = []
        model_latencies: Dict[str, list[float]] = {}
        start_date = datetime.now() - timedelta(days=days)

        for i in range(days):
            date = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
            daily_file = self._insights_dir / f"{date}.json"

            if not daily_file.exists():
                continue

            try:
                with open(daily_file) as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue

            for request in data.get("requests", []):
                latency = request.get("latency", 0)
                model = request.get("model", "unknown")

                latencies.append(latency)
                if model not in model_latencies:
                    model_latencies[model] = []
                model_latencies[model].append(latency)

        if not latencies:
            return {
                "avg": 0.0,
                "min": 0.0,
                "max": 0.0,
                "median": 0.0,
                "p95": 0.0,
                "by_model": {},
            }

        sorted_latencies = sorted(latencies)
        p95_index = int(len(sorted_latencies) * 0.95)

        return {
            "avg": round(statistics.mean(latencies), 3),
            "min": round(min(latencies), 3),
            "max": round(max(latencies), 3),
            "median": round(statistics.median(latencies), 3),
            "p95": round(sorted_latencies[min(p95_index, len(sorted_latencies) - 1)], 3),
            "by_model": {
                model: round(statistics.mean(lats), 3)
                for model, lats in model_latencies.items()
                if lats
            },
        }

    def export_insights(self, format: str = "json", days: int = 30) -> str:
        start_date = datetime.now() - timedelta(days=days)
        all_data: Dict[str, Any] = {
            "export_date": datetime.now().isoformat(),
            "period_days": days,
            "daily_summaries": [],
            "model_distribution": self.get_model_distribution(days),
            "cost_trend": self.get_cost_trend(days),
            "latency_stats": self.get_latency_stats(days),
        }

        for i in range(days):
            date = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
            summary = self.get_daily_summary(date)
            if summary["total_requests"] > 0:
                all_data["daily_summaries"].append(summary)

        if format == "json":
            return json.dumps(all_data, indent=2)
        else:
            return json.dumps(all_data, indent=2)

    def get_session_insights(self) -> Dict[str, Any]:
        requests = self._current_session.get("requests", [])
        if not requests:
            return {
                "total_requests": 0,
                "total_cost": 0.0,
                "total_tokens": 0,
                "avg_latency": 0.0,
            }

        successful = [r for r in requests if r.get("success", False)]
        latencies = [r.get("latency", 0) for r in requests]

        return {
            "total_requests": len(requests),
            "successful_requests": len(successful),
            "total_cost": sum(r.get("cost", 0) for r in requests),
            "total_tokens_in": sum(r.get("tokens_in", 0) for r in requests),
            "total_tokens_out": sum(r.get("tokens_out", 0) for r in requests),
            "avg_latency": round(statistics.mean(latencies), 3) if latencies else 0.0,
            "models_used": list(set(r.get("model", "unknown") for r in requests)),
        }

    def clear_old_insights(self, days: int = 90) -> int:
        cutoff_date = datetime.now() - timedelta(days=days)
        cleared = 0

        for file_path in self._insights_dir.glob("*.json"):
            if file_path.stem == "index":
                continue

            try:
                file_date = datetime.strptime(file_path.stem, "%Y-%m-%d")
                if file_date < cutoff_date:
                    file_path.unlink()
                    cleared += 1
            except ValueError:
                continue

        return cleared

    def generate(self, days: int = 7, source: Optional[str] = None) -> Dict[str, Any]:
        """生成行为分析报告。

        Args:
            days: 分析天数
            source: 可选的来源过滤

        Returns:
            分析报告字典
        """
        daily_summaries = []
        total_requests = 0
        total_cost = 0.0
        total_tokens_in = 0
        total_tokens_out = 0

        start_date = datetime.now() - timedelta(days=days)

        for i in range(days):
            date = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
            summary = self.get_daily_summary(date)

            if source and summary.get("source") != source:
                continue

            daily_summaries.append(summary)
            total_requests += summary.get("total_requests", 0)
            total_cost += summary.get("total_cost", 0.0)
            total_tokens_in += summary.get("total_tokens_in", 0)
            total_tokens_out += summary.get("total_tokens_out", 0)

        model_dist = self.get_model_distribution(days)
        latency_stats = self.get_latency_stats(days)

        return {
            "period_days": days,
            "daily_summaries": daily_summaries,
            "total": {
                "requests": total_requests,
                "cost": round(total_cost, 4),
                "tokens_in": total_tokens_in,
                "tokens_out": total_tokens_out,
            },
            "model_distribution": model_dist,
            "latency_stats": latency_stats,
            "generated_at": datetime.now().isoformat(),
        }

    def format_terminal(self, report: Dict[str, Any]) -> str:
        """格式化分析报告为终端输出。

        Args:
            report: generate() 返回的报告

        Returns:
            格式化的终端输出字符串
        """
        lines = []
        lines.append("━" * 60)
        lines.append("  📊 Prometheus 行为分析报告")
        lines.append(f"  周期: 最近 {report.get('period_days', 7)} 天")
        lines.append("━" * 60)

        total = report.get("total", {})
        lines.append("")
        lines.append("  总体统计:")
        lines.append(f"    请求数:     {total.get('requests', 0):,}")
        lines.append(f"    总成本:     ${total.get('cost', 0):.4f}")
        lines.append(f"    输入Token:  {total.get('tokens_in', 0):,}")
        lines.append(f"    输出Token:  {total.get('tokens_out', 0):,}")

        model_dist = report.get("model_distribution", {})
        if model_dist:
            lines.append("")
            lines.append("  模型使用分布:")
            for model, stats in sorted(
                model_dist.items(), key=lambda x: x[1].get("count", 0), reverse=True
            ):
                lines.append(f"    {model}:")
                lines.append(f"      请求数: {stats.get('count', 0):,}")
                lines.append(f"      成本:   ${stats.get('cost', 0):.4f}")

        latency = report.get("latency_stats", {})
        if latency:
            lines.append("")
            lines.append("  延迟统计 (秒):")
            lines.append(f"    平均: {latency.get('avg', 0):.3f}s")
            lines.append(f"    最小: {latency.get('min', 0):.3f}s")
            lines.append(f"    最大: {latency.get('max', 0):.3f}s")
            lines.append(f"    P95:  {latency.get('p95', 0):.3f}s")

        daily = report.get("daily_summaries", [])
        if daily:
            lines.append("")
            lines.append("  日均请求:")
            avg_daily = sum(d.get("total_requests", 0) for d in daily) / len(daily)
            lines.append(f"    {avg_daily:.1f} 请求/天")

        lines.append("")
        lines.append("━" * 60)
        lines.append(f"  生成时间: {report.get('generated_at', datetime.now().isoformat())}")
        lines.append("━" * 60)

        return "\n".join(lines)
