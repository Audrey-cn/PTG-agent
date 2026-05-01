from __future__ import annotations

from typing import Any

PROVIDER_AUTH_URLS: dict[str, str] = {
    "google": "https://accounts.google.com/o/oauth2/v2/auth",
    "github_copilot": "https://github.com/login/oauth/authorize",
    "github_copilot_acp": "https://github.com/login/oauth/authorize",
    "qwen_oauth": "https://oauth.aliyuncs.com/authorize",
    "huggingface": "https://huggingface.co/oauth/authorize",
}

PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o",
    "anthropic": "claude-3.5-sonnet",
    "openrouter": "anthropic/claude-sonnet-4",
    "vercel": "gpt-4o",
    "deepseek": "deepseek-chat",
    "xai": "grok-2",
    "google": "gemini-2.0-flash",
    "github_copilot": "gpt-4o",
    "github_copilot_acp": "gpt-4o",
    "huggingface": "meta-llama/Llama-3.3-70B-Instruct",
    "nous_portal": "nous-hermes-2",
    "nvidia_nim": "meta/llama-3.1-405b-instruct",
    "qwen_oauth": "qwen-max",
    "xiaomi_mimo": "mimo-7b",
    "stepfun": "step-1-8k",
    "minimax": "abab6.5-chat",
    "alibaba_cloud": "qwen-max",
    "ollama_cloud": "llama3.2",
    "arcee_ai": "arcee-lite",
    "kilo_code": "kilo-7b",
    "opencode_zen": "zen-7b",
    "opencode_go": "go-7b",
    "aws_bedrock": "anthropic.claude-3-sonnet-20240229-v1:0",
    "azure_foundry": "gpt-4o",
    "local_ollama": "llama3.2",
    "moonshot": "moonshot-v1-8k",
    "kimi": "moonshot-v1-8k",
    "zhipu": "glm-4",
}

_MODEL_PREFIX_TO_PROVIDER: dict[str, str] = {
    "gpt-": "openai",
    "o1": "openai",
    "o3": "openai",
    "claude-": "anthropic",
    "deepseek-": "deepseek",
    "grok-": "xai",
    "gemini-": "google",
    "moonshot-": "moonshot",
    "glm-": "zhipu",
    "qwen-": "alibaba_cloud",
    "step-": "stepfun",
    "abab": "minimax",
    "llama": "local_ollama",
    "mistral": "local_ollama",
    "phi": "local_ollama",
    "codellama": "local_ollama",
}

_PROVIDER_MODEL_PATTERNS: dict[str, list[str]] = {
    "openrouter": ["anthropic/", "openai/", "google/", "meta-llama/", "mistralai/"],
    "huggingface": ["/", "meta-llama/", "mistralai/"],
}


def get_provider_config(provider_name: str) -> dict[str, Any]:
    from prometheus.cli.models import CANONICAL_PROVIDERS
    spec = CANONICAL_PROVIDERS.get(provider_name)
    if not spec:
        return {}
    return {
        "name": provider_name,
        "label": spec.get("label", provider_name),
        "env_var": spec.get("env_var", ""),
        "base_url": spec.get("base_url", ""),
        "default_model": spec.get("default_model", ""),
        "models": spec.get("models", []),
    }


def list_providers() -> list[str]:
    from prometheus.cli.models import CANONICAL_PROVIDERS
    return list(CANONICAL_PROVIDERS.keys())


def get_provider_env_var(provider: str) -> str:
    config = get_provider_config(provider)
    return config.get("env_var", "")


def resolve_provider(model_name: str) -> str:
    from prometheus.cli.models import CANONICAL_PROVIDERS
    for provider, spec in CANONICAL_PROVIDERS.items():
        if model_name in spec.get("models", []):
            return provider
    for prefix, provider in _MODEL_PREFIX_TO_PROVIDER.items():
        if model_name.startswith(prefix):
            return provider
    for provider, patterns in _PROVIDER_MODEL_PATTERNS.items():
        for pattern in patterns:
            if pattern in model_name:
                return provider
    return "custom"
