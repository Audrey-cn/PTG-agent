from __future__ import annotations

from typing import Any

# Alias mapping for provider names
ALIASES: Dict[str, str] = {
    "openai": "openrouter",
    "glm": "zai",
    "z-ai": "zai",
    "z.ai": "zai",
    "zhipu": "zai",
    "x-ai": "xai",
    "x.ai": "xai",
    "grok": "xai",
    "nim": "nvidia",
    "nvidia-nim": "nvidia",
    "build-nvidia": "nvidia",
    "nemotron": "nvidia",
    "kimi-coding": "kimi-for-coding",
    "kimi": "kimi-for-coding",
    "kimi-for-coding": "kimi-for-coding",
    "kimi-coding-cn": "kimi-for-coding",
    "moonshot": "kimi-for-coding",
    "step": "stepfun",
    "stepfun-coding-plan": "stepfun",
    "minimax-china": "minimax-cn",
    "minimax_cn": "minimax-cn",
    "claude": "anthropic",
    "claude-code": "anthropic",
    "copilot": "github-copilot",
    "github": "github-copilot",
    "github-copilot-acp": "copilot-acp",
    "ai-gateway": "vercel",
    "aigateway": "vercel",
    "vercel-ai-gateway": "vercel",
    "opencode-zen": "opencode",
    "zen": "opencode",
    "go": "opencode-go",
    "opencode-go-sub": "opencode-go",
    "kilocode": "kilo",
    "kilo-code": "kilo",
    "kilo-gateway": "kilo",
    "deep-seek": "deepseek",
    "dashscope": "alibaba",
    "aliyun": "alibaba",
    "qwen": "alibaba",
    "alibaba-cloud": "alibaba",
    "alibaba_coding": "alibaba-coding-plan",
    "alibaba-coding": "alibaba-coding-plan",
    "alibaba_coding_plan": "alibaba-coding-plan",
    "gemini-cli": "google-gemini-cli",
    "gemini-oauth": "google-gemini-cli",
    "hf": "huggingface",
    "hugging-face": "huggingface",
    "huggingface-hub": "huggingface",
    "mimo": "xiaomi",
    "xiaomi-mimo": "xiaomi",
    "tencent": "tencent-tokenhub",
    "tokenhub": "tencent-tokenhub",
    "tencent-cloud": "tencent-tokenhub",
    "tencentmaas": "tencent-tokenhub",
    "aws": "bedrock",
    "aws-bedrock": "bedrock",
    "amazon-bedrock": "bedrock",
    "amazon": "bedrock",
    "arcee-ai": "arcee",
    "arceeai": "arcee",
    "gmi-cloud": "gmi",
    "gmicloud": "gmi",
    "gmi": "gmi",
    "lmstudio": "lmstudio",
    "lm-studio": "lmstudio",
    "lm_studio": "lmstudio",
    "ollama": "custom",
    "vllm": "local",
    "llamacpp": "local",
    "llama.cpp": "local",
    "llama-cpp": "local",
}


def normalize_provider(name: str) -> str:
    """Resolve provider aliases to canonical names.

    Args:
        name: Input provider name or alias.

    Returns:
        Canonical provider ID string.
    """
    key = name.strip().lower()
    return ALIASES.get(key, key)


PROVIDER_AUTH_URLS: Dict[str, str] = {
    "google": "https://accounts.google.com/o/oauth2/v2/auth",
    "github_copilot": "https://github.com/login/oauth/authorize",
    "github_copilot_acp": "https://github.com/login/oauth/authorize",
    "qwen_oauth": "https://oauth.aliyuncs.com/authorize",
    "huggingface": "https://huggingface.co/oauth/authorize",
}

PROVIDER_DEFAULT_MODELS: Dict[str, str] = {
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
    "nous_portal": "nous-prometheus-2",
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

_MODEL_PREFIX_TO_PROVIDER: Dict[str, str] = {
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

_PROVIDER_MODEL_PATTERNS: Dict[str, List[str]] = {
    "openrouter": ["anthropic/", "openai/", "google/", "meta-llama/", "mistralai/"],
    "huggingface": ["/", "meta-llama/", "mistralai/"],
}


def get_provider_config(provider_name: str) -> Dict[str, Any]:
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


def list_providers() -> List[str]:
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
