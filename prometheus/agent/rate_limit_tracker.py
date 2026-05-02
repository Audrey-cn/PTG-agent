"""Rate limit tracker for API providers."""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from prometheus_time import now as prometheus_now

logger = logging.getLogger(__name__)


@dataclass
class RateLimitStatus:
    provider: str
    credential_id: str
    requests_remaining: int
    tokens_remaining: int
    reset_at: datetime
    is_exhausted: bool = False

    def __post_init__(self):
        if self.reset_at.tzinfo is None:
            self.reset_at = self.reset_at.replace(tzinfo=UTC)


@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    timestamp: datetime = field(default_factory=prometheus_now)

    def __post_init__(self):
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=UTC)


class RateLimitTracker:
    """
    Tracks rate limit status and token usage per provider/credential.

    Provides methods to:
    - Update rate limit info from API responses
    - Check if a credential is exhausted
    - Record token usage
    - Get remaining quotas
    """

    def __init__(self):
        self._limits: dict[str, RateLimitStatus] = {}
        self._usage: dict[str, list[TokenUsage]] = {}
        self._lock = threading.RLock()

    def _key(self, provider: str, credential_id: str) -> str:
        return f"{provider}:{credential_id}"

    def update_limit(
        self,
        provider: str,
        credential_id: str,
        requests_remaining: int | None = None,
        tokens_remaining: int | None = None,
        reset_at: datetime | None = None,
        retry_after_seconds: int | None = None,
    ) -> RateLimitStatus:
        """Update rate limit information for a credential."""
        with self._lock:
            key = self._key(provider, credential_id)
            current = self._limits.get(key)

            if (
                requests_remaining is not None
                and requests_remaining <= 0
                or tokens_remaining is not None
                and tokens_remaining <= 0
            ):
                is_exhausted = True
                if reset_at is None and retry_after_seconds is not None:
                    reset_at = prometheus_now() + timedelta(seconds=retry_after_seconds)
            else:
                is_exhausted = False

            if reset_at is None and current is not None:
                reset_at = current.reset_at
            elif reset_at is None:
                reset_at = prometheus_now() + timedelta(hours=1)

            new_status = RateLimitStatus(
                provider=provider,
                credential_id=credential_id,
                requests_remaining=requests_remaining
                if requests_remaining is not None
                else (current.requests_remaining if current else -1),
                tokens_remaining=tokens_remaining
                if tokens_remaining is not None
                else (current.tokens_remaining if current else -1),
                reset_at=reset_at,
                is_exhausted=is_exhausted,
            )
            self._limits[key] = new_status
            return new_status

    def record_usage(
        self,
        provider: str,
        credential_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int | None = None,
    ) -> TokenUsage:
        """Record token usage for a credential."""
        if total_tokens is None:
            total_tokens = prompt_tokens + completion_tokens

        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

        with self._lock:
            key = self._key(provider, credential_id)
            if key not in self._usage:
                self._usage[key] = []
            self._usage[key].append(usage)

            if len(self._usage[key]) > 1000:
                self._usage[key] = self._usage[key][-500:]

        return usage

    def get_limit(self, provider: str, credential_id: str) -> RateLimitStatus | None:
        """Get current rate limit status for a credential."""
        with self._lock:
            key = self._key(provider, credential_id)
            status = self._limits.get(key)
            if status and status.is_exhausted and status.reset_at <= prometheus_now():
                status.is_exhausted = False
            return status

    def get_usage(
        self,
        provider: str,
        credential_id: str,
        window_seconds: int | None = None,
    ) -> list[TokenUsage]:
        """Get token usage history for a credential."""
        with self._lock:
            key = self._key(provider, credential_id)
            usages = self._usage.get(key, [])
            if window_seconds is None:
                return list(usages)
            cutoff = prometheus_now() - timedelta(seconds=window_seconds)
            return [u for u in usages if u.timestamp > cutoff]

    def get_total_usage(
        self,
        provider: str,
        credential_id: str,
        window_seconds: int | None = None,
    ) -> dict[str, int]:
        """Get total token usage within a time window."""
        usages = self.get_usage(provider, credential_id, window_seconds)
        if not usages:
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        return {
            "prompt_tokens": sum(u.prompt_tokens for u in usages),
            "completion_tokens": sum(u.completion_tokens for u in usages),
            "total_tokens": sum(u.total_tokens for u in usages),
        }

    def is_exhausted(self, provider: str, credential_id: str) -> bool:
        """Check if a credential is rate limited."""
        status = self.get_limit(provider, credential_id)
        return status is not None and status.is_exhausted

    def wait_time(self, provider: str, credential_id: str) -> float:
        """Get seconds to wait until rate limit resets."""
        status = self.get_limit(provider, credential_id)
        if status is None or not status.is_exhausted:
            return 0.0
        now = prometheus_now()
        if status.reset_at <= now:
            return 0.0
        return (status.reset_at - now).total_seconds()

    def clear_expired(self) -> int:
        """Clear expired rate limit entries. Returns count cleared."""
        with self._lock:
            now = prometheus_now()
            cleared = 0
            expired_keys = [key for key, status in self._limits.items() if status.reset_at < now]
            for key in expired_keys:
                del self._limits[key]
                cleared += 1
            return cleared

    def get_all_limits(self) -> dict[str, RateLimitStatus]:
        """Get all tracked rate limits."""
        with self._lock:
            result = {}
            now = prometheus_now()
            for key, status in self._limits.items():
                if status.is_exhausted and status.reset_at <= now:
                    status.is_exhausted = False
                result[key] = status
            return result


_tracker = RateLimitTracker()


def get_tracker() -> RateLimitTracker:
    """Get the global rate limit tracker instance."""
    return _tracker


def update_from_response(
    provider: str,
    credential_id: str,
    response_headers: dict[str, Any] | None = None,
    status_code: int | None = None,
) -> RateLimitStatus | None:
    """
    Update rate limit info from API response headers.

    Common header names:
    - X-RateLimit-Remaining, X-RateLimit-Limit
    - X-RateLimit-Request-Remaining, X-RateLimit-Request-Limit
    - X-RateLimit-Token-Remaining, X-RateLimit-Token-Limit
    - Retry-After
    - RateLimit-Remaining, RateLimit-Limit
    """
    tracker = get_tracker()

    if status_code == 429:
        retry_after = None
        if response_headers:
            retry_after = response_headers.get("Retry-After")
            if retry_after:
                try:
                    retry_after = int(retry_after)
                except (ValueError, TypeError):
                    retry_after = None

        return tracker.update_limit(
            provider,
            credential_id,
            requests_remaining=0,
            tokens_remaining=0,
            retry_after_seconds=retry_after,
        )

    if response_headers is None:
        return None

    requests_remaining = None
    tokens_remaining = None
    reset_at = None

    for header_name in [
        "X-RateLimit-Request-Remaining",
        "X-RateLimit-Remaining",
        "RateLimit-Remaining",
    ]:
        if header_name in response_headers:
            try:
                requests_remaining = int(response_headers[header_name])
                break
            except (ValueError, TypeError):
                pass

    for header_name in [
        "X-RateLimit-Token-Remaining",
        "X-RateLimit-Token-Limit",
    ]:
        if header_name in response_headers:
            try:
                tokens_remaining = int(response_headers[header_name])
                break
            except (ValueError, TypeError):
                pass

    for header_name in [
        "X-RateLimit-Reset",
        "RateLimit-Reset",
    ]:
        if header_name in response_headers:
            try:
                reset_ts = float(response_headers[header_name])
                if reset_ts > 1_000_000_000:
                    reset_at = datetime.fromtimestamp(reset_ts, tz=UTC)
                else:
                    reset_at = prometheus_now() + timedelta(seconds=reset_ts)
                break
            except (ValueError, TypeError):
                pass

    return tracker.update_limit(
        provider,
        credential_id,
        requests_remaining=requests_remaining,
        tokens_remaining=tokens_remaining,
        reset_at=reset_at,
    )
