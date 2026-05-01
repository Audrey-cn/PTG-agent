from __future__ import annotations

import contextlib
import threading
import time
from dataclasses import dataclass


@dataclass
class _ProviderState:
    remaining_requests: int | None = None
    remaining_tokens: int | None = None
    reset_requests_at: float | None = None
    reset_tokens_at: float | None = None
    limit_requests: int | None = None
    limit_tokens: int | None = None


class RateLimitTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._providers: dict[str, _ProviderState] = {}

    def _get_state(self, provider: str) -> _ProviderState:
        if provider not in self._providers:
            self._providers[provider] = _ProviderState()
        return self._providers[provider]

    def update_from_headers(self, provider: str, headers: dict[str, str]) -> None:
        with self._lock:
            state = self._get_state(provider)

            for key, value in headers.items():
                key_lower = key.lower()
                if key_lower in ("x-ratelimit-remaining-requests", "x-ratelimit-remaining"):
                    with contextlib.suppress(ValueError, TypeError):
                        state.remaining_requests = int(value)
                elif key_lower in ("x-ratelimit-remaining-tokens",):
                    with contextlib.suppress(ValueError, TypeError):
                        state.remaining_tokens = int(value)
                elif key_lower in ("x-ratelimit-reset-requests", "x-ratelimit-reset"):
                    with contextlib.suppress(ValueError, TypeError):
                        state.reset_requests_at = float(value)
                elif key_lower in ("x-ratelimit-reset-tokens",):
                    with contextlib.suppress(ValueError, TypeError):
                        state.reset_tokens_at = float(value)
                elif key_lower in ("x-ratelimit-limit-requests", "x-ratelimit-limit"):
                    with contextlib.suppress(ValueError, TypeError):
                        state.limit_requests = int(value)
                elif key_lower in ("x-ratelimit-limit-tokens",):
                    with contextlib.suppress(ValueError, TypeError):
                        state.limit_tokens = int(value)

            now = time.time()
            if state.reset_requests_at is not None and now >= state.reset_requests_at:
                state.remaining_requests = state.limit_requests
                state.reset_requests_at = None
            if state.reset_tokens_at is not None and now >= state.reset_tokens_at:
                state.remaining_tokens = state.limit_tokens
                state.reset_tokens_at = None

    def check_available(self, provider: str) -> bool:
        with self._lock:
            state = self._get_state(provider)
            now = time.time()

            if state.reset_requests_at is not None and now >= state.reset_requests_at:
                state.remaining_requests = state.limit_requests
                state.reset_requests_at = None

            if state.remaining_requests is not None:
                return state.remaining_requests > 0
            return True

    def get_wait_time(self, provider: str) -> float:
        with self._lock:
            state = self._get_state(provider)
            now = time.time()

            if state.remaining_requests is not None and state.remaining_requests <= 0:
                if state.reset_requests_at is not None:
                    wait = state.reset_requests_at - now
                    return max(wait, 0.0)
                return 60.0

            if state.remaining_tokens is not None and state.remaining_tokens <= 0:
                if state.reset_tokens_at is not None:
                    wait = state.reset_tokens_at - now
                    return max(wait, 0.0)
                return 60.0

            return 0.0

    def get_status(self) -> dict[str, dict[str, int | float | None]]:
        with self._lock:
            now = time.time()
            result: dict[str, dict[str, int | float | None]] = {}
            for provider, state in self._providers.items():
                info: dict[str, int | float | None] = {
                    "remaining_requests": state.remaining_requests,
                    "remaining_tokens": state.remaining_tokens,
                    "limit_requests": state.limit_requests,
                    "limit_tokens": state.limit_tokens,
                }
                if state.reset_requests_at is not None:
                    info["reset_requests_in"] = max(state.reset_requests_at - now, 0.0)
                else:
                    info["reset_requests_in"] = None
                if state.reset_tokens_at is not None:
                    info["reset_tokens_in"] = max(state.reset_tokens_at - now, 0.0)
                else:
                    info["reset_tokens_in"] = None
                result[provider] = info
            return result
