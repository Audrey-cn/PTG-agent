from __future__ import annotations

from urllib.parse import urlparse

PROVIDER_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "openrouter": "https://openrouter.ai/api/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "xai": "https://api.x.ai/v1",
    "google": "https://generativelanguage.googleapis.com",
}

_HOST_TO_PROVIDER: dict[str, str] = {
    "api.openai.com": "openai",
    "api.anthropic.com": "anthropic",
    "openrouter.ai": "openrouter",
    "api.deepseek.com": "deepseek",
    "api.x.ai": "xai",
    "generativelanguage.googleapis.com": "google",
}

_API_MODE_MAP: dict[str, str] = {
    "api.anthropic.com": "anthropic_messages",
    "api.openai.com": "openai_chat",
    "openrouter.ai": "openai_chat",
    "api.deepseek.com": "openai_chat",
    "api.x.ai": "openai_chat",
    "generativelanguage.googleapis.com": "google_generate",
}


def detect_provider_from_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    hostname = parsed.hostname or ""
    for host, provider in _HOST_TO_PROVIDER.items():
        if hostname == host or hostname.endswith("." + host):
            return provider
    return "custom"


def detect_api_mode(base_url: str) -> str | None:
    parsed = urlparse(base_url)
    hostname = parsed.hostname or ""
    for host, mode in _API_MODE_MAP.items():
        if hostname == host or hostname.endswith("." + host):
            return mode
    path = parsed.path.rstrip("/")
    if "responses" in path:
        return "codex_responses"
    if "messages" in path:
        return "anthropic_messages"
    return "openai_chat"


def resolve_base_url(provider: str, config: dict | None = None) -> str:
    if config and "base_url" in config:
        return config["base_url"]
    return PROVIDER_URLS.get(provider, "")
