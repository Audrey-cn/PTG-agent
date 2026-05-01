"""Retry utilities with jittered backoff for Prometheus."""

import asyncio
import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def jittered_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: float = 1.0,
) -> float:
    """Calculate delay with exponential backoff and jitter.

    Args:
        attempt: The current attempt number (0-indexed)
        base_delay: Minimum delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential growth
        jitter: Jitter factor (0.0-1.0). 0 means no jitter, 1 means full jitter

    Returns:
        Delay in seconds before next retry
    """
    delay = min(base_delay * (exponential_base**attempt), max_delay)

    if jitter > 0:
        jitter_range = delay * jitter
        delay = delay + random.uniform(-jitter_range / 2, jitter_range / 2)

    return max(0, delay)


async def async_retry_with_backoff(
    func: Callable[..., T],
    *args,
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: float = 0.5,
    retry_on: type | None = Exception,
    backoff_factor: float | None = None,
    **kwargs,
) -> T:
    """Async retry with exponential backoff and jitter.

    Args:
        func: Async function to retry
        *args: Positional arguments for func
        max_attempts: Maximum number of attempts
        base_delay: Minimum delay between retries
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential growth
        jitter: Jitter factor (0.0-1.0)
        retry_on: Exception type to retry on (default: all)
        backoff_factor: Optional per-attempt delay override
        **kwargs: Keyword arguments for func

    Returns:
        Result of func

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_attempts):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        except retry_on if retry_on else Exception as e:
            last_exception = e

            if attempt < max_attempts - 1:
                delay = (
                    backoff_factor(attempt)
                    if backoff_factor
                    else jittered_backoff(attempt, base_delay, max_delay, exponential_base, jitter)
                )

                logger.warning(
                    "Attempt %d/%d failed: %s. Retrying in %.2fs...",
                    attempt + 1,
                    max_attempts,
                    str(e)[:100],
                    delay,
                )

                await asyncio.sleep(delay)
            else:
                logger.error("All %d attempts failed for %s", max_attempts, func.__name__)

    raise last_exception


def retry_with_backoff(
    func: Callable[..., T],
    *args,
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: float = 0.5,
    retry_on: type | None = Exception,
    backoff_factor: Callable[[int], float] | None = None,
    **kwargs,
) -> T:
    """Sync retry with exponential backoff and jitter.

    Args:
        func: Function to retry
        *args: Positional arguments for func
        max_attempts: Maximum number of attempts
        base_delay: Minimum delay between retries
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential growth
        jitter: Jitter factor (0.0-1.0)
        retry_on: Exception type to retry on (default: all)
        backoff_factor: Optional callable that takes attempt and returns delay
        **kwargs: Keyword arguments for func

    Returns:
        Result of func

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_attempts):
        try:
            return func(*args, **kwargs)

        except retry_on if retry_on else Exception as e:
            last_exception = e

            if attempt < max_attempts - 1:
                delay = (
                    backoff_factor(attempt)
                    if backoff_factor
                    else jittered_backoff(attempt, base_delay, max_delay, exponential_base, jitter)
                )

                logger.warning(
                    "Attempt %d/%d failed: %s. Retrying in %.2fs...",
                    attempt + 1,
                    max_attempts,
                    str(e)[:100],
                    delay,
                )

                time.sleep(delay)
            else:
                logger.error("All %d attempts failed for %s", max_attempts, func.__name__)

    raise last_exception


class RetryContext:
    """Context manager for retry operations with state tracking."""

    def __init__(
        self,
        max_attempts: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: float = 0.5,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.attempt = 0
        self.total_delay = 0.0

    def calculate_delay(self) -> float:
        """Calculate delay for current attempt."""
        delay = jittered_backoff(
            self.attempt,
            self.base_delay,
            self.max_delay,
            self.exponential_base,
            self.jitter,
        )
        self.total_delay += delay
        return delay

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and self.attempt < self.max_attempts - 1:
            delay = self.calculate_delay()
            logger.warning(
                "Retry attempt %d/%d after %.2fs delay", self.attempt + 2, self.max_attempts, delay
            )
            await asyncio.sleep(delay)
            self.attempt += 1
            return True
        return False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and self.attempt < self.max_attempts - 1:
            delay = self.calculate_delay()
            logger.warning(
                "Retry attempt %d/%d after %.2fs delay", self.attempt + 2, self.max_attempts, delay
            )
            time.sleep(delay)
            self.attempt += 1
            return True
        return False


def create_rate_limit_retry(
    max_attempts: int = 3,
    initial_delay: float = 2.0,
    max_delay: float = 30.0,
) -> RetryContext:
    """Create a RetryContext optimized for rate limit errors."""
    return RetryContext(
        max_attempts=max_attempts,
        base_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=2.0,
        jitter=0.3,
    )


def create_timeout_retry(
    max_attempts: int = 5,
    initial_delay: float = 1.0,
    max_delay: float = 15.0,
) -> RetryContext:
    """Create a RetryContext optimized for timeout errors."""
    return RetryContext(
        max_attempts=max_attempts,
        base_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=1.5,
        jitter=0.5,
    )
