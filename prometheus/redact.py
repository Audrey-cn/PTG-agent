from __future__ import annotations

import re
from typing import Any

REDACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(sk-)[a-zA-Z0-9]{20,}", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(key-)[a-zA-Z0-9]{20,}", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(Bearer\s+)[a-zA-Z0-9\-._~+/]+=*", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"), "[REDACTED_EMAIL]"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[REDACTED_IP]"),
    (re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s\-]?)?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}(?!\d)"), "[REDACTED_PHONE]"),
    (re.compile(r"\b(?:\d[ \-]?){13,19}\b"), "[REDACTED_CC]"),
    (re.compile(r"([?&](?:token|key|secret|api_key|access_token|apikey|auth)=[^&\s]+)", re.IGNORECASE), r"\1=[REDACTED]"),
]

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|passwd|secret|key|token|auth|credential|private|api_key|apikey|access_key|secret_key)",
    re.IGNORECASE,
)


def redact_text(text: str) -> str:
    result = text
    for pattern, replacement in REDACT_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def redact_dict(data: dict) -> dict:
    result: dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, dict):
            result[k] = redact_dict(v)
        elif isinstance(v, list):
            result[k] = [redact_dict(item) if isinstance(item, dict) else _redact_value(k, item) for item in v]
        else:
            result[k] = _redact_value(k, v)
    return result


def _redact_value(key: str, value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if is_sensitive_key(key):
        return "[REDACTED]"
    return redact_text(value)


def is_sensitive_key(key: str) -> bool:
    return bool(_SENSITIVE_KEY_PATTERN.search(key))
