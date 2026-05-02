from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any


class AuthError(Exception):
    """Authentication-related error."""

    pass


def resolve_provider(provider_name: str = None) -> str:
    """Resolve and return the provider name.

    Args:
        provider_name: Optional provider name to resolve.

    Returns:
        Resolved provider name.

    Raises:
        AuthError: If provider cannot be resolved.
    """
    if provider_name:
        return provider_name

    # Try to get from environment
    provider = os.environ.get("PROMETHEUS_PROVIDER", "").strip()
    if provider:
        return provider

    raise AuthError(
        "No provider configured. Set PROMETHEUS_PROVIDER env var or pass provider argument."
    )


def format_auth_error(error: AuthError) -> str:
    """Format an AuthError for display.

    Args:
        error: The AuthError instance.

    Returns:
        Formatted error message string.
    """
    return str(error)


def resolve_nous_runtime_credentials(min_key_ttl_seconds=1800, timeout_seconds=15) -> dict:
    """Resolve Nous runtime credentials."""
    raise AuthError("Nous credentials not available")


def resolve_codex_runtime_credentials(**kwargs) -> dict:
    """Resolve Codex runtime credentials."""
    raise AuthError("Codex credentials not available")


def resolve_gemini_oauth_runtime_credentials(**kwargs) -> dict:
    """Resolve Gemini OAuth runtime credentials."""
    raise AuthError("Gemini OAuth credentials not available")


def resolve_qwen_runtime_credentials(**kwargs) -> dict:
    """Resolve Qwen runtime credentials."""
    raise AuthError("Qwen credentials not available")


def resolve_external_process_provider_credentials(**kwargs) -> dict:
    """Resolve external process provider credentials."""
    raise AuthError("External process credentials not available")


def resolve_api_key_provider_credentials(**kwargs) -> dict:
    """Resolve API key provider credentials."""
    raise AuthError("API key provider credentials not available")


# ─── Token refresh / TTL constants ────────────────────────────────────────────

CODEX_ACCESS_TOKEN_REFRESH_SKEW_SECONDS = 120
"""Seconds before actual expiry to consider an openai-codex token as 'expiring'."""

DEFAULT_AGENT_KEY_MIN_TTL_SECONDS = 1800
"""Default minimum TTL (in seconds) for agent keys to be considered usable."""

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

PROVIDER_REGISTRY = dict(PROVIDER_DISPLAY_NAMES)
"""Registry of known providers (alias for display names)."""

# ─── Auth store helpers ───────────────────────────────────────────────────────

_AUTH_STORE_LOCK = threading.Lock()


def _auth_store_lock():
    """Return the lock for auth store operations."""
    return _AUTH_STORE_LOCK


def _get_auth_store_path() -> Path:
    """Return the path to the auth store file."""
    from prometheus.config import get_prometheus_home

    return get_prometheus_home() / "auth.json"


def _load_auth_store() -> dict:
    """Load the auth store from disk."""
    path = _get_auth_store_path()
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_auth_store(data: dict) -> None:
    """Save the auth store to disk."""
    path = _get_auth_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _load_provider_state(provider: str) -> dict:
    """Load provider-specific state from auth store."""
    store = _load_auth_store()
    return store.get(provider, {})


def _save_provider_state(provider: str, state: dict) -> None:
    """Save provider-specific state to auth store."""
    store = _load_auth_store()
    store[provider] = state
    _save_auth_store(store)


def _resolve_kimi_base_url() -> str:
    """Resolve KIMI base URL from env or default."""
    return os.environ.get("KIMI_BASE_URL", "https://api.moonshot.cn/v1")


def _resolve_zai_base_url() -> str:
    """Resolve ZAI base URL from env or default."""
    return os.environ.get("ZAI_BASE_URL", "https://api.openai.com/v1")


def _decode_jwt_claims(token: str) -> dict:
    """Decode JWT token claims (simplified)."""
    import base64

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        payload = parts[1]
        payload += "=" * (4 - len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception:
        return {}


def _codex_access_token_is_expiring(token: str, skew_seconds: int = 120) -> bool:
    """Check if an openai-codex access token is about to expire."""
    claims = _decode_jwt_claims(token)
    if not claims:
        return True
    exp = claims.get("exp", 0)
    import time

    return int(time.time()) + skew_seconds >= int(exp)


def read_credential_pool() -> list:
    """Read the credential pool from disk."""
    path = _get_auth_store_path().parent / "credentials.json"
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def write_credential_pool(pool: list) -> None:
    """Write the credential pool to disk."""
    path = _get_auth_store_path().parent / "credentials.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pool, f, indent=2)


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
            with open(env_path, encoding="utf-8") as f:
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
            with open(env_path, encoding="utf-8") as f:
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


def get_auth_key(provider: str) -> str | None:
    provider_lower = provider.lower()
    env_key = PROVIDER_ENV_MAP.get(provider_lower)
    if not env_key:
        return None
    return os.environ.get(env_key) or None


def get_nous_auth_status() -> dict[str, Any]:
    """Get Nous authentication status."""
    nous_key = get_auth_key("nous")
    return {
        "logged_in": bool(nous_key),
        "has_key": bool(nous_key),
    }
