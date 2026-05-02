"""Dump command for prometheus CLI."""

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from prometheus.config import PrometheusConfig, get_env_path, get_project_root, get_prometheus_home
from prometheus.constants_core import display_prometheus_home


def _get_git_commit(project_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(project_root),
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "(unknown)"


def _redact(value: str) -> str:
    from prometheus.redact import mask_secret

    return mask_secret(value)


def _gateway_status() -> str:
    try:
        from prometheus.cli.gateway import get_gateway_runtime_snapshot

        snapshot = get_gateway_runtime_snapshot()
        if snapshot.running:
            mode = snapshot.manager
            if snapshot.has_process_service_mismatch:
                mode = "manual"
            return f"running ({mode}, pid {snapshot.gateway_pids[0]})"
        if snapshot.service_installed and not snapshot.service_running:
            return f"stopped ({snapshot.manager})"
        return f"stopped ({snapshot.manager})"
    except Exception:
        return "unknown" if sys.platform.startswith(("linux", "darwin")) else "N/A"


def _count_skills(prometheus_home: Path) -> int:
    skills_dir = prometheus_home / "skills"
    if not skills_dir.is_dir():
        return 0
    count = 0
    for _item in skills_dir.rglob("SKILL.md"):
        count += 1
    return count


def _count_mcp_servers(config: dict) -> int:
    mcp = config.get("mcp", {})
    servers = mcp.get("servers", {})
    return len(servers)


def _cron_summary(prometheus_home: Path) -> str:
    jobs_file = prometheus_home / "cron" / "jobs.json"
    if not jobs_file.exists():
        return "0"
    try:
        with open(jobs_file, encoding="utf-8") as f:
            data = json.load(f)
        jobs = data.get("jobs", [])
        active = sum(1 for j in jobs if j.get("enabled", True))
        return f"{active} active / {len(jobs)} total"
    except Exception:
        return "(error reading)"


def _configured_platforms() -> list[str]:
    checks = {
        "telegram": "TELEGRAM_BOT_TOKEN",
        "discord": "DISCORD_BOT_TOKEN",
        "slack": "SLACK_BOT_TOKEN",
        "whatsapp": "WHATSAPP_ENABLED",
        "signal": "SIGNAL_HTTP_URL",
        "email": "EMAIL_ADDRESS",
        "sms": "TWILIO_ACCOUNT_SID",
        "matrix": "MATRIX_HOMESERVER_URL",
        "mattermost": "MATTERMOST_URL",
        "homeassistant": "HASS_TOKEN",
        "dingtalk": "DINGTALK_CLIENT_ID",
        "feishu": "FEISHU_APP_ID",
        "wecom": "WECOM_BOT_ID",
        "wecom_callback": "WECOM_CALLBACK_CORP_ID",
        "weixin": "WEIXIN_ACCOUNT_ID",
        "qqbot": "QQ_APP_ID",
    }
    return [name for name, env in checks.items() if os.getenv(env)]


def _memory_provider(config: dict) -> str:
    mem = config.get("memory", {})
    provider = mem.get("provider", "")
    return provider if provider else "built-in"


def _get_model_and_provider(config: dict) -> tuple[str, str]:
    model_cfg = config.get("model", "")
    if isinstance(model_cfg, dict):
        model = (
            model_cfg.get("default")
            or model_cfg.get("model")
            or model_cfg.get("name")
            or "(not set)"
        )
        provider = model_cfg.get("provider") or "(auto)"
    elif isinstance(model_cfg, str):
        model = model_cfg or "(not set)"
        provider = "(auto)"
    else:
        model = "(not set)"
        provider = "(auto)"
    return model, provider


def _config_overrides(config: dict) -> dict[str, str]:
    from prometheus.cli.config import DEFAULT_CONFIG

    overrides = {}

    interesting_paths = [
        ("agent", "max_turns"),
        ("agent", "gateway_timeout"),
        ("agent", "tool_use_enforcement"),
        ("terminal", "backend"),
        ("terminal", "docker_image"),
        ("terminal", "persistent_shell"),
        ("browser", "allow_private_urls"),
        ("compression", "enabled"),
        ("compression", "threshold"),
        ("display", "streaming"),
        ("display", "skin"),
        ("display", "show_reasoning"),
        ("privacy", "redact_pii"),
        ("tts", "provider"),
    ]

    for section, key in interesting_paths:
        default_section = DEFAULT_CONFIG.get(section, {})
        user_section = config.get(section, {})
        if not isinstance(default_section, dict) or not isinstance(user_section, dict):
            continue
        default_val = default_section.get(key)
        user_val = user_section.get(key)
        if user_val is not None and user_val != default_val:
            overrides[f"{section}.{key}"] = str(user_val)

    default_toolsets = DEFAULT_CONFIG.get("toolsets", [])
    user_toolsets = config.get("toolsets", [])
    if user_toolsets != default_toolsets:
        overrides["toolsets"] = str(user_toolsets)

    fallbacks = config.get("fallback_providers", [])
    if fallbacks:
        overrides["fallback_providers"] = str(fallbacks)

    return overrides


def run_dump(args):
    show_keys = getattr(args, "show_keys", False)

    from dotenv import load_dotenv

    env_path = get_env_path()
    if env_path.exists():
        try:
            load_dotenv(env_path, encoding="utf-8")
        except UnicodeDecodeError:
            load_dotenv(env_path, encoding="latin-1")
    load_dotenv(get_project_root() / ".env", override=False, encoding="utf-8")

    project_root = get_project_root()
    prometheus_home = get_prometheus_home()

    try:
        from prometheus.cli import __release_date__, __version__
    except ImportError:
        __version__ = "(unknown)"
        __release_date__ = ""

    commit = _get_git_commit(project_root)

    try:
        config = PrometheusConfig.load().to_dict()
    except Exception:
        config = {}

    model, provider = _get_model_and_provider(config)

    try:
        from prometheus.cli.profiles import get_active_profile_name

        profile = get_active_profile_name() or "(default)"
    except Exception:
        profile = "(default)"

    terminal_cfg = config.get("terminal", {})
    backend = terminal_cfg.get("backend", "local")

    try:
        import openai

        openai_ver = openai.__version__
    except ImportError:
        openai_ver = "not installed"

    os_info = f"{platform.system()} {platform.release()} {platform.machine()}"

    lines = []
    lines.append("--- prometheus dump ---")
    ver_str = f"{__version__}"
    if __release_date__:
        ver_str += f" ({__release_date__})"
    ver_str += f" [{commit}]"
    lines.append(f"version:          {ver_str}")
    lines.append(f"os:               {os_info}")
    lines.append(f"python:           {sys.version.split()[0]}")
    lines.append(f"openai_sdk:       {openai_ver}")
    lines.append(f"profile:          {profile}")
    lines.append(f"prometheus_home:  {display_prometheus_home()}")
    lines.append(f"model:            {model}")
    lines.append(f"provider:         {provider}")
    lines.append(f"terminal:         {backend}")

    lines.append("")
    lines.append("api_keys:")
    api_keys = [
        ("OPENROUTER_API_KEY", "openrouter"),
        ("OPENAI_API_KEY", "openai"),
        ("ANTHROPIC_API_KEY", "anthropic"),
        ("ANTHROPIC_TOKEN", "anthropic_token"),
        ("NOUS_API_KEY", "nous"),
        ("GOOGLE_API_KEY", "google/gemini"),
        ("GEMINI_API_KEY", "gemini"),
        ("GLM_API_KEY", "glm/zai"),
        ("ZAI_API_KEY", "zai"),
        ("KIMI_API_KEY", "kimi"),
        ("MINIMAX_API_KEY", "minimax"),
        ("DEEPSEEK_API_KEY", "deepseek"),
        ("DASHSCOPE_API_KEY", "dashscope"),
        ("HF_TOKEN", "huggingface"),
        ("NVIDIA_API_KEY", "nvidia"),
        ("AI_GATEWAY_API_KEY", "ai_gateway"),
        ("OPENCODE_ZEN_API_KEY", "opencode_zen"),
        ("OPENCODE_GO_API_KEY", "opencode_go"),
        ("KILOCODE_API_KEY", "kilocode"),
        ("FIRECRAWL_API_KEY", "firecrawl"),
        ("TAVILY_API_KEY", "tavily"),
        ("BROWSERBASE_API_KEY", "browserbase"),
        ("FAL_KEY", "fal"),
        ("ELEVENLABS_API_KEY", "elevenlabs"),
        ("GITHUB_TOKEN", "github"),
    ]

    for env_var, label in api_keys:
        val = os.getenv(env_var, "")
        if show_keys and val:
            display = _redact(val)
        else:
            display = "set" if val else "not set"
        lines.append(f"  {label:<20} {display}")

    lines.append("")
    lines.append("features:")

    toolsets = config.get("toolsets", ["prometheus-cli"])
    lines.append(f"  toolsets:           {', '.join(toolsets) if toolsets else '(default)'}")
    lines.append(f"  mcp_servers:        {_count_mcp_servers(config)}")
    lines.append(f"  memory_provider:    {_memory_provider(config)}")
    lines.append(f"  gateway:            {_gateway_status()}")

    platforms = _configured_platforms()
    lines.append(f"  platforms:          {', '.join(platforms) if platforms else 'none'}")
    lines.append(f"  cron_jobs:          {_cron_summary(prometheus_home)}")
    lines.append(f"  skills:             {_count_skills(prometheus_home)}")

    overrides = _config_overrides(config)
    if overrides:
        lines.append("")
        lines.append("config_overrides:")
        for key, val in overrides.items():
            lines.append(f"  {key}: {val}")

    lines.append("--- end dump ---")

    output = "\n".join(lines)
    print(output)
