from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CounterMetric:
    name: str
    value: int = 0
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class GaugeMetric:
    name: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class HistogramMetric:
    name: str
    values: list[float] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)
    buckets: list[float] = field(default_factory=lambda: [0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0])


class GatewayMetrics:
    def __init__(self) -> None:
        self._counters: Dict[str, CounterMetric] = {}
        self._gauges: Dict[str, GaugeMetric] = {}
        self._histograms: Dict[str, HistogramMetric] = {}
        self._lock = threading.Lock()
        self._start_time = time.time()

    def _make_key(self, name: str, labels: Dict[str, str] | None) -> str:
        if not labels:
            return name
        sorted_labels = sorted(labels.items())
        label_str = ",".join(f"{k}={v}" for k, v in sorted_labels)
        return f"{name}{{{label_str}}}"

    def increment_counter(self, name: str, labels: Dict[str, str] | None = None) -> None:
        key = self._make_key(name, labels)
        with self._lock:
            if key not in self._counters:
                self._counters[key] = CounterMetric(
                    name=name,
                    labels=labels or {},
                )
            self._counters[key].value += 1

    def set_gauge(self, name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        key = self._make_key(name, labels)
        with self._lock:
            if key not in self._gauges:
                self._gauges[key] = GaugeMetric(
                    name=name,
                    labels=labels or {},
                )
            self._gauges[key].value = value

    def observe_histogram(
        self, name: str, value: float, labels: Dict[str, str] | None = None
    ) -> None:
        key = self._make_key(name, labels)
        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = HistogramMetric(
                    name=name,
                    labels=labels or {},
                )
            self._histograms[key].values.append(value)

    def get_all_metrics(self) -> Dict[str, Any]:
        with self._lock:
            counters = {
                key: {
                    "name": m.name,
                    "value": m.value,
                    "labels": m.labels.copy(),
                }
                for key, m in self._counters.items()
            }
            gauges = {
                key: {
                    "name": m.name,
                    "value": m.value,
                    "labels": m.labels.copy(),
                }
                for key, m in self._gauges.items()
            }
            histograms = {}
            for key, m in self._histograms.items():
                values = m.values
                total = sum(values)
                count = len(values)
                avg = total / count if count > 0 else 0
                buckets = {}
                for bucket in m.buckets:
                    buckets[f"le_{bucket}"] = len([v for v in values if v <= bucket])
                histograms[key] = {
                    "name": m.name,
                    "count": count,
                    "sum": total,
                    "avg": avg,
                    "labels": m.labels.copy(),
                    "buckets": buckets,
                }
            return {
                "uptime_seconds": time.time() - self._start_time,
                "counters": counters,
                "gauges": gauges,
                "histograms": histograms,
            }

    def export_prometheus(self) -> str:
        lines: List[str] = []
        with self._lock:
            for _key, m in self._counters.items():
                lines.append(f"# TYPE {m.name} counter")
                label_str = ""
                if m.labels:
                    label_str = "{" + ",".join(f'{k}="{v}"' for k, v in m.labels.items()) + "}"
                lines.append(f"{m.name}{label_str} {m.value}")
            for _key, m in self._gauges.items():
                lines.append(f"# TYPE {m.name} gauge")
                label_str = ""
                if m.labels:
                    label_str = "{" + ",".join(f'{k}="{v}"' for k, v in m.labels.items()) + "}"
                lines.append(f"{m.name}{label_str} {m.value}")
            for _key, m in self._histograms.items():
                lines.append(f"# TYPE {m.name} histogram")
                values = m.values
                total = sum(values)
                count = len(values)
                label_str = ""
                if m.labels:
                    label_str = "{" + ",".join(f'{k}="{v}"' for k, v in m.labels.items())
                for bucket in m.buckets:
                    bucket_count = len([v for v in values if v <= bucket])
                    bucket_label = (
                        f'{label_str},le="{bucket}"}}' if m.labels else f'{{le="{bucket}"}}'
                    )
                    lines.append(f"{m.name}_bucket{bucket_label} {bucket_count}")
                if m.labels:
                    lines.append(f"{m.name}_count{{{label_str}}} {count}")
                    lines.append(f"{m.name}_sum{{{label_str}}} {total}")
                else:
                    lines.append(f"{m.name}_count {count}")
                    lines.append(f"{m.name}_sum {total}")
        return "\n".join(lines)

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._start_time = time.time()
