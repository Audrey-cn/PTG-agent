"""Models.dev registry integration for Prometheus."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from prometheus._paths import get_paths
from prometheus.utils import atomic_json_write

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

MODELS_DEV_URL = "https://models.dev/api.json"
_MODELS_DEV_CACHE_TTL = 3600

_models_dev_cache: dict[str, Any] = {}
_models_dev_cache_time: float = 0


@dataclass
class ModelInfo:
    """Full metadata for a single model from models.dev."""

    id: str
    name: str
    family: str
    provider_id: str

    reasoning: bool = False
    tool_call: bool = False
    attachment: bool = False
    temperature: bool = False
    structured_output: bool = False
    open_weights: bool = False

    input_modalities: tuple[str, ...] = ()
    output_modalities: tuple[str, ...] = ()

    context_window: int = 0
    max_output: int = 0
    max_input: int | None = None

    cost_input: float = 0.0
    cost_output: float = 0.0
    cost_cache_read: float | None = None
    cost_cache_write: float | None = None

    knowledge_cutoff: str = ""
    release_date: str = ""
    status: str = ""
    interleaved: Any = False

    def has_cost_data(self) -> bool:
        return self.cost_input > 0 or self.cost_output > 0

    def supports_vision(self) -> bool:
        return self.attachment or "image" in self.input_modalities

    def supports_pdf(self) -> bool:
        return "pdf" in self.input_modalities

    def supports_audio_input(self) -> bool:
        return "audio" in self.input_modalities

    def format_cost(self) -> str:
        """Human-readable cost string, e.g. '$3.00/M in, $15.00/M out'."""
        if not self.has_cost_data():
            return "unknown"
        parts = [f"${self.cost_input:.2f}/M in", f"${self.cost_output:.2f}/M out"]
        if self.cost_cache_read is not None:
            parts.append(f"cache read ${self.cost_cache_read:.2f}/M")
        return ", ".join(parts)

    def format_capabilities(self) -> str:
        """Human-readable capabilities."""
        caps = []
        if self.reasoning:
            caps.append("reasoning")
        if self.tool_call:
            caps.append("tools")
        if self.supports_vision():
            caps.append("vision")
        if self.supports_pdf():
            caps.append("PDF")
        if self.supports_audio_input():
            caps.append("audio")
        if self.structured_output:
            caps.append("structured output")
        if self.open_weights:
            caps.append("open weights")
        return ", ".join(caps) if caps else "basic"


@dataclass
class ProviderInfo:
    """Full metadata for a provider from models.dev."""

    id: str
    name: str
    env: tuple[str, ...]
    api: str
    doc: str = ""
    model_count: int = 0


PROVIDER_TO_MODELS_DEV: dict[str, str] = {
    "openrouter": "openrouter",
    "anthropic": "anthropic",
    "openai": "openai",
    "openai-codex": "openai",
    "zai": "zai",
    "kimi-coding": "kimi-for-coding",
    "stepfun": "stepfun",
    "kimi-coding-cn": "kimi-for-coding",
    "minimax": "minimax",
    "minimax-oauth": "minimax",
    "minimax-cn": "minimax-cn",
    "deepseek": "deepseek",
    "alibaba": "alibaba",
    "qwen-oauth": "alibaba",
    "copilot": "github-copilot",
    "ai-gateway": "vercel",
    "opencode-zen": "opencode",
    "opencode-go": "opencode-go",
    "kilocode": "kilo",
    "fireworks": "fireworks-ai",
    "huggingface": "huggingface",
    "gemini": "google",
    "google": "google",
    "xai": "xai",
    "xiaomi": "xiaomi",
    "nvidia": "nvidia",
    "groq": "groq",
    "mistral": "mistral",
    "togetherai": "togetherai",
    "perplexity": "perplexity",
    "cohere": "cohere",
    "ollama-cloud": "ollama-cloud",
}

_MODELS_DEV_TO_PROVIDER: dict[str, str] | None = None


def _get_cache_path() -> Path:
    """Return path to disk cache file."""
    return get_paths().cache / "models_dev_cache.json"


def _load_disk_cache() -> dict[str, Any]:
    """Load models.dev data from disk cache."""
    try:
        cache_path = _get_cache_path()
        if cache_path.exists():
            with open(cache_path, encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.debug("Failed to load models.dev disk cache: %s", e)
    return {}


def _save_disk_cache(data: dict[str, Any]) -> None:
    """Save models.dev data to disk cache atomically."""
    try:
        cache_path = _get_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_json_write(data, cache_path)
    except Exception as e:
        logger.debug("Failed to save models.dev disk cache: %s", e)


def fetch_models_dev(force_refresh: bool = False) -> dict[str, Any]:
    """Fetch models.dev registry. In-memory cache (1hr) + disk fallback."""
    global _models_dev_cache, _models_dev_cache_time

    if (
        not force_refresh
        and _models_dev_cache
        and (time.time() - _models_dev_cache_time) < _MODELS_DEV_CACHE_TTL
    ):
        return _models_dev_cache

    try:
        import urllib.request

        req = urllib.request.Request(MODELS_DEV_URL, headers={"User-Agent": "Prometheus/1.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            if isinstance(data, dict) and data:
                _models_dev_cache = data
                _models_dev_cache_time = time.time()
                _save_disk_cache(data)
                logger.debug(
                    "Fetched models.dev registry: %d providers",
                    len(data),
                )
                return data
    except Exception as e:
        logger.debug("Failed to fetch models.dev: %s", e)

    if not _models_dev_cache:
        _models_dev_cache = _load_disk_cache()
        if _models_dev_cache:
            _models_dev_cache_time = time.time() - _MODELS_DEV_CACHE_TTL + 300
            logger.debug("Loaded models.dev from disk cache (%d providers)", len(_models_dev_cache))

    return _models_dev_cache


def lookup_models_dev_context(provider: str, model: str) -> int | None:
    """Look up context_length for a provider+model combo in models.dev."""
    mdev_provider_id = PROVIDER_TO_MODELS_DEV.get(provider)
    if not mdev_provider_id:
        return None

    data = fetch_models_dev()
    provider_data = data.get(mdev_provider_id)
    if not isinstance(provider_data, dict):
        return None

    models = provider_data.get("models", {})
    if not isinstance(models, dict):
        return None

    entry = models.get(model)
    if entry:
        ctx = _extract_context(entry)
        if ctx:
            return ctx

    model_lower = model.lower()
    for mid, mdata in models.items():
        if mid.lower() == model_lower:
            ctx = _extract_context(mdata)
            if ctx:
                return ctx

    return None


def _extract_context(entry: dict[str, Any]) -> int | None:
    """Extract context_length from a models.dev model entry."""
    if not isinstance(entry, dict):
        return None
    limit = entry.get("limit")
    if not isinstance(limit, dict):
        return None
    ctx = limit.get("context")
    if isinstance(ctx, (int, float)) and ctx > 0:
        return int(ctx)
    return None


@dataclass
class ModelCapabilities:
    """Structured capability metadata for a model."""

    supports_tools: bool = True
    supports_vision: bool = False
    supports_reasoning: bool = False
    context_window: int = 200000
    max_output_tokens: int = 8192
    model_family: str = ""


def _get_provider_models(provider: str) -> dict[str, Any] | None:
    """Resolve a provider ID to its models dict from models.dev."""
    mdev_provider_id = PROVIDER_TO_MODELS_DEV.get(provider)
    if not mdev_provider_id:
        return None

    data = fetch_models_dev()
    provider_data = data.get(mdev_provider_id)
    if not isinstance(provider_data, dict):
        return None

    models = provider_data.get("models", {})
    if not isinstance(models, dict):
        return None

    return models


def _find_model_entry(models: dict[str, Any], model: str) -> dict[str, Any] | None:
    """Find a model entry by exact match, then case-insensitive fallback."""
    entry = models.get(model)
    if isinstance(entry, dict):
        return entry

    model_lower = model.lower()
    for mid, mdata in models.items():
        if mid.lower() == model_lower and isinstance(mdata, dict):
            return mdata

    return None


def get_model_capabilities(provider: str, model: str) -> ModelCapabilities | None:
    """Look up full capability metadata from models.dev cache."""
    models = _get_provider_models(provider)
    if models is None:
        return None

    entry = _find_model_entry(models, model)
    if entry is None:
        return None

    supports_tools = bool(entry.get("tool_call", False))
    input_mods = entry.get("modalities", {})
    if isinstance(input_mods, dict):
        input_mods = input_mods.get("input", [])
    else:
        input_mods = []
    supports_vision = bool(entry.get("attachment", False)) or "image" in input_mods
    supports_reasoning = bool(entry.get("reasoning", False))

    limit = entry.get("limit", {})
    if not isinstance(limit, dict):
        limit = {}

    ctx = limit.get("context")
    context_window = int(ctx) if isinstance(ctx, (int, float)) and ctx > 0 else 200000

    max_output = limit.get("output")
    if not isinstance(max_output, (int, float)) or max_output <= 0:
        max_output = 8192

    family = entry.get("family", "")

    return ModelCapabilities(
        supports_tools=supports_tools,
        supports_vision=supports_vision,
        supports_reasoning=supports_reasoning,
        context_window=context_window,
        max_output_tokens=int(max_output),
        model_family=family,
    )


def search_models(query: str, provider: str | None = None) -> list[ModelInfo]:
    """Search for models matching a query string."""
    results = []
    data = fetch_models_dev()

    providers_to_search = [provider] if provider else data.keys()

    for prov_id in providers_to_search:
        if prov_id not in data:
            continue

        provider_data = data[prov_id]
        if not isinstance(provider_data, dict):
            continue

        models = provider_data.get("models", {})
        if not isinstance(models, dict):
            continue

        for model_id, model_data in models.items():
            if query.lower() in model_id.lower() or query.lower() in str(model_data).lower():
                results.append(
                    ModelInfo(
                        id=model_id,
                        name=model_data.get("name", model_id),
                        family=model_data.get("family", ""),
                        provider_id=prov_id,
                        reasoning=model_data.get("reasoning", False),
                        tool_call=model_data.get("tool_call", False),
                        context_window=_extract_context(model_data) or 0,
                    )
                )

    return results
