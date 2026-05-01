"""Failover system for Prometheus."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .error_classifier import ClassifiedError, FailoverReason, classify_api_error

logger = logging.getLogger(__name__)


class FailoverState(Enum):
    """Failover state machine states."""

    NORMAL = "normal"
    RETRYING = "retrying"
    ROTATING_CREDENTIAL = "rotating_credential"
    FALLBACK = "fallback"
    COMPRESSING = "compressing"
    EXHAUSTED = "exhausted"


@dataclass
class ProviderEndpoint:
    """A single provider endpoint."""

    name: str
    base_url: str | None = None
    api_key: str | None = None
    priority: int = 0
    enabled: bool = True
    failure_count: int = 0
    last_failure: str | None = None


@dataclass
class FailoverConfig:
    """Configuration for failover behavior."""

    max_retries: int = 3
    max_credential_rotations: int = 2
    max_fallbacks: int = 2
    retry_delay_base: float = 1.0
    retry_delay_max: float = 30.0
    enable_credential_rotation: bool = True
    enable_fallback: bool = True
    enable_compression: bool = True


@dataclass
class FailoverResult:
    """Result of a failover operation."""

    success: bool
    new_endpoint: str | None = None
    action_taken: str = ""
    message: str = ""
    should_retry: bool = False
    should_compress: bool = False
    should_rotate_credential: bool = False
    should_fallback: bool = False


class FailoverManager:
    """Manages failover between provider endpoints.

    Implements a state machine for handling various error types
    with appropriate recovery actions.
    """

    def __init__(
        self,
        config: FailoverConfig | None = None,
        on_rotate_credential: Callable | None = None,
        on_fallback: Callable | None = None,
        on_compress: Callable | None = None,
    ):
        """Initialize the failover manager.

        Args:
            config: Failover configuration
            on_rotate_credential: Callback when credential rotation needed
            on_fallback: Callback when fallback to another model needed
            on_compress: Callback when context compression needed
        """
        self._config = config or FailoverConfig()
        self._endpoints: dict[str, list[ProviderEndpoint]] = {}
        self._current_endpoint: dict[str, int] = {}
        self._state: dict[str, FailoverState] = {}
        self._retry_count: dict[str, int] = {}
        self._rotation_count: dict[str, int] = {}
        self._fallback_count: dict[str, int] = {}

        self._on_rotate_credential = on_rotate_credential
        self._on_fallback = on_fallback
        self._on_compress = on_compress

    def register_provider(
        self,
        provider_name: str,
        endpoints: list[ProviderEndpoint],
    ):
        """Register a provider with its endpoints.

        Args:
            provider_name: Name of the provider
            endpoints: List of endpoints (sorted by priority)
        """
        self._endpoints[provider_name] = sorted(endpoints, key=lambda e: -e.priority)
        self._current_endpoint[provider_name] = 0
        self._state[provider_name] = FailoverState.NORMAL
        self._retry_count[provider_name] = 0
        self._rotation_count[provider_name] = 0
        self._fallback_count[provider_name] = 0

    def get_current_endpoint(self, provider_name: str) -> ProviderEndpoint | None:
        """Get the current active endpoint for a provider.

        Args:
            provider_name: Name of the provider

        Returns:
            Current endpoint or None
        """
        if provider_name not in self._endpoints:
            return None

        idx = self._current_endpoint.get(provider_name, 0)
        endpoints = self._endpoints[provider_name]

        if 0 <= idx < len(endpoints):
            return endpoints[idx]
        return None

    def handle_error(
        self,
        provider_name: str,
        error: Exception,
        context: dict[str, Any] | None = None,
    ) -> FailoverResult:
        """Handle an error from a provider.

        Args:
            provider_name: Name of the provider
            error: The exception that occurred
            context: Additional context (model, approx_tokens, etc.)

        Returns:
            FailoverResult with recommended action
        """
        if provider_name not in self._endpoints:
            return FailoverResult(
                success=False,
                message=f"Unknown provider: {provider_name}",
            )

        classified = classify_api_error(
            error,
            provider=provider_name,
            model=context.get("model") if context else "",
            approx_tokens=context.get("approx_tokens", 0) if context else 0,
        )

        state = self._state[provider_name]

        if state == FailoverState.EXHAUSTED:
            return FailoverResult(
                success=False,
                message="All failover options exhausted",
                should_retry=False,
            )

        if classified.reason == FailoverReason.auth:
            return self._handle_auth_error(provider_name, classified)

        if classified.reason == FailoverReason.billing:
            return self._handle_billing_error(provider_name, classified)

        if classified.reason == FailoverReason.rate_limit:
            return self._handle_rate_limit_error(provider_name, classified)

        if classified.reason == FailoverReason.context_overflow:
            return self._handle_context_overflow_error(provider_name, classified)

        if classified.reason in (FailoverReason.server_error, FailoverReason.overloaded):
            return self._handle_server_error(provider_name, classified)

        if classified.reason == FailoverReason.timeout:
            return self._handle_timeout_error(provider_name, classified)

        if classified.reason == FailoverReason.model_not_found:
            return self._handle_model_not_found_error(provider_name, classified)

        return FailoverResult(
            success=False,
            message=f"Unhandled error type: {classified.reason}",
            should_retry=False,
        )

    def _handle_auth_error(
        self,
        provider_name: str,
        classified: ClassifiedError,
    ) -> FailoverResult:
        """Handle authentication errors."""
        rotation_count = self._rotation_count.get(provider_name, 0)

        if (
            self._config.enable_credential_rotation
            and rotation_count < self._config.max_credential_rotations
        ):
            self._rotation_count[provider_name] = rotation_count + 1
            self._state[provider_name] = FailoverState.ROTATING_CREDENTIAL

            if self._on_rotate_credential:
                self._on_rotate_credential(provider_name)

            return FailoverResult(
                success=True,
                action_taken="rotate_credential",
                message=f"Rotating credential (attempt {rotation_count + 1}/{self._config.max_credential_rotations})",
                should_retry=True,
                should_rotate_credential=True,
            )

        self._state[provider_name] = FailoverState.EXHAUSTED
        return FailoverResult(
            success=False,
            action_taken="auth_failed",
            message="Authentication failed after credential rotation",
            should_retry=False,
            should_fallback=self._config.enable_fallback,
        )

    def _handle_billing_error(
        self,
        provider_name: str,
        classified: ClassifiedError,
    ) -> FailoverResult:
        """Handle billing/credit errors."""
        rotation_count = self._rotation_count.get(provider_name, 0)

        if (
            self._config.enable_credential_rotation
            and rotation_count < self._config.max_credential_rotations
        ):
            self._rotation_count[provider_name] = rotation_count + 1

            if self._on_rotate_credential:
                self._on_rotate_credential(provider_name)

            return FailoverResult(
                success=True,
                action_taken="rotate_credential",
                message="Rotating credential due to billing issue",
                should_retry=True,
                should_rotate_credential=True,
            )

        return FailoverResult(
            success=False,
            action_taken="billing_exhausted",
            message="Billing exhausted, no more credentials to try",
            should_retry=False,
            should_fallback=self._config.enable_fallback,
        )

    def _handle_rate_limit_error(
        self,
        provider_name: str,
        classified: ClassifiedError,
    ) -> FailoverResult:
        """Handle rate limit errors."""
        retry_count = self._retry_count.get(provider_name, 0)

        if retry_count < self._config.max_retries:
            self._retry_count[provider_name] = retry_count + 1
            self._state[provider_name] = FailoverState.RETRYING

            min(
                self._config.retry_delay_base * (2**retry_count),
                self._config.retry_delay_max,
            )

            return FailoverResult(
                success=True,
                action_taken="retry_with_backoff",
                message=f"Retrying with backoff (attempt {retry_count + 1}/{self._config.max_retries})",
                should_retry=True,
            )

        fallback_count = self._fallback_count.get(provider_name, 0)

        if self._config.enable_fallback and fallback_count < self._config.max_fallbacks:
            return self._fallback_to_next_endpoint(provider_name)

        return FailoverResult(
            success=False,
            action_taken="rate_limit_exhausted",
            message="Rate limit retries exhausted",
            should_retry=False,
            should_rotate_credential=True,
            should_fallback=self._config.enable_fallback,
        )

    def _handle_context_overflow_error(
        self,
        provider_name: str,
        classified: ClassifiedError,
    ) -> FailoverResult:
        """Handle context overflow errors."""
        if self._config.enable_compression:
            self._state[provider_name] = FailoverState.COMPRESSING

            if self._on_compress:
                self._on_compress(provider_name)

            return FailoverResult(
                success=True,
                action_taken="compress_context",
                message="Triggering context compression",
                should_retry=True,
                should_compress=True,
            )

        return FailoverResult(
            success=False,
            action_taken="context_overflow",
            message="Context overflow and compression disabled",
            should_retry=False,
        )

    def _handle_server_error(
        self,
        provider_name: str,
        classified: ClassifiedError,
    ) -> FailoverResult:
        """Handle server errors (5xx)."""
        retry_count = self._retry_count.get(provider_name, 0)

        if retry_count < self._config.max_retries:
            self._retry_count[provider_name] = retry_count + 1
            self._state[provider_name] = FailoverState.RETRYING

            return FailoverResult(
                success=True,
                action_taken="retry",
                message=f"Retrying server error (attempt {retry_count + 1}/{self._config.max_retries})",
                should_retry=True,
            )

        return self._fallback_to_next_endpoint(provider_name)

    def _handle_timeout_error(
        self,
        provider_name: str,
        classified: ClassifiedError,
    ) -> FailoverResult:
        """Handle timeout errors."""
        retry_count = self._retry_count.get(provider_name, 0)

        if retry_count < self._config.max_retries:
            self._retry_count[provider_name] = retry_count + 1

            return FailoverResult(
                success=True,
                action_taken="retry",
                message=f"Retrying timeout (attempt {retry_count + 1}/{self._config.max_retries})",
                should_retry=True,
            )

        return self._fallback_to_next_endpoint(provider_name)

    def _handle_model_not_found_error(
        self,
        provider_name: str,
        classified: ClassifiedError,
    ) -> FailoverResult:
        """Handle model not found errors."""
        if self._config.enable_fallback:
            return self._fallback_to_next_endpoint(provider_name)

        return FailoverResult(
            success=False,
            action_taken="model_not_found",
            message="Model not found and fallback disabled",
            should_retry=False,
        )

    def _fallback_to_next_endpoint(self, provider_name: str) -> FailoverResult:
        """Fall back to the next available endpoint."""
        fallback_count = self._fallback_count.get(provider_name, 0)
        endpoints = self._endpoints.get(provider_name, [])

        if not endpoints:
            return FailoverResult(
                success=False,
                message="No endpoints available",
                should_retry=False,
            )

        current_idx = self._current_endpoint.get(provider_name, 0)

        if current_idx >= len(endpoints) - 1:
            self._state[provider_name] = FailoverState.EXHAUSTED
            return FailoverResult(
                success=False,
                action_taken="all_endpoints_exhausted",
                message="All endpoints exhausted",
                should_retry=False,
            )

        self._current_endpoint[provider_name] = current_idx + 1
        self._fallback_count[provider_name] = fallback_count + 1
        self._state[provider_name] = FailoverState.FALLBACK
        self._retry_count[provider_name] = 0

        new_endpoint = endpoints[current_idx + 1]

        if self._on_fallback:
            self._on_fallback(provider_name, new_endpoint.name)

        return FailoverResult(
            success=True,
            new_endpoint=new_endpoint.name,
            action_taken="fallback",
            message=f"Falling back to {new_endpoint.name}",
            should_retry=True,
        )

    def reset_provider(self, provider_name: str) -> None:
        """Reset failover state for a provider.

        Args:
            provider_name: Name of the provider
        """
        if provider_name in self._state:
            self._state[provider_name] = FailoverState.NORMAL
            self._retry_count[provider_name] = 0
            self._rotation_count[provider_name] = 0
            self._fallback_count[provider_name] = 0

    def get_state(self, provider_name: str) -> FailoverState:
        """Get the current failover state for a provider."""
        return self._state.get(provider_name, FailoverState.NORMAL)

    def get_status(self) -> dict[str, Any]:
        """Get status of all providers."""
        return {
            provider: {
                "state": self._state[provider].value,
                "current_endpoint": self.get_current_endpoint(provider),
                "retry_count": self._retry_count.get(provider, 0),
                "rotation_count": self._rotation_count.get(provider, 0),
                "fallback_count": self._fallback_count.get(provider, 0),
            }
            for provider in self._endpoints
        }


_global_failover_manager: FailoverManager | None = None


def get_failover_manager() -> FailoverManager:
    """Get the global failover manager instance."""
    global _global_failover_manager
    if _global_failover_manager is None:
        _global_failover_manager = FailoverManager()
    return _global_failover_manager


def configure_failover(
    max_retries: int = 3,
    max_credential_rotations: int = 2,
    max_fallbacks: int = 2,
    enable_credential_rotation: bool = True,
    enable_fallback: bool = True,
    enable_compression: bool = True,
) -> FailoverManager:
    """Configure the global failover manager.

    Args:
        max_retries: Maximum retry attempts
        max_credential_rotations: Max credential rotations
        max_fallbacks: Max fallback attempts
        enable_credential_rotation: Enable credential rotation
        enable_fallback: Enable fallback
        enable_compression: Enable compression

    Returns:
        Configured FailoverManager
    """
    config = FailoverConfig(
        max_retries=max_retries,
        max_credential_rotations=max_credential_rotations,
        max_fallbacks=max_fallbacks,
        enable_credential_rotation=enable_credential_rotation,
        enable_fallback=enable_fallback,
        enable_compression=enable_compression,
    )

    global _global_failover_manager
    _global_failover_manager = FailoverManager(config=config)
    return _global_failover_manager
