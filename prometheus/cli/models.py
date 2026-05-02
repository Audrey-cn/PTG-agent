from __future__ import annotations

import json
import os
from typing import Any

try:
    from importlib.metadata import version

    _PROMETHEUS_VERSION = version("prometheus")
except Exception:
    _PROMETHEUS_VERSION = "0.8.0"

_PROMETHEUS_USER_AGENT = f"prometheus-cli/{_PROMETHEUS_VERSION}"


def provider_label(provider_name: str) -> str:
    """Return the display label for a provider name.

    Args:
        provider_name: Provider key (e.g. 'openai', 'anthropic').

    Returns:
        Human-readable label (e.g. 'OpenAI', 'Anthropic').
    """
    return CANONICAL_PROVIDERS.get(provider_name, {}).get("label", provider_name)


CANONICAL_PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {
        "label": "OpenAI",
        "env_var": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o3-mini"],
    },
    "anthropic": {
        "label": "Anthropic",
        "env_var": "ANTHROPIC_API_KEY",
        "base_url": "https://api.anthropic.com",
        "default_model": "claude-sonnet-4-20250514",
        "models": ["claude-3.5-sonnet", "claude-3-opus", "claude-3-haiku"],
    },
    "openrouter": {
        "label": "OpenRouter",
        "env_var": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "anthropic/claude-sonnet-4",
        "models": [
            "auto",
            "anthropic/claude-sonnet-4",
            "openai/gpt-4o",
            "google/gemini-2.5-pro-preview",
        ],
    },
    "vercel": {
        "label": "Vercel AI",
        "env_var": "VERCEL_AI_KEY",
        "base_url": "https://api.vercel.ai/v1",
        "default_model": "gpt-4o",
        "models": ["gpt-4o", "claude-3.5-sonnet"],
    },
    "deepseek": {
        "label": "DeepSeek",
        "env_var": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-v3", "deepseek-coder"],
    },
    "xai": {
        "label": "xAI",
        "env_var": "XAI_API_KEY",
        "base_url": "https://api.x.ai/v1",
        "default_model": "grok-2",
        "models": ["grok-2", "grok-2-vision"],
    },
    "google": {
        "label": "Google GenAI",
        "env_var": "GOOGLE_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com",
        "default_model": "gemini-2.0-flash",
        "models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
    },
    "github_copilot": {
        "label": "GitHub Copilot",
        "env_var": "GITHUB_TOKEN",
        "base_url": "https://api.github.com/copilot",
        "default_model": "gpt-4o",
        "models": ["gpt-4o", "gpt-4o-mini"],
    },
    "github_copilot_acp": {
        "label": "GitHub Copilot ACP",
        "env_var": "GITHUB_COPILOT_TOKEN",
        "base_url": "https://api.githubcopilot.com",
        "default_model": "gpt-4o",
        "models": ["gpt-4o", "claude-3.5-sonnet"],
    },
    "huggingface": {
        "label": "HuggingFace",
        "env_var": "HF_TOKEN",
        "base_url": "https://api-inference.huggingface.co/models",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct",
        "models": ["meta-llama/Llama-3.3-70B-Instruct", "mistralai/Mistral-7B-Instruct-v0.3"],
    },
    "nous_portal": {
        "label": "Nous Portal",
        "env_var": "NOUS_API_KEY",
        "base_url": "https://api.nousportal.com/v1",
        "default_model": "nous-prometheus-2",
        "models": ["nous-prometheus-2", "nous-capybara"],
    },
    "nvidia_nim": {
        "label": "NVIDIA NIM",
        "env_var": "NVIDIA_API_KEY",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "default_model": "meta/llama-3.1-405b-instruct",
        "models": ["meta/llama-3.1-405b-instruct", "meta/llama-3.1-70b-instruct"],
    },
    "qwen_oauth": {
        "label": "Qwen (OAuth)",
        "env_var": "QWEN_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/api/v1",
        "default_model": "qwen-max",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo"],
    },
    "xiaomi_mimo": {
        "label": "Xiaomi MiMo",
        "env_var": "XIAOMI_MIMO_API_KEY",
        "base_url": "https://api.xiaomi.com/mimo/v1",
        "default_model": "mimo-7b",
        "models": ["mimo-7b"],
    },
    "stepfun": {
        "label": "StepFun",
        "env_var": "STEPFUN_API_KEY",
        "base_url": "https://api.stepfun.com/v1",
        "default_model": "step-1-8k",
        "models": ["step-1-8k", "step-1-32k", "step-1-128k"],
    },
    "minimax": {
        "label": "MiniMax",
        "env_var": "MINIMAX_API_KEY",
        "base_url": "https://api.minimax.chat/v1",
        "default_model": "abab6.5-chat",
        "models": ["abab6.5-chat", "abab5.5-chat"],
    },
    "alibaba_cloud": {
        "label": "Alibaba Cloud",
        "env_var": "ALIBABA_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/api/v1",
        "default_model": "qwen-max",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo"],
    },
    "ollama_cloud": {
        "label": "Ollama Cloud",
        "env_var": "OLLAMA_CLOUD_API_KEY",
        "base_url": "https://api.ollama.cloud/v1",
        "default_model": "llama3.2",
        "models": ["llama3.2", "mistral", "phi3"],
    },
    "arcee_ai": {
        "label": "Arcee AI",
        "env_var": "ARCEE_API_KEY",
        "base_url": "https://api.arcee.ai/v1",
        "default_model": "arcee-lite",
        "models": ["arcee-lite", "arcee-blitz"],
    },
    "kilo_code": {
        "label": "Kilo Code",
        "env_var": "KILO_API_KEY",
        "base_url": "https://api.kilocode.ai/v1",
        "default_model": "kilo-7b",
        "models": ["kilo-7b"],
    },
    "opencode_zen": {
        "label": "OpenCode Zen",
        "env_var": "OPENCODE_API_KEY",
        "base_url": "https://api.opencode.dev/v1",
        "default_model": "zen-7b",
        "models": ["zen-7b"],
    },
    "opencode_go": {
        "label": "OpenCode Go",
        "env_var": "OPENCODE_GO_API_KEY",
        "base_url": "https://go.opencode.dev/v1",
        "default_model": "go-7b",
        "models": ["go-7b"],
    },
    "aws_bedrock": {
        "label": "AWS Bedrock",
        "env_var": "AWS_ACCESS_KEY_ID",
        "base_url": "https://bedrock-runtime.us-east-1.amazonaws.com",
        "default_model": "anthropic.claude-3-sonnet-20240229-v1:0",
        "models": [
            "anthropic.claude-3-sonnet-20240229-v1:0",
            "anthropic.claude-3-opus-20240229-v1:0",
        ],
    },
    "azure_foundry": {
        "label": "Azure AI Foundry",
        "env_var": "AZURE_OPENAI_API_KEY",
        "base_url": "https://your-resource.openai.azure.com",
        "default_model": "gpt-4o",
        "models": ["gpt-4o", "gpt-4o-mini"],
    },
    "local_ollama": {
        "label": "Local Ollama",
        "env_var": "OLLAMA_HOST",
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3.2",
        "models": ["llama3.2", "mistral", "phi3", "codellama"],
    },
    "custom": {
        "label": "Custom Provider",
        "env_var": "CUSTOM_API_KEY",
        "base_url": "",
        "default_model": "",
        "models": [],
    },
    "moonshot": {
        "label": "Moonshot",
        "env_var": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
    },
    "kimi": {
        "label": "Kimi",
        "env_var": "KIMI_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k"],
    },
    "zhipu": {
        "label": "ZhiPu",
        "env_var": "ZHIPU_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4",
        "models": ["glm-4", "glm-4-flash", "glm-4-plus"],
    },
}


def cmd_model(args) -> None:
    if hasattr(args, "list") and args.list:
        provider = getattr(args, "provider", None)
        cmd_model_list(provider)
        return
    if hasattr(args, "switch") and args.switch:
        cmd_model_switch(args.switch)
        return
    if hasattr(args, "probe") and args.probe:
        base_url = args.probe
        api_key = getattr(args, "api_key", None)
        cmd_model_probe(base_url, api_key)
        return
    if hasattr(args, "info") and args.info:
        cmd_model_info(args.info)
        return
    if hasattr(args, "action") and args.action:
        _handle_legacy_action(args)
        return
    _print_model_help()


def _handle_legacy_action(args) -> None:
    from prometheus.config import Config as PrometheusConfig

    cfg = PrometheusConfig.load()
    if args.action == "show":
        print("\n🤖 模型配置\n")
        model_cfg = cfg.to_dict().get("model", {})
        for k, v in model_cfg.items():
            print(f"  {k}: {v}")
    elif args.action == "set":
        if not args.key or not args.value:
            print("用法: ptg model set <key> <value>")
            return
        cfg.set("model", args.key, args.value)
        cfg.save()
        print(f"✅ 模型配置已更新: {args.key} = {args.value}")
    elif args.action == "providers":
        print("\n🤖 支持的提供者\n")
        for pid, spec in CANONICAL_PROVIDERS.items():
            print(f"  · {pid:<18} {spec['label']:<20} 认证: {spec['env_var']}")
    else:
        _print_model_help()


def _print_model_help() -> None:
    print("\n🤖 模型管理\n")
    print("  用法:")
    print("    ptg model list [--provider <名称>]  列出模型")
    print("    ptg model switch <模型名>           切换模型")
    print("    ptg model probe <base_url> [--api-key]  探测端点")
    print("    ptg model info <模型名>             查看模型信息")
    print("    ptg model show                      查看当前配置")
    print("    ptg model set <key> <value>         修改配置")
    print("    ptg model providers                 列出提供者\n")


def cmd_model_list(provider: str | None = None) -> None:
    from prometheus.model_catalog import list_models as catalog_list

    print("\n🤖 模型列表\n")
    if provider:
        spec = CANONICAL_PROVIDERS.get(provider)
        if not spec:
            print(f"❌ 未知提供者: {provider}")
            return
        print(f"  提供者: {spec['label']}\n")
        models = catalog_list(provider)
        if not models:
            models = [{"id": m, "description": ""} for m in spec.get("models", [])]
        for m in models:
            model_id = m.get("id", m) if isinstance(m, dict) else m
            desc = m.get("description", "") if isinstance(m, dict) else ""
            print(f"  · {model_id}")
            if desc:
                print(f"    {desc[:60]}")
    else:
        for pid, spec in CANONICAL_PROVIDERS.items():
            print(f"  [{spec['label']}]")
            models = catalog_list(pid)
            if not models:
                models = [{"id": m} for m in spec.get("models", [])[:3]]
            for m in models[:3]:
                model_id = m.get("id", m) if isinstance(m, dict) else m
                print(f"    · {model_id}")
            if len(spec.get("models", [])) > 3:
                print(f"    ... 还有 {len(spec['models']) - 3} 个")
            print()


def cmd_model_switch(model_name: str) -> None:
    from prometheus.cli.providers import resolve_provider
    from prometheus.config import Config as PrometheusConfig

    cfg = PrometheusConfig.load()
    provider = resolve_provider(model_name)
    cfg.set("model.name", model_name)
    if provider:
        cfg.set("model.provider", provider)
    cfg.save()
    print(f"\n✅ 已切换到模型: {model_name}")
    if provider:
        print(f"   提供者: {provider}\n")


def cmd_model_probe(base_url: str, api_key: str | None = None) -> None:
    import urllib.error
    import urllib.request

    print(f"\n🔍 探测端点: {base_url}\n")
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("❌ 未提供 API Key，设置 --api-key 或 OPENAI_API_KEY 环境变量")
        return
    models_url = base_url.rstrip("/") + "/models"
    try:
        req = urllib.request.Request(models_url, headers={"Authorization": f"Bearer {api_key}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        models = data.get("data", [])
        if not models:
            print("  未找到模型")
            return
        print(f"  发现 {len(models)} 个模型:\n")
        for m in models[:20]:
            model_id = m.get("id", "?")
            print(f"    · {model_id}")
        if len(models) > 20:
            print(f"    ... 还有 {len(models) - 20} 个")
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP 错误: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        print(f"❌ 连接失败: {e.reason}")
    except Exception as e:
        print(f"❌ 探测失败: {e}")


def cmd_model_info(model_name: str) -> None:
    from prometheus.model_catalog import get_model_info

    print(f"\n🔍 模型信息: {model_name}\n")
    info = get_model_info(model_name)
    if info:
        print(f"  ID: {info.get('id', '?')}")
        print(f"  描述: {info.get('description', '无')}")
        print(f"  上下文长度: {info.get('context_length', '?')}")
        pricing = info.get("pricing", {})
        if pricing:
            print(
                f"  价格 (输入/输出): ${pricing.get('in', 0)}/${pricing.get('out', 0)} per 1M tokens"
            )
    else:
        print("  未在目录中找到，可能是自定义模型")
        for _pid, spec in CANONICAL_PROVIDERS.items():
            if model_name in spec.get("models", []):
                print(f"  提供者: {spec['label']}")
                print(f"  默认端点: {spec['base_url']}")
                break
    print()
