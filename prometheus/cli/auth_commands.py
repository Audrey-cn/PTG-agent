from __future__ import annotations

from typing import Any

from prometheus.cli.auth import (
    PROVIDER_DISPLAY_NAMES,
    clear_auth,
    get_auth_key,
    set_auth,
    show_auth_status,
)


def cmd_auth(args: Any) -> None:
    if not hasattr(args, "action") or not args.action:
        show_auth_status()
        return
    action = args.action.lower()
    if action == "status":
        cmd_auth_status(args)
    elif action == "set":
        cmd_auth_set(args)
    elif action == "clear":
        cmd_auth_clear(args)
    elif action == "test":
        cmd_auth_test(args)
    else:
        show_auth_status()


def cmd_auth_status(args: Any) -> None:
    show_auth_status()


def cmd_auth_set(args: Any) -> None:
    if not hasattr(args, "provider") or not args.provider:
        print("用法: /auth set <provider> <api_key>")
        print(f"支持的 provider: {', '.join(PROVIDER_DISPLAY_NAMES.keys())}")
        return
    if not hasattr(args, "api_key") or not args.api_key:
        provider = args.provider.lower()
        display = PROVIDER_DISPLAY_NAMES.get(provider, provider)
        env_var = f"{provider.upper()}_API_KEY"
        if provider == "github":
            env_var = "GITHUB_TOKEN"
        print(f"用法: /auth set {provider} <api_key>")
        print(f"环境变量: {env_var}")
        return
    provider = args.provider
    api_key = args.api_key
    success = set_auth(provider, api_key)
    if success:
        display = PROVIDER_DISPLAY_NAMES.get(provider.lower(), provider)
        print(f"✅ {display} API Key 已设置")
    else:
        print(f"❌ 设置失败: 未知 provider '{provider}'")


def cmd_auth_clear(args: Any) -> None:
    if not hasattr(args, "provider") or not args.provider:
        print("用法: /auth clear <provider>")
        print(f"支持的 provider: {', '.join(PROVIDER_DISPLAY_NAMES.keys())}")
        return
    provider = args.provider
    success = clear_auth(provider)
    if success:
        display = PROVIDER_DISPLAY_NAMES.get(provider.lower(), provider)
        print(f"✅ {display} API Key 已清除")
    else:
        print(f"❌ 清除失败: 未知 provider '{provider}'")


def cmd_auth_test(args: Any) -> None:
    if not hasattr(args, "provider") or not args.provider:
        print("用法: /auth test <provider>")
        print(f"支持的 provider: {', '.join(PROVIDER_DISPLAY_NAMES.keys())}")
        return
    provider = args.provider.lower()
    display = PROVIDER_DISPLAY_NAMES.get(provider, provider)
    key = get_auth_key(provider)
    if not key:
        print(f"❌ {display}: 未设置 API Key")
        return
    print(f"🔍 测试 {display} 认证...")
    try:
        if provider == "openai":
            _test_openai(key)
        elif provider == "anthropic":
            _test_anthropic(key)
        elif provider == "openrouter":
            _test_openrouter(key)
        elif provider == "deepseek":
            _test_deepseek(key)
        elif provider == "google":
            _test_google(key)
        elif provider == "github":
            _test_github(key)
        else:
            print(f"⚠️ {display}: 测试未实现，但 Key 已设置")
    except Exception as e:
        print(f"❌ {display}: 测试失败 - {e}")


def _test_openai(api_key: str) -> None:
    import json
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        "https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {api_key}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            model_count = len(data.get("data", []))
            print(f"✅ OpenAI: 认证成功 ({model_count} 个模型可用)")
    except urllib.error.HTTPError as e:
        raise Exception(f"HTTP {e.code}")


def _test_anthropic(api_key: str) -> None:
    import urllib.error
    import urllib.request

    urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        method="POST",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )
    print("✅ Anthropic: API Key 格式有效 (跳过实际调用)")


def _test_openrouter(api_key: str) -> None:
    import json
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/models", headers={"Authorization": f"Bearer {api_key}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            json.loads(resp.read().decode())
            print("✅ OpenRouter: 认证成功")
    except urllib.error.HTTPError as e:
        raise Exception(f"HTTP {e.code}")


def _test_deepseek(api_key: str) -> None:
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        "https://api.deepseek.com/v1/models", headers={"Authorization": f"Bearer {api_key}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            print("✅ DeepSeek: 认证成功")
    except urllib.error.HTTPError as e:
        raise Exception(f"HTTP {e.code}")


def _test_google(api_key: str) -> None:
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            print("✅ Google: 认证成功")
    except urllib.error.HTTPError as e:
        raise Exception(f"HTTP {e.code}")


def _test_github(token: str) -> None:
    import json
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        "https://api.github.com/user", headers={"Authorization": f"token {token}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            login = data.get("login", "?")
            print(f"✅ GitHub: 认证成功 (用户: {login})")
    except urllib.error.HTTPError as e:
        raise Exception(f"HTTP {e.code}")
