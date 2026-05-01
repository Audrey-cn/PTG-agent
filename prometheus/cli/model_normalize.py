"""Per-provider model name normalization for Prometheus."""

from __future__ import annotations

import re

# Vendor prefix mapping
_VENDOR_PREFIXES: Dict[str, str] = {
    "claude": "anthropic",
    "gpt": "openai",
    "o1": "openai",
    "o3": "openai",
    "o4": "openai",
    "gemini": "google",
    "gemma": "google",
    "deepseek": "deepseek",
    "glm": "z-ai",
    "kimi": "moonshotai",
    "minimax": "minimax",
    "grok": "x-ai",
    "qwen": "qwen",
    "mimo": "xiaomi",
    "trinity": "arcee-ai",
    "nemotron": "nvidia",
    "llama": "meta-llama",
    "step": "stepfun",
}

# Providers whose APIs consume vendor/model slugs
_AGGREGATOR_PROVIDERS: frozenSet[str] = frozenset(
    {
        "openrouter",
        "nous",
        "ai-gateway",
        "kilocode",
    }
)

# Providers that want bare names with dots replaced by hyphens
_DOT_TO_HYPHEN_PROVIDERS: frozenSet[str] = frozenset(
    {
        "anthropic",
    }
)

# Providers that want bare names with dots preserved
_STRIP_VENDOR_ONLY_PROVIDERS: frozenSet[str] = frozenset(
    {
        "copilot",
        "copilot-acp",
        "openai-codex",
    }
)

# Providers whose native naming is authoritative -- pass through unchanged
_AUTHORITATIVE_NATIVE_PROVIDERS: frozenSet[str] = frozenset(
    {
        "gemini",
        "huggingface",
    }
)

# Direct providers that accept bare native names but should repair a matching
# provider/ prefix when users copy the aggregator form into config.yaml
_MATCHING_PREFIX_STRIP_PROVIDERS: frozenSet[str] = frozenset(
    {
        "zai",
        "kimi-coding",
        "kimi-coding-cn",
        "minimax",
        "minimax-oauth",
        "minimax-cn",
        "alibaba",
        "qwen-oauth",
        "xiaomi",
        "arcee",
        "ollama-cloud",
        "custom",
    }
)

# Providers whose APIs require lowercase model IDs
_LOWERCASE_MODEL_PROVIDERS: frozenSet[str] = frozenset(
    {
        "xiaomi",
    }
)

# DeepSeek special handling
_DEEPSEEK_REASONER_KEYWORDS: frozenSet[str] = frozenset(
    {
        "reasoner",
        "r1",
        "think",
        "reasoning",
        "cot",
    }
)

_DEEPSEEK_CANONICAL_MODELS: frozenSet[str] = frozenset(
    {
        "deepseek-chat",
        "deepseek-reasoner",
        "deepseek-v4-pro",
        "deepseek-v4-flash",
    }
)

_DEEPSEEK_V_SERIES_RE = re.compile(r"^deepseek-v\d+([-.].+)?$")


def _normalize_for_deepseek(model_name: str) -> str:
    bare = _strip_vendor_prefix(model_name).lower()
    if bare in _DEEPSEEK_CANONICAL_MODELS:
        return bare
    if _DEEPSEEK_V_SERIES_RE.match(bare):
        return bare
    for keyword in _DEEPSEEK_REASONER_KEYWORDS:
        if keyword in bare:
            return "deepseek-reasoner"
    return "deepseek-chat"


def _strip_vendor_prefix(model_name: str) -> str:
    if "/" in model_name:
        return model_name.split("/", 1)[1]
    return model_name


def _dots_to_hyphens(model_name: str) -> str:
    return model_name.replace(".", "-")


def _normalize_provider_alias(provider_name: str) -> str:
    raw = (provider_name or "").strip().lower()
    if not raw:
        return raw
    try:
        from prometheus.cli.providers import normalize_provider

        return normalize_provider(raw)
    except Exception:
        return raw


def _strip_matching_provider_prefix(model_name: str, target_provider: str) -> str:
    if "/" not in model_name:
        return model_name
    prefix, remainder = model_name.split("/", 1)
    if not prefix.strip() or not remainder.strip():
        return model_name
    normalized_prefix = _normalize_provider_alias(prefix)
    normalized_target = _normalize_provider_alias(target_provider)
    if normalized_prefix and normalized_prefix == normalized_target:
        return remainder.strip()
    return model_name


def detect_vendor(model_name: str) -> str | None:
    name = model_name.strip()
    if not name:
        return None
    if "/" in name:
        return name.split("/", 1)[0].lower() or None
    name_lower = name.lower()
    first_token = name_lower.split("-")[0]
    if first_token in _VENDOR_PREFIXES:
        return _VENDOR_PREFIXES[first_token]
    for prefix, vendor in _VENDOR_PREFIXES.items():
        if name_lower.startswith(prefix):
            return vendor
    return None


def _prepend_vendor(model_name: str) -> str:
    if "/" in model_name:
        return model_name
    vendor = detect_vendor(model_name)
    if vendor:
        return f"{vendor}/{model_name}"
    return model_name


def normalize_model_for_provider(model_input: str, target_provider: str) -> str:
    name = (model_input or "").strip()
    if not name:
        return name
    provider = _normalize_provider_alias(target_provider)

    if provider in _AGGREGATOR_PROVIDERS:
        return _prepend_vendor(name)

    if provider == "opencode-zen":
        bare = _strip_matching_provider_prefix(name, provider)
        if "/" in bare:
            return bare
        if bare.lower().startswith("claude-"):
            return _dots_to_hyphens(bare)
        return bare

    if provider in _DOT_TO_HYPHEN_PROVIDERS:
        bare = _strip_matching_provider_prefix(name, provider)
        if "/" in bare:
            return bare
        return _dots_to_hyphens(bare)

    if provider in {"copilot", "copilot-acp"}:
        try:
            from prometheus.cli.models import normalize_copilot_model_id

            normalized = normalize_copilot_model_id(name)
            if normalized:
                return normalized
        except Exception:
            pass

    if provider in _STRIP_VENDOR_ONLY_PROVIDERS:
        stripped = _strip_matching_provider_prefix(name, provider)
        if stripped == name and name.startswith("openai/"):
            return name.split("/", 1)[1]
        return stripped

    if provider == "deepseek":
        bare = _strip_matching_provider_prefix(name, provider)
        if "/" in bare:
            return bare
        return _normalize_for_deepseek(bare)

    if provider in _MATCHING_PREFIX_STRIP_PROVIDERS:
        result = _strip_matching_provider_prefix(name, provider)
        if provider in _LOWERCASE_MODEL_PROVIDERS:
            result = result.lower()
        return result

    if provider in _AUTHORITATIVE_NATIVE_PROVIDERS:
        return name

    return name
