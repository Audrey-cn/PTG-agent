"""API error classification for smart failover and recovery."""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ── Error taxonomy ──────────────────────────────────────────────────────


class FailoverReason(enum.Enum):
    """Why an API call failed — determines recovery strategy."""

    # Authentication / authorization
    auth = "auth"  # Transient auth (401/403) — refresh/rotate
    auth_permanent = "auth_permanent"  # Auth failed after refresh — abort

    # Billing / quota
    billing = "billing"  # 402 or confirmed credit exhaustion — rotate immediately
    rate_limit = "rate_limit"  # 429 or quota-based throttling — backoff then rotate

    # Server-side
    overloaded = "overloaded"  # 503/529 — provider overloaded, backoff
    server_error = "server_error"  # 500/502 — internal server error, retry

    # Transport
    timeout = "timeout"  # Connection/read timeout — rebuild client + retry

    # Context / payload
    context_overflow = "context_overflow"  # Context too large — compress, not failover
    payload_too_large = "payload_too_large"  # 413 — compress payload
    image_too_large = (
        "image_too_large"  # Native image part exceeds provider's per-image limit — shrink and retry
    )

    # Model
    model_not_found = "model_not_found"  # 404 or invalid model — fallback to different model
    provider_policy_blocked = "provider_policy_blocked"  # Aggregator (e.g. OpenRouter) blocked the only endpoint due to account data/privacy policy

    # Request format
    format_error = "format_error"  # 400 bad request — abort or strip + retry

    # Provider-specific
    thinking_signature = "thinking_signature"  # Anthropic thinking block sig invalid
    long_context_tier = "long_context_tier"  # Anthropic "extra usage" tier gate
    oauth_long_context_beta_forbidden = "oauth_long_context_beta_forbidden"  # Anthropic OAuth subscription rejects 1M context beta — disable beta and retry

    # Catch-all
    unknown = "unknown"  # Unclassifiable — retry with backoff


# ── Classification result ───────────────────────────────────────────────


@dataclass
class ClassifiedError:
    """Structured classification of an API error with recovery hints."""

    reason: FailoverReason
    status_code: int | None = None
    provider: str | None = None
    model: str | None = None
    message: str = ""
    error_context: dict[str, Any] = field(default_factory=dict)

    # Recovery action hints — the retry loop checks these instead of
    # re-classifying the error itself.
    retryable: bool = True
    should_compress: bool = False
    should_rotate_credential: bool = False
    should_fallback: bool = False

    @property
    def is_auth(self) -> bool:
        return self.reason in (FailoverReason.auth, FailoverReason.auth_permanent)


# ── Provider-specific patterns ──────────────────────────────────────────

_BILLING_PATTERNS = [
    "insufficient credits",
    "insufficient_quota",
    "insufficient balance",
    "credit balance",
    "credits have been exhausted",
    "top up your credits",
    "payment required",
    "billing hard limit",
    "exceeded your current quota",
    "account is deactivated",
    "plan does not include",
]

_RATE_LIMIT_PATTERNS = [
    "rate limit",
    "rate_limit",
    "too many requests",
    "throttled",
    "requests per minute",
    "tokens per minute",
    "requests per day",
    "try again in",
    "please retry after",
    "resource_exhausted",
    "rate increased too quickly",
    "throttlingexception",
    "too many concurrent requests",
    "servicequotaexceededexception",
]

_USAGE_LIMIT_PATTERNS = [
    "usage limit",
    "quota",
    "limit exceeded",
    "key limit exceeded",
]

_USAGE_LIMIT_TRANSIENT_SIGNALS = [
    "try again",
    "retry",
    "resets at",
    "reset in",
    "wait",
    "requests remaining",
    "periodic",
    "window",
]

_PAYLOAD_TOO_LARGE_PATTERNS = [
    "request entity too large",
    "payload too large",
    "error code: 413",
]

_IMAGE_TOO_LARGE_PATTERNS = [
    "image exceeds",
    "image too large",
    "image_too_large",
    "image size exceeds",
]

_CONTEXT_OVERFLOW_PATTERNS = [
    "context length",
    "context size",
    "maximum context",
    "token limit",
    "too many tokens",
    "reduce the length",
    "exceeds the limit",
    "context window",
    "prompt is too long",
    "prompt exceeds max length",
    "max_tokens",
    "maximum number of tokens",
    "exceeds the max_model_len",
    "max_model_len",
    "prompt length",
    "input is too long",
    "maximum model length",
    "context length exceeded",
    "truncating input",
    "slot context",
    "n_ctx_slot",
    "超过最大长度",
    "上下文长度",
    "input is too long",
    "max input token",
    "input token",
    "exceeds the maximum number of input tokens",
]

_MODEL_NOT_FOUND_PATTERNS = [
    "is not a valid model",
    "invalid model",
    "model not found",
    "model_not_found",
    "does not exist",
    "no such model",
    "unknown model",
    "unsupported model",
]

_PROVIDER_POLICY_BLOCKED_PATTERNS = [
    "no endpoints available matching your guardrail",
    "no endpoints available matching your data policy",
    "no endpoints found matching your data policy",
]

_AUTH_PATTERNS = [
    "invalid api key",
    "invalid_api_key",
    "authentication",
    "unauthorized",
    "forbidden",
    "invalid token",
    "token expired",
    "token revoked",
    "access denied",
]

_THINKING_SIG_PATTERNS = [
    "signature",
]

_TRANSPORT_ERROR_TYPES = frozenset(
    {
        "ReadTimeout",
        "ConnectTimeout",
        "PoolTimeout",
        "ConnectError",
        "RemoteProtocolError",
        "ConnectionError",
        "ConnectionResetError",
        "ConnectionAbortedError",
        "BrokenPipeError",
        "TimeoutError",
        "ReadError",
        "ServerDisconnectedError",
        "SSLError",
        "SSLZeroReturnError",
        "SSLWantReadError",
        "SSLWantWriteError",
        "SSLEOFError",
        "SSLSyscallError",
        "APIConnectionError",
        "APITimeoutError",
    }
)

_SERVER_DISCONNECT_PATTERNS = [
    "server disconnected",
    "peer closed connection",
    "connection reset by peer",
    "connection was closed",
    "network connection lost",
    "unexpected eof",
    "incomplete chunked read",
]

_SSL_TRANSIENT_PATTERNS = [
    "bad record mac",
    "ssl alert",
    "tls alert",
    "ssl handshake failure",
    "tlsv1 alert",
    "sslv3 alert",
    "bad_record_mac",
    "ssl_alert",
    "tls_alert",
    "tls_alert_internal_error",
    "[ssl:",
]


# ── Classification pipeline ─────────────────────────────────────────────


def classify_api_error(
    error: Exception,
    *,
    provider: str = "",
    model: str = "",
    approx_tokens: int = 0,
    context_length: int = 200000,
    num_messages: int = 0,
) -> ClassifiedError:
    """Classify an API error into a structured recovery recommendation."""
    status_code = _extract_status_code(error)
    error_type = type(error).__name__

    if status_code is None and error_type == "RateLimitError":
        status_code = 429

    body = _extract_error_body(error)
    error_code = _extract_error_code(body)

    _raw_msg = str(error).lower()
    _body_msg = ""
    _metadata_msg = ""

    if isinstance(body, dict):
        _err_obj = body.get("error", {})
        if isinstance(_err_obj, dict):
            _body_msg = str(_err_obj.get("message") or "").lower()
            _metadata = _err_obj.get("metadata", {})
            if isinstance(_metadata, dict):
                _raw_json = _metadata.get("raw") or ""
                if isinstance(_raw_json, str) and _raw_json.strip():
                    try:
                        import json

                        _inner = json.loads(_raw_json)
                        if isinstance(_inner, dict):
                            _inner_err = _inner.get("error", {})
                            if isinstance(_inner_err, dict):
                                _metadata_msg = str(_inner_err.get("message") or "").lower()
                    except (json.JSONDecodeError, TypeError):
                        pass
        if not _body_msg:
            _body_msg = str(body.get("message") or "").lower()

    parts = [_raw_msg]
    if _body_msg and _body_msg not in _raw_msg:
        parts.append(_body_msg)
    if _metadata_msg and _metadata_msg not in _raw_msg and _metadata_msg not in _body_msg:
        parts.append(_metadata_msg)
    error_msg = " ".join(parts)
    provider_lower = (provider or "").strip().lower()
    model_lower = (model or "").strip().lower()

    def _result(reason: FailoverReason, **overrides) -> ClassifiedError:
        defaults = {
            "reason": reason,
            "status_code": status_code,
            "provider": provider,
            "model": model,
            "message": _extract_message(error, body),
        }
        defaults.update(overrides)
        return ClassifiedError(**defaults)

    # Provider-specific patterns
    if status_code == 400 and "signature" in error_msg and "thinking" in error_msg:
        return _result(FailoverReason.thinking_signature, retryable=True, should_compress=False)

    if status_code == 429 and "extra usage" in error_msg and "long context" in error_msg:
        return _result(FailoverReason.long_context_tier, retryable=True, should_compress=True)

    if status_code == 400 and "long context beta" in error_msg and "not yet available" in error_msg:
        return _result(
            FailoverReason.oauth_long_context_beta_forbidden, retryable=True, should_compress=False
        )

    # HTTP status code classification
    if status_code is not None:
        classified = _classify_by_status(
            status_code,
            error_msg,
            error_code,
            body,
            provider=provider_lower,
            model=model_lower,
            approx_tokens=approx_tokens,
            context_length=context_length,
            num_messages=num_messages,
            result_fn=_result,
        )
        if classified is not None:
            return classified

    # Error code classification
    if error_code:
        classified = _classify_by_error_code(error_code, error_msg, _result)
        if classified is not None:
            return classified

    # Message pattern matching
    classified = _classify_by_message(
        error_msg,
        error_type,
        approx_tokens=approx_tokens,
        context_length=context_length,
        result_fn=_result,
    )
    if classified is not None:
        return classified

    # SSL/TLS transient errors
    if any(p in error_msg for p in _SSL_TRANSIENT_PATTERNS):
        return _result(FailoverReason.timeout, retryable=True)

    # Server disconnect + large session
    is_disconnect = any(p in error_msg for p in _SERVER_DISCONNECT_PATTERNS)
    if is_disconnect and not status_code:
        is_large = (
            approx_tokens > context_length * 0.6 or approx_tokens > 120000 or num_messages > 200
        )
        if is_large:
            return _result(FailoverReason.context_overflow, retryable=True, should_compress=True)
        return _result(FailoverReason.timeout, retryable=True)

    # Transport / timeout heuristics
    if error_type in _TRANSPORT_ERROR_TYPES or isinstance(
        error, (TimeoutError, ConnectionError, OSError)
    ):
        return _result(FailoverReason.timeout, retryable=True)

    # Fallback: unknown
    return _result(FailoverReason.unknown, retryable=True)


def _classify_by_status(
    status_code: int,
    error_msg: str,
    error_code: str,
    body: dict,
    *,
    provider: str,
    model: str,
    approx_tokens: int,
    context_length: int,
    num_messages: int = 0,
    result_fn,
) -> ClassifiedError | None:
    """Classify based on HTTP status code with message-aware refinement."""

    if status_code == 401:
        return result_fn(
            FailoverReason.auth,
            retryable=False,
            should_rotate_credential=True,
            should_fallback=True,
        )

    if status_code == 403:
        if "key limit exceeded" in error_msg or "spending limit" in error_msg:
            return result_fn(
                FailoverReason.billing,
                retryable=False,
                should_rotate_credential=True,
                should_fallback=True,
            )
        return result_fn(FailoverReason.auth, retryable=False, should_fallback=True)

    if status_code == 402:
        return _classify_402(error_msg, result_fn)

    if status_code == 404:
        if any(p in error_msg for p in _PROVIDER_POLICY_BLOCKED_PATTERNS):
            return _result(
                FailoverReason.provider_policy_blocked, retryable=False, should_fallback=False
            )
        if any(p in error_msg for p in _MODEL_NOT_FOUND_PATTERNS):
            return result_fn(FailoverReason.model_not_found, retryable=False, should_fallback=True)
        return result_fn(FailoverReason.unknown, retryable=True)

    if status_code == 413:
        return result_fn(FailoverReason.payload_too_large, retryable=True, should_compress=True)

    if status_code == 429:
        return result_fn(
            FailoverReason.rate_limit,
            retryable=True,
            should_rotate_credential=True,
            should_fallback=True,
        )

    if status_code == 400:
        return _classify_400(
            error_msg,
            error_code,
            body,
            provider=provider,
            model=model,
            approx_tokens=approx_tokens,
            context_length=context_length,
            num_messages=num_messages,
            result_fn=result_fn,
        )

    if status_code in (500, 502):
        return result_fn(FailoverReason.server_error, retryable=True)

    if status_code in (503, 529):
        return result_fn(FailoverReason.overloaded, retryable=True)

    if 400 <= status_code < 500:
        return result_fn(FailoverReason.format_error, retryable=False, should_fallback=True)

    if 500 <= status_code < 600:
        return result_fn(FailoverReason.server_error, retryable=True)

    return None


def _classify_402(error_msg: str, result_fn) -> ClassifiedError:
    """Disambiguate 402: billing exhaustion vs transient usage limit."""
    has_usage_limit = any(p in error_msg for p in _USAGE_LIMIT_PATTERNS)
    has_transient_signal = any(p in error_msg for p in _USAGE_LIMIT_TRANSIENT_SIGNALS)

    if has_usage_limit and has_transient_signal:
        return result_fn(
            FailoverReason.rate_limit,
            retryable=True,
            should_rotate_credential=True,
            should_fallback=True,
        )

    return result_fn(
        FailoverReason.billing, retryable=False, should_rotate_credential=True, should_fallback=True
    )


def _classify_400(
    error_msg: str,
    error_code: str,
    body: dict,
    *,
    provider: str,
    model: str,
    approx_tokens: int,
    context_length: int,
    num_messages: int = 0,
    result_fn,
) -> ClassifiedError:
    """Classify 400 Bad Request."""

    if any(p in error_msg for p in _IMAGE_TOO_LARGE_PATTERNS):
        return result_fn(FailoverReason.image_too_large, retryable=True)

    if any(p in error_msg for p in _CONTEXT_OVERFLOW_PATTERNS):
        return result_fn(FailoverReason.context_overflow, retryable=True, should_compress=True)

    if any(p in error_msg for p in _PROVIDER_POLICY_BLOCKED_PATTERNS):
        return result_fn(
            FailoverReason.provider_policy_blocked, retryable=False, should_fallback=False
        )
    if any(p in error_msg for p in _MODEL_NOT_FOUND_PATTERNS):
        return result_fn(FailoverReason.model_not_found, retryable=False, should_fallback=True)

    if any(p in error_msg for p in _RATE_LIMIT_PATTERNS):
        return result_fn(
            FailoverReason.rate_limit,
            retryable=True,
            should_rotate_credential=True,
            should_fallback=True,
        )
    if any(p in error_msg for p in _BILLING_PATTERNS):
        return result_fn(
            FailoverReason.billing,
            retryable=False,
            should_rotate_credential=True,
            should_fallback=True,
        )

    err_body_msg = ""
    if isinstance(body, dict):
        err_obj = body.get("error", {})
        if isinstance(err_obj, dict):
            err_body_msg = str(err_obj.get("message") or "").strip().lower()
        if not err_body_msg:
            err_body_msg = str(body.get("message") or "").strip().lower()
    is_generic = len(err_body_msg) < 30 or err_body_msg in ("error", "")
    is_large = approx_tokens > context_length * 0.4 or approx_tokens > 80000 or num_messages > 80

    if is_generic and is_large:
        return result_fn(FailoverReason.context_overflow, retryable=True, should_compress=True)

    return result_fn(FailoverReason.format_error, retryable=False, should_fallback=True)


def _classify_by_error_code(
    error_code: str,
    error_msg: str,
    result_fn,
) -> ClassifiedError | None:
    """Classify by structured error codes from the response body."""
    code_lower = error_code.lower()

    if code_lower in ("resource_exhausted", "throttled", "rate_limit_exceeded"):
        return result_fn(FailoverReason.rate_limit, retryable=True, should_rotate_credential=True)

    if code_lower in ("insufficient_quota", "billing_not_active", "payment_required"):
        return result_fn(
            FailoverReason.billing,
            retryable=False,
            should_rotate_credential=True,
            should_fallback=True,
        )

    if code_lower in ("model_not_found", "model_not_available", "invalid_model"):
        return result_fn(FailoverReason.model_not_found, retryable=False, should_fallback=True)

    if code_lower in ("context_length_exceeded", "max_tokens_exceeded"):
        return result_fn(FailoverReason.context_overflow, retryable=True, should_compress=True)

    return None


def _classify_by_message(
    error_msg: str,
    error_type: str,
    *,
    approx_tokens: int,
    context_length: int,
    result_fn,
) -> ClassifiedError | None:
    """Classify based on error message patterns."""

    if any(p in error_msg for p in _PAYLOAD_TOO_LARGE_PATTERNS):
        return result_fn(FailoverReason.payload_too_large, retryable=True, should_compress=True)

    if any(p in error_msg for p in _IMAGE_TOO_LARGE_PATTERNS):
        return result_fn(FailoverReason.image_too_large, retryable=True)

    has_usage_limit = any(p in error_msg for p in _USAGE_LIMIT_PATTERNS)
    if has_usage_limit:
        has_transient_signal = any(p in error_msg for p in _USAGE_LIMIT_TRANSIENT_SIGNALS)
        if has_transient_signal:
            return result_fn(
                FailoverReason.rate_limit,
                retryable=True,
                should_rotate_credential=True,
                should_fallback=True,
            )
        return result_fn(
            FailoverReason.billing,
            retryable=False,
            should_rotate_credential=True,
            should_fallback=True,
        )

    if any(p in error_msg for p in _BILLING_PATTERNS):
        return result_fn(
            FailoverReason.billing,
            retryable=False,
            should_rotate_credential=True,
            should_fallback=True,
        )

    if any(p in error_msg for p in _RATE_LIMIT_PATTERNS):
        return result_fn(
            FailoverReason.rate_limit,
            retryable=True,
            should_rotate_credential=True,
            should_fallback=True,
        )

    if any(p in error_msg for p in _CONTEXT_OVERFLOW_PATTERNS):
        return result_fn(FailoverReason.context_overflow, retryable=True, should_compress=True)

    if any(p in error_msg for p in _AUTH_PATTERNS):
        return result_fn(
            FailoverReason.auth,
            retryable=False,
            should_rotate_credential=True,
            should_fallback=True,
        )

    if any(p in error_msg for p in _PROVIDER_POLICY_BLOCKED_PATTERNS):
        return result_fn(
            FailoverReason.provider_policy_blocked, retryable=False, should_fallback=False
        )

    if any(p in error_msg for p in _MODEL_NOT_FOUND_PATTERNS):
        return result_fn(FailoverReason.model_not_found, retryable=False, should_fallback=True)

    return None


# ── Helpers ─────────────────────────────────────────────────────────────


def _extract_status_code(error: Exception) -> int | None:
    """Walk the error and its cause chain to find an HTTP status code."""
    current = error
    for _ in range(5):
        code = getattr(current, "status_code", None)
        if isinstance(code, int):
            return code
        code = getattr(current, "status", None)
        if isinstance(code, int) and 100 <= code < 600:
            return code
        cause = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
        if cause is None or cause is current:
            break
        current = cause
    return None


def _extract_error_body(error: Exception) -> dict:
    """Extract the structured error body from an SDK exception."""
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        return body
    response = getattr(error, "response", None)
    if response is not None:
        try:
            json_body = response.json()
            if isinstance(json_body, dict):
                return json_body
        except Exception:
            pass
    return {}


def _extract_error_code(body: dict) -> str:
    """Extract an error code string from the response body."""
    if not body:
        return ""
    error_obj = body.get("error", {})
    if isinstance(error_obj, dict):
        code = error_obj.get("code") or error_obj.get("type") or ""
        if isinstance(code, str) and code.strip():
            return code.strip()
    code = body.get("code") or body.get("error_code") or ""
    if isinstance(code, (str, int)):
        return str(code).strip()
    return ""


def _extract_message(error: Exception, body: dict) -> str:
    """Extract the most informative error message."""
    if body:
        error_obj = body.get("error", {})
        if isinstance(error_obj, dict):
            msg = error_obj.get("message", "")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()[:500]
        msg = body.get("message", "")
        if isinstance(msg, str) and msg.strip():
            return msg.strip()[:500]
    return str(error)[:500]
