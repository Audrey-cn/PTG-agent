from __future__ import annotations

import time
from typing import Any


class NousRateGuard:
    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        requests_per_day: int = 10000,
    ):
        self._rpm = requests_per_minute
        self._rph = requests_per_hour
        self._rpd = requests_per_day
        self._minute_requests: list[float] = []
        self._hour_requests: list[float] = []
        self._day_requests: list[float] = []

    def check_rate_limit(self) -> bool:
        now = time.time()
        self._cleanup(now)
        if len(self._minute_requests) >= self._rpm:
            return False
        if len(self._hour_requests) >= self._rph:
            return False
        return not len(self._day_requests) >= self._rpd

    def record_request(self) -> None:
        now = time.time()
        self._minute_requests.append(now)
        self._hour_requests.append(now)
        self._day_requests.append(now)

    def get_wait_time(self) -> float:
        now = time.time()
        self._cleanup(now)
        if len(self._minute_requests) < self._rpm:
            return 0.0
        oldest_minute = self._minute_requests[0] if self._minute_requests else now
        wait_minute = max(0, 60 - (now - oldest_minute))
        if len(self._hour_requests) < self._rph:
            return wait_minute
        oldest_hour = self._hour_requests[0] if self._hour_requests else now
        wait_hour = max(0, 3600 - (now - oldest_hour))
        if len(self._day_requests) < self._rpd:
            return max(wait_minute, wait_hour)
        oldest_day = self._day_requests[0] if self._day_requests else now
        wait_day = max(0, 86400 - (now - oldest_day))
        return max(wait_minute, wait_hour, wait_day)

    def get_remaining(self) -> int:
        now = time.time()
        self._cleanup(now)
        return min(
            self._rpm - len(self._minute_requests),
            self._rph - len(self._hour_requests),
            self._rpd - len(self._day_requests),
        )

    def _cleanup(self, now: float) -> None:
        self._minute_requests = [t for t in self._minute_requests if now - t < 60]
        self._hour_requests = [t for t in self._hour_requests if now - t < 3600]
        self._day_requests = [t for t in self._day_requests if now - t < 86400]

    def reset(self) -> None:
        self._minute_requests.clear()
        self._hour_requests.clear()
        self._day_requests.clear()

    def get_status(self) -> Dict[str, Any]:
        now = time.time()
        self._cleanup(now)
        return {
            "minute": {
                "used": len(self._minute_requests),
                "limit": self._rpm,
            },
            "hour": {
                "used": len(self._hour_requests),
                "limit": self._rph,
            },
            "day": {
                "used": len(self._day_requests),
                "limit": self._rpd,
            },
        }
