from __future__ import annotations

import re
from enum import Enum
from dataclasses import dataclass


class ErrorCategory(Enum):
    RATE_LIMIT = "rate_limit"
    AUTH_FAILURE = "auth_failure"
    TIMEOUT = "timeout"
    CONTENT_FILTER = "content_filter"
    SERVER_ERROR = "server_error"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


@dataclass
class ErrorInfo:
    category: ErrorCategory
    is_retryable: bool
    suggested_delay: float
    message: str


_RATE_LIMIT_PATTERNS = [
    re.compile(r"rate.?limit", re.IGNORECASE),
    re.compile(r"too many requests", re.IGNORECASE),
    re.compile(r"429"),
    re.compile(r"quota exceeded", re.IGNORECASE),
    re.compile(r"requests per", re.IGNORECASE),
]

_AUTH_PATTERNS = [
    re.compile(r"unauthorized", re.IGNORECASE),
    re.compile(r"401"),
    re.compile(r"403"),
    re.compile(r"forbidden", re.IGNORECASE),
    re.compile(r"invalid api key", re.IGNORECASE),
    re.compile(r"authentication", re.IGNORECASE),
    re.compile(r"permission denied", re.IGNORECASE),
]

_TIMEOUT_PATTERNS = [
    re.compile(r"timeout", re.IGNORECASE),
    re.compile(r"timed? ?out", re.IGNORECASE),
    re.compile(r"deadline exceeded", re.IGNORECASE),
    re.compile(r"connection timed? ?out", re.IGNORECASE),
]

_CONTENT_FILTER_PATTERNS = [
    re.compile(r"content.?filter", re.IGNORECASE),
    re.compile(r"safety", re.IGNORECASE),
    re.compile(r"policy violation", re.IGNORECASE),
    re.compile(r"inappropriate content", re.IGNORECASE),
    re.compile(r"flagged", re.IGNORECASE),
]

_SERVER_ERROR_PATTERNS = [
    re.compile(r"5\d{2}"),
    re.compile(r"internal server error", re.IGNORECASE),
    re.compile(r"server error", re.IGNORECASE),
    re.compile(r"service unavailable", re.IGNORECASE),
    re.compile(r"bad gateway", re.IGNORECASE),
    re.compile(r"gateway timeout", re.IGNORECASE),
    re.compile(r"overloaded", re.IGNORECASE),
]

_NETWORK_ERROR_PATTERNS = [
    re.compile(r"connection", re.IGNORECASE),
    re.compile(r"network", re.IGNORECASE),
    re.compile(r"dns", re.IGNORECASE),
    re.compile(r"resolve", re.IGNORECASE),
    re.compile(r"socket", re.IGNORECASE),
    re.compile(r"eof", re.IGNORECASE),
    re.compile(r"reset", re.IGNORECASE),
]


def _matches_patterns(text: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(p.search(text) for p in patterns)


def classify_error(error: Exception) -> ErrorInfo:
    error_type = type(error).__name__.lower()
    error_msg = str(error).lower()
    combined = f"{error_type} {error_msg}"

    if _matches_patterns(combined, _RATE_LIMIT_PATTERNS):
        return ErrorInfo(
            category=ErrorCategory.RATE_LIMIT,
            is_retryable=True,
            suggested_delay=30.0,
            message=error_msg or "Rate limit exceeded",
        )

    if _matches_patterns(combined, _AUTH_PATTERNS):
        return ErrorInfo(
            category=ErrorCategory.AUTH_FAILURE,
            is_retryable=False,
            suggested_delay=0.0,
            message=error_msg or "Authentication failure",
        )

    if _matches_patterns(combined, _TIMEOUT_PATTERNS):
        return ErrorInfo(
            category=ErrorCategory.TIMEOUT,
            is_retryable=True,
            suggested_delay=5.0,
            message=error_msg or "Request timed out",
        )

    if _matches_patterns(combined, _CONTENT_FILTER_PATTERNS):
        return ErrorInfo(
            category=ErrorCategory.CONTENT_FILTER,
            is_retryable=False,
            suggested_delay=0.0,
            message=error_msg or "Content filtered by safety policy",
        )

    if _matches_patterns(combined, _SERVER_ERROR_PATTERNS):
        return ErrorInfo(
            category=ErrorCategory.SERVER_ERROR,
            is_retryable=True,
            suggested_delay=10.0,
            message=error_msg or "Server error",
        )

    if _matches_patterns(combined, _NETWORK_ERROR_PATTERNS):
        return ErrorInfo(
            category=ErrorCategory.NETWORK_ERROR,
            is_retryable=True,
            suggested_delay=3.0,
            message=error_msg or "Network error",
        )

    return ErrorInfo(
        category=ErrorCategory.UNKNOWN,
        is_retryable=False,
        suggested_delay=0.0,
        message=error_msg or "Unknown error",
    )
