"""Usage Pricing Module for Prometheus."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

DEFAULT_PRICING = {"input": 0.0, "output": 0.0}

_ZERO = Decimal("0")
_ONE_MILLION = Decimal("1000000")

CostStatus = Literal["actual", "estimated", "included", "unknown"]
CostSource = Literal[
    "provider_cost_api",
    "provider_generation_api",
    "provider_models_api",
    "official_docs_snapshot",
    "user_override",
    "custom_contract",
    "none",
]


@dataclass(frozen=True)
class CanonicalUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    request_count: int = 1
    raw_usage: dict[str, Any] | None = None

    @property
    def prompt_tokens(self) -> int:
        return self.input_tokens + self.cache_read_tokens + self.cache_write_tokens

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.output_tokens


@dataclass(frozen=True)
class BillingRoute:
    provider: str
    model: str
    base_url: str = ""
    billing_mode: str = "unknown"


@dataclass(frozen=True)
class PricingEntry:
    input_cost_per_million: Decimal | None = None
    output_cost_per_million: Decimal | None = None
    cache_read_cost_per_million: Decimal | None = None
    cache_write_cost_per_million: Decimal | None = None
    request_cost: Decimal | None = None
    source: CostSource = "none"
    source_url: str | None = None
    pricing_version: str | None = None
    fetched_at: datetime | None = None


@dataclass(frozen=True)
class CostResult:
    amount_usd: Decimal | None
    status: CostStatus
    source: CostSource
    label: str
    fetched_at: datetime | None = None
    pricing_version: str | None = None
    notes: Tuple[str, ...] = ()


def _UTC_NOW():
    return datetime.now(UTC)


_OFFICIAL_DOCS_PRICING: dict[Tuple[str, str], PricingEntry] = {
    ("anthropic", "claude-opus-4-20250514"): PricingEntry(
        input_cost_per_million=Decimal("15.00"),
        output_cost_per_million=Decimal("75.00"),
        cache_read_cost_per_million=Decimal("1.50"),
        cache_write_cost_per_million=Decimal("18.75"),
        source="official_docs_snapshot",
        source_url="https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching",
        pricing_version="anthropic-prompt-caching-2026-03-16",
    ),
    ("anthropic", "claude-sonnet-4-20250514"): PricingEntry(
        input_cost_per_million=Decimal("3.00"),
        output_cost_per_million=Decimal("15.00"),
        cache_read_cost_per_million=Decimal("0.30"),
        cache_write_cost_per_million=Decimal("3.75"),
        source="official_docs_snapshot",
        source_url="https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching",
        pricing_version="anthropic-prompt-caching-2026-03-16",
    ),
    ("openai", "gpt-4o"): PricingEntry(
        input_cost_per_million=Decimal("2.50"),
        output_cost_per_million=Decimal("10.00"),
        cache_read_cost_per_million=Decimal("1.25"),
        source="official_docs_snapshot",
        source_url="https://openai.com/api/pricing/",
        pricing_version="openai-pricing-2026-03-16",
    ),
    ("openai", "gpt-4o-mini"): PricingEntry(
        input_cost_per_million=Decimal("0.15"),
        output_cost_per_million=Decimal("0.60"),
        cache_read_cost_per_million=Decimal("0.075"),
        source="official_docs_snapshot",
        source_url="https://openai.com/api/pricing/",
        pricing_version="openai-pricing-2026-03-16",
    ),
    ("openai", "o3"): PricingEntry(
        input_cost_per_million=Decimal("10.00"),
        output_cost_per_million=Decimal("40.00"),
        cache_read_cost_per_million=Decimal("2.50"),
        source="official_docs_snapshot",
        source_url="https://openai.com/api/pricing/",
        pricing_version="openai-pricing-2026-03-16",
    ),
    ("openai", "o3-mini"): PricingEntry(
        input_cost_per_million=Decimal("1.10"),
        output_cost_per_million=Decimal("4.40"),
        cache_read_cost_per_million=Decimal("0.55"),
        source="official_docs_snapshot",
        source_url="https://openai.com/api/pricing/",
        pricing_version="openai-pricing-2026-03-16",
    ),
    ("anthropic", "claude-3-5-sonnet-20241022"): PricingEntry(
        input_cost_per_million=Decimal("3.00"),
        output_cost_per_million=Decimal("15.00"),
        cache_read_cost_per_million=Decimal("0.30"),
        cache_write_cost_per_million=Decimal("3.75"),
        source="official_docs_snapshot",
        source_url="https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching",
        pricing_version="anthropic-pricing-2026-03-16",
    ),
    ("deepseek", "deepseek-chat"): PricingEntry(
        input_cost_per_million=Decimal("0.14"),
        output_cost_per_million=Decimal("0.28"),
        source="official_docs_snapshot",
        source_url="https://api-docs.deepseek.com/quick_start/pricing",
        pricing_version="deepseek-pricing-2026-03-16",
    ),
    ("deepseek", "deepseek-reasoner"): PricingEntry(
        input_cost_per_million=Decimal("0.55"),
        output_cost_per_million=Decimal("2.19"),
        source="official_docs_snapshot",
        source_url="https://api-docs.deepseek.com/quick_start/pricing",
        pricing_version="deepseek-pricing-2026-03-16",
    ),
    ("google", "gemini-2.5-pro"): PricingEntry(
        input_cost_per_million=Decimal("1.25"),
        output_cost_per_million=Decimal("10.00"),
        source="official_docs_snapshot",
        source_url="https://ai.google.dev/pricing",
        pricing_version="google-pricing-2026-03-16",
    ),
    ("google", "gemini-2.5-flash"): PricingEntry(
        input_cost_per_million=Decimal("0.15"),
        output_cost_per_million=Decimal("0.60"),
        source="official_docs_snapshot",
        source_url="https://ai.google.dev/pricing",
        pricing_version="google-pricing-2026-03-16",
    ),
}


def has_known_pricing(model_name: str, provider: str = None, base_url: str = None) -> bool:
    """Check if a model has known pricing."""
    if not model_name:
        return False

    normalized = model_name.lower()

    if ("claude" in normalized or "anthropic" in normalized) and "claude" in normalized:
        return True
    if "gpt" in normalized or "openai" in normalized:
        return True
    if "gemini" in normalized or "google" in normalized:
        return True
    if "deepseek" in normalized:
        return True
    return "bedrock" in (base_url or "").lower()


def estimate_usage_cost(
    model: str,
    usage: CanonicalUsage,
    provider: str = None,
    base_url: str = None,
) -> CostResult:
    """Estimate USD cost for a usage record."""
    if not has_known_pricing(model, provider=provider, base_url=base_url):
        return CostResult(
            amount_usd=None,
            status="unknown",
            source="none",
            label=f"No pricing data for {model}",
        )

    model_lower = model.lower()
    provider_key = (provider or "unknown", model)

    if model_lower not in _OFFICIAL_DOCS_PRICING and provider_key not in _OFFICIAL_DOCS_PRICING:
        return CostResult(
            amount_usd=None,
            status="unknown",
            source="none",
            label=f"No pricing entry for {model}",
        )

    entry = _OFFICIAL_DOCS_PRICING.get(
        (provider or "unknown", model)
    ) or _OFFICIAL_DOCS_PRICING.get(model_lower)

    if not entry:
        return CostResult(
            amount_usd=None,
            status="unknown",
            source="none",
            label=f"No pricing entry for {model}",
        )

    total = _ZERO

    if entry.input_cost_per_million is not None:
        total += Decimal(usage.input_tokens) * entry.input_cost_per_million / _ONE_MILLION

    if entry.output_cost_per_million is not None:
        total += Decimal(usage.output_tokens) * entry.output_cost_per_million / _ONE_MILLION

    if entry.cache_read_cost_per_million is not None:
        total += Decimal(usage.cache_read_tokens) * entry.cache_read_cost_per_million / _ONE_MILLION

    if entry.cache_write_cost_per_million is not None:
        total += (
            Decimal(usage.cache_write_tokens) * entry.cache_write_cost_per_million / _ONE_MILLION
        )

    return CostResult(
        amount_usd=total,
        status="estimated",
        source=entry.source,
        label=f"Estimated cost for {model}",
        pricing_version=entry.pricing_version,
        fetched_at=entry.fetched_at,
    )


def format_duration_compact(seconds: float) -> str:
    """Format seconds into a compact duration string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"
