from __future__ import annotations

import functools
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    retryable_exceptions: Tuple[type[Exception], ...] = (Exception,)


def retry_with_backoff(
    func: F | None = None,
    config: RetryConfig | None = None,
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> Any:
    cfg = config or RetryConfig()

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            for attempt in range(cfg.max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except cfg.retryable_exceptions as exc:
                    last_exception = exc
                    if attempt >= cfg.max_retries:
                        raise
                    delay = min(
                        cfg.base_delay * (cfg.backoff_factor**attempt),
                        cfg.max_delay,
                    )
                    jitter = random.uniform(0, delay * 0.5)
                    wait_time = delay + jitter
                    if on_retry is not None:
                        on_retry(attempt + 1, exc, wait_time)
                    time.sleep(wait_time)
            raise last_exception  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    if func is not None:
        return decorator(func)
    return decorator
