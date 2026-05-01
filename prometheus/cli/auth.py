from __future__ import annotations

import os
import sys
from typing import Optional

PROVIDER_ENV_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "xai": "XAI_API_KEY",
    "google": "GOOGLE_API_KEY",
    "github": "GITHUB_TOKEN",
}

PROVIDER_DISPLAY_NAMES = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "openrouter": "OpenRouter",
    "deepseek": "DeepSeek",
    "xai": "xAI (Grok)",
    "google": "Google (Gemini)",
    "github": "GitHub",
}


def check_auth(provider: str) -> bool:
    provider_lower = provider.lower()
    env_key = PROVIDER_ENV_MAP.get(provider_lower)
    if not env_key:
        return False
    key = os.environ.get(env_key, "")
    return bool(key and len(key) >= 8)


def set_auth(provider: str, api_key: str) -> bool:
    provider_lower = provider.lower()
    env_key = PROVIDER_ENV_MAP.get(provider_lower)
    if not env_key:
        return False
    os.environ[env_key] = api_key
    try:
        from prometheus.config import get_env_path
        env_path = get_env_path()
        existing = {}
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        existing[k.strip()] = v.strip()
        existing[env_key] = api_key
        with open(env_path, "w", encoding="utf-8") as f:
            for k, v in existing.items():
                f.write(f"{k}={v}\n")
        return True
    except Exception:
        return False


def clear_auth(provider: str) -> bool:
    provider_lower = provider.lower()
    env_key = PROVIDER_ENV_MAP.get(provider_lower)
    if not env_key:
        return False
    if env_key in os.environ:
        del os.environ[env_key]
    try:
        from prometheus.config import get_env_path
        env_path = get_env_path()
        if env_path.exists():
            existing = {}
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        existing[k.strip()] = v.strip()
            if env_key in existing:
                del existing[env_key]
            with open(env_path, "w", encoding="utf-8") as f:
                for k, v in existing.items():
                    f.write(f"{k}={v}\n")
        return True
    except Exception:
        return False


def show_auth_status() -> None:
    print("\n🔐 认证状态\n")
    for provider, env_key in PROVIDER_ENV_MAP.items():
        display_name = PROVIDER_DISPLAY_NAMES.get(provider, provider)
        key = os.environ.get(env_key, "")
        if key:
            masked = key[:4] + "*" * 8 + key[-4:] if len(key) > 16 else key[:4] + "*" * 4
            status = f"✅ {masked}"
        else:
            status = "❌ 未设置"
        print(f"  {display_name:<15} {status}")
    print()


def get_auth_key(provider: str) -> Optional[str]:
    provider_lower = provider.lower()
    env_key = PROVIDER_ENV_MAP.get(provider_lower)
    if not env_key:
        return None
    return os.environ.get(env_key) or None
