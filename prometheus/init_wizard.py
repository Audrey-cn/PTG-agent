import getpass
import json
import os
import urllib.error
import urllib.request

from prometheus.config import Config, get_prometheus_home

__version__ = "0.8.0"

try:
    from colorama import Fore, Style, init

    init()
    C = Fore
    S = Style
except ImportError:

    class _NoColor:
        def __getattr__(self, name):
            return ""

    C = _NoColor()
    S = _NoColor()

PROVIDERS = [
    ("openrouter", "OpenRouter", "OPENROUTER_API_KEY", "100+ models, pay-per-use"),
    ("nous", "Nous Portal", None, "Nous Research subscription (OAuth)"),
    ("ai-gateway", "Vercel AI Gateway", "AI_GATEWAY_API_KEY", "200+ models, $5 credit, no markup"),
    ("anthropic", "Anthropic", "ANTHROPIC_API_KEY", "Claude models — API key"),
    ("openai", "OpenAI", "OPENAI_API_KEY", "GPT-4o, o3, o4-mini"),
    ("openai-codex", "OpenAI Codex", None, "Codex coding agent (OAuth)"),
    ("xiaomi", "Xiaomi MiMo", "XIAOMI_API_KEY", "MiMo-V2.5 pro/omni/flash"),
    ("nvidia", "NVIDIA NIM", "NVIDIA_API_KEY", "Nemotron models"),
    ("qwen-oauth", "Qwen OAuth (Portal)", None, "Qwen OAuth — local CLI login"),
    ("copilot", "GitHub Copilot", "GITHUB_TOKEN", "Uses gh auth token"),
    ("copilot-acp", "GitHub Copilot ACP", None, "Subprocess copilot --acp --stdio"),
    ("huggingface", "Hugging Face", "HF_TOKEN", "20+ open models via Inference Providers"),
    ("gemini", "Google AI Studio", "GOOGLE_API_KEY", "Gemini models — native API"),
    ("google-gemini-cli", "Google Gemini (OAuth)", None, "OAuth + Code Assist, free tier"),
    ("deepseek", "DeepSeek", "DEEPSEEK_API_KEY", "V3, R1, coder — direct API"),
    ("xai", "xAI", "XAI_API_KEY", "Grok models"),
    ("zai", "Z.AI / GLM", "GLM_API_KEY", "Zhipu AI direct API"),
    ("kimi-coding", "Kimi / Moonshot", "KIMI_API_KEY", "Kimi Coding Plan"),
    ("kimi-coding-cn", "Kimi / Moonshot (China)", "KIMI_CN_API_KEY", "Moonshot CN direct API"),
    ("stepfun", "StepFun Step Plan", "STEPFUN_API_KEY", "Agent/coding models"),
    ("minimax", "MiniMax", "MINIMAX_API_KEY", "Global direct API"),
    ("minimax-cn", "MiniMax (China)", "MINIMAX_CN_API_KEY", "Domestic direct API"),
    ("alibaba", "Alibaba Cloud (DashScope)", "DASHSCOPE_API_KEY", "Qwen + multi-provider"),
    ("ollama-cloud", "Ollama Cloud", "OLLAMA_API_KEY", "Cloud-hosted open models"),
    ("arcee", "Arcee AI", "ARCEEAI_API_KEY", "Trinity models"),
    ("kilocode", "Kilo Code", "KILOCODE_API_KEY", "Kilo Gateway API"),
    ("opencode-zen", "OpenCode Zen", "OPENCODE_ZEN_API_KEY", "35+ curated models, pay-as-you-go"),
    ("opencode-go", "OpenCode Go", "OPENCODE_GO_API_KEY", "Open models, $10/month"),
    ("bedrock", "AWS Bedrock", None, "Claude, Nova, Llama — IAM/SDK"),
    ("azure-foundry", "Azure Foundry", "AZURE_FOUNDRY_API_KEY", "Your Azure AI deployment"),
    ("ollama", "本地 Ollama", None, "自托管本地模型"),
    ("custom", "自定义 OpenAI-compatible", None, "任意兼容端点"),
]

PROVIDER_DEFAULTS = {
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "model": "openai/gpt-4o"},
    "nous": {
        "base_url": "https://inference-api.nousresearch.com/v1",
        "model": "hermes-3-llama-3.2-3b",
    },
    "ai-gateway": {"base_url": "https://ai-gateway.vercel.sh/v1", "model": "gpt-4o"},
    "anthropic": {"base_url": "https://api.anthropic.com/v1", "model": "claude-sonnet-4-20250514"},
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o"},
    "openai-codex": {"base_url": "https://chatgpt.com/backend-api/codex", "model": "codex"},
    "xiaomi": {"base_url": "https://api.xiaomimimo.com/v1", "model": "mimo-v2.5-pro"},
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "nvidia/nemotron-4-340b-instruct",
    },
    "qwen-oauth": {"base_url": "https://portal.qwen.ai/v1", "model": "qwen-max"},
    "copilot": {"base_url": "https://api.githubcopilot.com", "model": "gpt-4o"},
    "copilot-acp": {"base_url": "acp://copilot", "model": "gpt-4o"},
    "huggingface": {
        "base_url": "https://router.huggingface.co/v1",
        "model": "meta-llama/Llama-3.3-70B-Instruct",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "model": "gemini-2.5-flash",
    },
    "google-gemini-cli": {"base_url": "cloudcode-pa://google", "model": "gemini-2.5-flash"},
    "deepseek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    "xai": {"base_url": "https://api.x.ai/v1", "model": "grok-3"},
    "zai": {"base_url": "https://api.z.ai/api/paas/v4", "model": "glm-4"},
    "kimi-coding": {"base_url": "https://api.moonshot.ai/v1", "model": "kimi-latest"},
    "kimi-coding-cn": {"base_url": "https://api.moonshot.cn/v1", "model": "kimi-latest"},
    "stepfun": {"base_url": "https://api.stepfun.ai/step_plan/v1", "model": "step-2-16k"},
    "minimax": {"base_url": "https://api.minimax.io/anthropic", "model": "MiniMax-M1"},
    "minimax-cn": {"base_url": "https://api.minimaxi.com/anthropic", "model": "MiniMax-M1"},
    "alibaba": {
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-max",
    },
    "ollama-cloud": {"base_url": "https://ollama.com/v1", "model": "llama3.3"},
    "arcee": {"base_url": "https://api.arcee.ai/api/v1", "model": "arcee-trinity"},
    "kilocode": {"base_url": "https://api.kilo.ai/api/gateway", "model": "gpt-4o"},
    "opencode-zen": {"base_url": "https://opencode.ai/zen/v1", "model": "gpt-4o"},
    "opencode-go": {"base_url": "https://opencode.ai/zen/go/v1", "model": "gpt-4o"},
    "bedrock": {
        "base_url": "https://bedrock-runtime.us-east-1.amazonaws.com",
        "model": "us.anthropic.claude-sonnet-4-20250514-v1:0",
    },
    "azure-foundry": {"base_url": "", "model": ""},
    "ollama": {"base_url": "http://localhost:11434/v1", "model": "qwen2.5-coder:32b"},
    "custom": {"base_url": "", "model": ""},
}

CHANNELS = [
    ("cli", "CLI 命令行", True, None),
    ("telegram", "Telegram 机器人", False, "python-telegram-bot"),
    ("discord", "Discord 机器人", False, "discord.py"),
    ("slack", "Slack", False, "slack-bolt"),
    ("signal", "Signal", False, None),
    ("email", "Email (SMTP)", False, None),
    ("sms", "SMS (Twilio)", False, None),
    ("matrix", "Matrix", False, None),
    ("mattermost", "Mattermost", False, None),
    ("whatsapp", "WhatsApp", False, None),
    ("dingtalk", "钉钉 (DingTalk)", False, "dingtalk-stream"),
    ("feishu", "飞书 / Lark", False, "lark-oapi"),
    ("yuanbao", "元宝 (Yuanbao)", False, None),
    ("wecom", "企业微信 (WeCom)", False, None),
    ("wecom-callback", "企微回调 (WeCom Callback)", False, None),
    ("weixin", "微信 (WeChat)", False, None),
    ("bluebubbles", "BlueBubbles (iMessage)", False, None),
    ("qqbot", "QQ Bot", False, None),
    ("webhook", "HTTP Webhook", False, "fastapi"),
]

TOOL_MODULES = [
    ("memory", "记忆系统", "核心记忆管理", "stable"),
    ("knowledge", "知识编译器", "语义知识编译与检索", "stable"),
    ("seed_editor", "种子编辑器", "TTG 种子编辑与解码", "stable"),
    ("chronicler", "史诗编史官", "烙印/追溯/附史", "stable"),
    ("audit", "语义审核", "格式无关内容审核", "stable"),
    ("skin", "皮肤引擎", "CLI 视觉主题", "stable"),
    ("backup", "备份恢复", "配置与记忆备份", "stable"),
    ("cron", "定时任务", "Cron 定时调度", "beta"),
    ("sandbox", "代码沙箱", "安全代码执行", "beta"),
    ("gateway", "消息网关", "多频道消息路由", "beta"),
    ("mcp", "MCP 协议", "Model Context Protocol", "experimental"),
]


def _prompt(text, default="", password=False):
    prompt_fn = getpass.getpass if password else input
    try:
        return prompt_fn(text).strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return ""


def _prompt_yes_no(question, default=True):
    default_str = "Y/n" if default else "y/N"
    while True:
        try:
            v = input(f"{question} [{default_str}]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return default
        if not v:
            return default
        if v in ("y", "yes"):
            return True
        if v in ("n", "no"):
            return False
        print("请输入 'y' 或 'n'")


def _prompt_choice(question, choices, default=0):
    print(f"\n{question}")
    for i, label in enumerate(choices):
        marker = "●" if i == default else "○"
        print(f"  {marker} {i + 1}. {label}")
    print()
    while True:
        try:
            v = input(f"  选择 [1-{len(choices)}] (直接回车={default + 1}): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return default
        if not v:
            return default
        try:
            idx = int(v) - 1
            if 0 <= idx < len(choices):
                return idx
        except ValueError:
            pass
        print(f"  请输入 1-{len(choices)} 之间的数字")


def _prompt_checklist(question, items, pre_selected=None):
    pre = set(pre_selected or [])
    print(f"\n{question}")
    print("  输入编号选择，多个用逗号分隔 (如: 1,3,5)")
    print("  输入 'all' 全选，直接回车保持默认\n")
    for i, label in enumerate(items):
        mark = "✅" if i in pre else "⬜"
        print(f"  {mark} {i + 1}. {label}")
    print()
    while True:
        try:
            v = input("  选择: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return list(pre)
        if not v:
            return list(pre)
        if v == "all":
            return list(range(len(items)))
        try:
            indices = [int(x.strip()) - 1 for x in v.split(",")]
            valid = [i for i in indices if 0 <= i < len(items)]
            if valid:
                return valid
        except ValueError:
            pass
        print("  请输入有效的编号 (如 1,3,5) 或 'all'")


def _fetch_ollama_models(timeout=3.0):
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            return [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        return []


def _can_import(module_name):
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def _print_header(title):
    width = 59
    print()
    print(f" {C.CYAN}{'─' * width}{S.RESET_ALL}")
    print(f" {C.CYAN}{title}{S.RESET_ALL}")
    print(f" {C.CYAN}{'─' * width}{S.RESET_ALL}")


def _print_success(msg):
    print(f" {C.GREEN}✓{S.RESET_ALL} {msg}")


def _print_warn(msg):
    print(f" {C.YELLOW}⚠{S.RESET_ALL} {msg}")


def _print_info(msg):
    print(f" {C.CYAN}▶{S.RESET_ALL} {msg}")


def _print_done():
    print()
    print(f" {C.GREEN}{'═' * 59}{S.RESET_ALL}")
    print(f" {C.GREEN}  ✓ 初始化完成 — Prometheus 已就绪{S.RESET_ALL}")
    print(f" {C.GREEN}{'═' * 59}{S.RESET_ALL}")


def _print_provider_table(providers, detected_env_vars):
    half = (len(providers) + 1) // 2
    for i in range(half):
        left_pid, left_label, left_env, left_desc = providers[i]
        left_key = ""
        if left_env and left_env in detected_env_vars:
            left_key = f" {C.GREEN}✓{S.RESET_ALL}"
        left_str = f"{left_label}{left_key}"
        left_line = f"  {C.CYAN}{i + 1:>2}.{S.RESET_ALL} {left_str:<28}"

        right_idx = i + half
        if right_idx < len(providers):
            right_pid, right_label, right_env, right_desc = providers[right_idx]
            right_key = ""
            if right_env and right_env in detected_env_vars:
                right_key = f" {C.GREEN}✓{S.RESET_ALL}"
            right_str = f"{right_label}{right_key}"
            right_line = f"{C.CYAN}{right_idx + 1:>2}.{S.RESET_ALL} {right_str:<28}"
            print(f"{left_line}{right_line}")
        else:
            print(left_line)


def _fetch_custom_models(base_url, api_key, timeout=8.0):
    if not base_url:
        return None
    normalized = base_url.strip().rstrip("/")
    candidates = [(normalized, False)]
    if normalized.endswith("/v1"):
        alt = normalized[:-3].rstrip("/")
    else:
        alt = normalized + "/v1"
    if alt and alt != normalized:
        candidates.append((alt, True))
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    for candidate_base, is_fallback in candidates:
        url = f"{candidate_base.rstrip('/')}/models"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
                models = [m.get("id", "") for m in data.get("data", [])]
                if models:
                    return {
                        "models": models,
                        "resolved_base_url": candidate_base.rstrip("/"),
                        "fallback": is_fallback,
                    }
        except Exception:
            continue
    return None


def step0_language(config):
    _print_header("Step 0 · 语言 / Language")

    print()
    print("  ● 1. 中文 (Chinese)")
    print("  ○ 2. English")
    print()
    while True:
        try:
            v = input("  选择 / Select [1-2] (1): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            v = ""
        if not v:
            v = "1"
        if v == "1":
            config.set("system.language", "zh")
            _print_success("界面语言设置为 中文")
            return
        elif v == "2":
            config.set("system.language", "en")
            _print_success("Interface language set to English")
            return
        print("  请输入 1 或 2 / Please enter 1 or 2")


def run_setup():
    print()
    print(f" {C.YELLOW}{'═' * 59}{S.RESET_ALL}")
    print(f" {C.YELLOW}🔥 Prometheus · 史诗编史官 — 初始化向导{S.RESET_ALL}")
    print(f" {C.YELLOW}   Teach-To-Grow v{__version__}{S.RESET_ALL}")
    print(f" {C.YELLOW}{'═' * 59}{S.RESET_ALL}")

    config = Config()

    step0_language(config)
    step1_provider(config)
    step2_channels(config)
    step3_tools(config)
    if not step4_confirm(config):
        return False
    step5_finish(config)

    return True


def step1_provider(config):
    _print_header("Step 1 · 模型提供者")

    detected_env_vars = set()
    detected = []
    for pid, label, env_var, _desc in PROVIDERS:
        if env_var and os.getenv(env_var):
            detected_env_vars.add(env_var)
            detected.append((pid, label, env_var))

    if detected:
        _print_info("检测到以下环境变量 Key：")
        for pid, label, env_var in detected:
            print(f"  {C.GREEN}✅{S.RESET_ALL} {label} ({env_var})")

    provider_labels = []
    for pid, label, env_var, _desc in PROVIDERS:
        has_key = env_var and env_var in detected_env_vars
        marker = " ✓已设置" if has_key else ""
        provider_labels.append(f"{label}{marker}")

    choice = _prompt_choice("  选择模型提供者：", provider_labels, 0)
    pid, label, env_var, desc = PROVIDERS[choice]

    defaults = PROVIDER_DEFAULTS.get(pid, {})
    config.set("model.provider", pid)

    auth_types = {
        "nous": "OAuth",
        "openai-codex": "OAuth",
        "qwen-oauth": "OAuth",
        "google-gemini-cli": "OAuth",
        "copilot-acp": "external_process",
        "bedrock": "AWS SDK/IAM",
        "copilot": "gh auth token",
    }

    if pid == "ollama":
        _print_info("正在检测本地 Ollama 服务...")
        local_models = _fetch_ollama_models()
        if local_models:
            _print_success(f"检测到 {len(local_models)} 个本地模型")
            print(f"  可用模型: {', '.join(local_models[:5])}")
            if len(local_models) > 5:
                print(f"  ... 还有 {len(local_models) - 5} 个模型")
            choice = _prompt_choice("  选择模型：", local_models, 0)
            selected_model = local_models[choice]
        else:
            _print_warn("未检测到本地模型，请手动输入")
            selected_model = _prompt("  模型名称：", default="llama3")

        config.set("api.base_url", "http://localhost:11434/v1")
        config.set("model.name", selected_model)
        _print_success(f"本地模型 {selected_model} 已配置")
        return

    if pid in ("bedrock", "copilot-acp", "google-gemini-cli", "qwen-oauth", "openai-codex", "nous"):
        auth_note = auth_types.get(pid, "特殊认证")
        _print_info(f"{label} 使用 {auth_note} 认证方式。")
        if pid == "bedrock":
            region = _prompt("  AWS Region：", default="us-east-1")
            config.set(
                "api.base_url", f"https://bedrock-runtime.{region or 'us-east-1'}.amazonaws.com"
            )
        elif pid == "copilot-acp":
            _print_info("将使用本地 copilot --acp --stdio 子进程")
        else:
            config.set("api.base_url", defaults.get("base_url", ""))

        model = _prompt("  默认模型：", default=defaults.get("model", ""))
        config.set("model.name", model or defaults.get("model", ""))
        _print_success(f"{label} 已配置")
        return

    if env_var and env_var in detected_env_vars:
        use_env = _prompt_yes_no(f"  使用环境变量 {env_var}？", True)
        if use_env:
            config.set("api.key", "")
            config.set("api.base_url", defaults.get("base_url", ""))
            default_model = defaults.get("model", "")
            model = _prompt("  默认模型：", default=default_model)
            config.set("model.name", model or default_model)

            custom_model_choice = _prompt_yes_no("  是否额外指定自定义模型？", False)
            if custom_model_choice:
                custom_model = _prompt("  自定义模型名称：")
                if custom_model:
                    config.set("model.name", custom_model)

            if pid == "custom":
                custom_url = _prompt("  Base URL：", default=defaults.get("base_url", ""))
                if custom_url:
                    config.set("api.base_url", custom_url)
            _print_success(f"{label} 已配置 (使用环境变量)")
            return

    if pid == "custom":
        base_url = _prompt("  Base URL (例如 https://api.openai.com/v1)：")
        if base_url:
            config.set("api.base_url", base_url)
        api_key = _prompt("  API Key：", password=True)
        if api_key:
            config.set("api.key", api_key)
        probe = _fetch_custom_models(base_url or "", api_key or "")
        if probe and probe.get("models"):
            _models = probe["models"]
            _print_success(f"从端点探测到 {len(_models)} 个模型")
            if probe.get("fallback"):
                _print_info(f"端点路径已修正为 {probe['resolved_base_url']}")
                config.set("api.base_url", probe["resolved_base_url"])
            print()
            for i, m in enumerate(_models[:20], 1):
                print(f"  {i:>2}. {m}")
            if len(_models) > 20:
                print(f"  ... 还有 {len(_models) - 20} 个模型未显示")
            pick = _prompt(f"  选择模型 [1-{min(len(_models), 20)}] 或直接输入名称：")
            if pick.isdigit() and 1 <= int(pick) <= min(len(_models), 20):
                config.set("model.name", _models[int(pick) - 1])
            elif pick:
                config.set("model.name", pick)
            else:
                config.set("model.name", _models[0])
        else:
            _print_info("无法探测端点模型列表，将手动设置")
            default_model = "gpt-4o"
            model = _prompt("  默认模型：", default=default_model)
            config.set("model.name", model or default_model)
        max_tokens = _prompt("  Max Tokens：", default="4096")
        try:
            config.set("model.max_tokens", int(max_tokens or 4096))
        except ValueError:
            config.set("model.max_tokens", 4096)
        temp_val = _prompt("  Temperature (0.0-2.0)：", default="0.7")
        try:
            config.set("model.temperature", float(temp_val or 0.7))
        except ValueError:
            config.set("model.temperature", 0.7)
        _print_success(f"{label} 已配置")
        return
    elif env_var:
        api_key = _prompt(f"  {label} API Key ({env_var})：", password=True)
        if api_key:
            config.set("api.key", api_key)
        config.set("api.base_url", defaults.get("base_url", ""))
    else:
        config.set("api.base_url", defaults.get("base_url", ""))

    default_model = defaults.get("model", "gpt-4o")
    model = _prompt("  默认模型：", default=default_model)
    config.set("model.name", model or default_model)

    custom_model_choice = _prompt_yes_no("  是否额外指定自定义模型？", False)
    if custom_model_choice:
        custom_model = _prompt("  自定义模型名称：")
        if custom_model:
            config.set("model.name", custom_model)

    max_tokens = _prompt("  Max Tokens：", default="4096")
    try:
        config.set("model.max_tokens", int(max_tokens or 4096))
    except ValueError:
        config.set("model.max_tokens", 4096)

    temp_val = _prompt("  Temperature (0.0-2.0)：", default="0.7")
    try:
        config.set("model.temperature", float(temp_val or 0.7))
    except ValueError:
        config.set("model.temperature", 0.7)

    _print_success(f"{label} 已配置")


def step2_channels(config):
    _print_header("Step 2 · 消息频道")

    _print_info("选择要启用的消息频道，可多选：")

    items = []
    pre_selected = [0]
    for _i, (cid, label, _always_on, _dep) in enumerate(CHANNELS):
        dep_str = ""
        if _dep and not _can_import(_dep):
            dep_str = f" {C.RED}(依赖缺失: pip install {_dep}){S.RESET_ALL}"
        items.append(f"{label}{dep_str}")

    selected = _prompt_checklist("选择频道（直接回车保持默认）：", items, pre_selected)

    channels_config = {}
    for idx in selected:
        cid, label, always_on, dep = CHANNELS[idx]
        if dep and not _can_import(dep):
            _print_warn(f"{label} 依赖未安装，将跳过。可稍后补装：pip install {dep}")
            continue

        channels_config[cid] = {"enabled": True}

        if cid == "cli":
            pass
        elif cid == "telegram":
            token = _prompt("  Telegram Bot Token：", password=True)
            if token:
                channels_config["telegram"]["token"] = token
                home = _prompt("  Home Channel ID (可选)：")
                if home:
                    channels_config["telegram"]["home_channel"] = home
            else:
                _print_warn("未输入 Token，Telegram 频道将禁用")
                channels_config["telegram"]["enabled"] = False
        elif cid == "discord":
            token = _prompt("  Discord Bot Token：", password=True)
            if token:
                channels_config["discord"]["token"] = token
            else:
                channels_config["discord"]["enabled"] = False
        elif cid == "slack":
            token = _prompt("  Slack Bot Token (xoxb-...)：", password=True)
            if token:
                channels_config["slack"]["token"] = token
            app_token = _prompt("  Slack App Token (xapp-...)：", password=True)
            if app_token:
                channels_config["slack"]["app_token"] = app_token
        elif cid == "signal":
            url = _prompt("  Signal HTTP URL：")
            if url:
                channels_config["signal"]["url"] = url
            else:
                channels_config["signal"]["enabled"] = False
        elif cid == "email":
            addr = _prompt("  Email Address：")
            smtp = _prompt("  SMTP Server：", default="smtp.gmail.com")
            if addr:
                channels_config["email"]["address"] = addr
                channels_config["email"]["smtp_server"] = smtp or "smtp.gmail.com"
            else:
                channels_config["email"]["enabled"] = False
        elif cid == "sms":
            sid = _prompt("  Twilio Account SID：")
            token = _prompt("  Twilio Auth Token：", password=True)
            if sid and token:
                channels_config["sms"]["sid"] = sid
                channels_config["sms"]["token"] = token
            else:
                channels_config["sms"]["enabled"] = False
        elif cid == "matrix":
            token = _prompt("  Matrix Access Token：", password=True)
            if token:
                channels_config["matrix"]["token"] = token
            else:
                channels_config["matrix"]["enabled"] = False
        elif cid == "mattermost":
            token = _prompt("  Mattermost Token：", password=True)
            if token:
                channels_config["mattermost"]["token"] = token
            else:
                channels_config["mattermost"]["enabled"] = False
        elif cid == "whatsapp":
            channels_config["whatsapp"]["enabled"] = True
            _print_info("WhatsApp 已启用（需额外配置）")
        elif cid == "dingtalk":
            client_id = _prompt("  钉钉 Client ID：")
            client_secret = _prompt("  钉钉 Client Secret：", password=True)
            if client_id and client_secret:
                channels_config["dingtalk"]["client_id"] = client_id
                channels_config["dingtalk"]["client_secret"] = client_secret
            else:
                channels_config["dingtalk"]["enabled"] = False
        elif cid == "feishu":
            app_id = _prompt("  飞书 App ID：")
            app_secret = _prompt("  飞书 App Secret：", password=True)
            if app_id and app_secret:
                channels_config["feishu"]["app_id"] = app_id
                channels_config["feishu"]["app_secret"] = app_secret
            else:
                channels_config["feishu"]["enabled"] = False
        elif cid == "yuanbao":
            app_id = _prompt("  元宝 App ID：")
            app_secret = _prompt("  元宝 App Secret：", password=True)
            if app_id and app_secret:
                channels_config["yuanbao"]["app_id"] = app_id
                channels_config["yuanbao"]["app_secret"] = app_secret
            else:
                channels_config["yuanbao"]["enabled"] = False
        elif cid == "wecom":
            bot_id = _prompt("  企业微信 Bot ID：")
            if bot_id:
                channels_config["wecom"]["bot_id"] = bot_id
            else:
                channels_config["wecom"]["enabled"] = False
        elif cid == "wecom-callback":
            corp_id = _prompt("  企业微信 Corp ID：")
            corp_secret = _prompt("  企业微信 Corp Secret：", password=True)
            if corp_id and corp_secret:
                channels_config["wecom-callback"]["corp_id"] = corp_id
                channels_config["wecom-callback"]["corp_secret"] = corp_secret
            else:
                channels_config["wecom-callback"]["enabled"] = False
        elif cid == "weixin":
            account_id = _prompt("  微信 Account ID：")
            if account_id:
                channels_config["weixin"]["account_id"] = account_id
            else:
                channels_config["weixin"]["enabled"] = False
        elif cid == "bluebubbles":
            url = _prompt("  BlueBubbles Server URL：")
            if url:
                channels_config["bluebubbles"]["server_url"] = url
            else:
                channels_config["bluebubbles"]["enabled"] = False
        elif cid == "qqbot":
            app_id = _prompt("  QQ App ID：")
            if app_id:
                channels_config["qqbot"]["app_id"] = app_id
            else:
                channels_config["qqbot"]["enabled"] = False
        elif cid == "webhook":
            url = _prompt("  Webhook URL (为空则自动使用 /webhook)：")
            if url:
                channels_config["webhook"]["url"] = url
            secret = _prompt("  Webhook Secret (可选)：", password=True)
            if secret:
                channels_config["webhook"]["secret"] = secret

    config.set("channels", channels_config)

    enabled_count = sum(1 for c in channels_config.values() if c.get("enabled"))
    _print_success(f"频道配置完成 ({enabled_count} 个已启用)")


def step3_tools(config):
    _print_header("Step 3 · 工具模块")

    _print_info("选择要预启用的工具模块，可多选：")

    items = []
    for _, label, desc, status in TOOL_MODULES:
        status_icon = {"stable": "🟢", "beta": "🟡", "experimental": "🔵"}.get(status, "⚪")
        status_label = {"stable": "稳定", "beta": "测试", "experimental": "实验"}.get(
            status, status
        )
        items.append(f"{status_icon} {label:<12} [{status_label}] — {desc}")

    pre = list(range(len(TOOL_MODULES)))

    selected = _prompt_checklist("选择模块（直接回车保持默认）：", items, pre)

    enabled_tools = [TOOL_MODULES[i][0] for i in selected]
    config.set("toolsets", enabled_tools)

    if "prometheus-cli" not in enabled_tools:
        config.set("toolsets", list(enabled_tools) + ["prometheus-cli"])

    _print_success(f"工具模块配置完成 ({len(selected)} 个已启用)")


def step4_confirm(config):
    _print_header("Step 4 · 确认配置")

    provider = config.get("model.provider", "未选择")
    model_name = config.get("model.name", "未选择")
    key_set = bool(config.get("api.key", "")) or bool(
        os.getenv("OPENROUTER_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("DEEPSEEK_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    )

    channels_cfg = config.get("channels", {})
    enabled_channels = [k for k, v in channels_cfg.items() if v.get("enabled")]

    tools_list = config.get("toolsets", [])
    tools_count = len(tools_list)

    print()
    print(f"  {C.YELLOW}┌{'─' * 45}┐{S.RESET_ALL}")
    print(f"  {C.YELLOW}│{'':<18}配置汇总{'':>18}│{S.RESET_ALL}")
    print(f"  {C.YELLOW}├{'─' * 45}┤{S.RESET_ALL}")
    print(f"  {C.YELLOW}│{S.RESET_ALL}  📡 提供者：   {provider}")
    print(f"  {C.YELLOW}│{S.RESET_ALL}  🧠 模型：     {model_name}")
    print(f"  {C.YELLOW}│{S.RESET_ALL}  🔑 Key：      {'已配置' if key_set else '⚠ 未配置'}")
    print(
        f"  {C.YELLOW}│{S.RESET_ALL}  💬 频道：     {', '.join(enabled_channels) if enabled_channels else '仅 CLI'}"
    )
    print(f"  {C.YELLOW}│{S.RESET_ALL}  🛠️  工具：     {tools_count} 个模块")
    print(f"  {C.YELLOW}└{'─' * 45}┘{S.RESET_ALL}")
    print()

    if not _prompt_yes_no("确认创建？", True):
        print("  已取消。")
        return False
    return True


def step5_finish(config):
    prometheus_home = get_prometheus_home()
    os.makedirs(prometheus_home, exist_ok=True)
    os.makedirs(prometheus_home / "memories", exist_ok=True)
    os.makedirs(prometheus_home / "skills", exist_ok=True)

    config.save()

    _create_user_md(config)
    _create_soul_md(config)
    _create_memory_md(config)

    _print_done()
    print()
    print("  欢迎！Prometheus 已就绪。")
    print()
    print(f"  📁 配置目录：    {prometheus_home}")
    print("  🤖 个性/身份：  首次进入 'ptg chat' 时设置")
    print(f"  📝 用户画像：    {prometheus_home}/memories/USER.md")
    print(f"  📋 配置文件：    {prometheus_home}/config.yaml")
    print()
    print(f"  {C.CYAN}你可以随时编辑这些文件来自定义体验。{S.RESET_ALL}")
    print()

    return True


def _create_user_md(config):
    content = f"""# 用户画像

## 基本信息
- 名字：探索者
- 首次注册：{_now()}

## 沟通偏好
- 风格：简洁专业
- 工作偏好：效率优先

## 自定义区
<!-- 在此区域添加您的个人偏好 -->
<!-- 首次进入 'ptg chat' 时将引导你完成个性化设置 -->
"""
    path = get_prometheus_home() / "memories" / "USER.md"
    if not path.exists():
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        _print_success("用户画像已创建")


def _create_soul_md(config):
    content = """# AI 个性定义

## 风格
友好、专业、简洁

## 行为准则
1. 保持严谨简洁的沟通风格
2. 不确定时主动询问，不猜测
3. 控制权放用户，AI 不自动修改
4. 遵循三查三定原则：查技能/查知识库/查工具；定边界/定分工/定里程碑

## 编码规范
1. 优先编辑现有文件，不创建新文件
2. 不主动创建文档
3. 遵循现有代码风格

<!-- 首次进入 'ptg chat' 时将引导你完成个性化设置 -->
"""
    path = get_prometheus_home() / "SOUL.md"
    if not path.exists():
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        _print_success("AI 个性已创建")


def _create_memory_md(config):
    content = f"""# 会话记忆

> 此文件由系统自动维护

## 首次初始化
- 时间：{_now()}
- 方式：ptg setup 引导

## 记忆条目
<!-- 会话记忆将在此下方累积 -->
"""
    path = get_prometheus_home() / "memories" / "MEMORY.md"
    if not path.exists():
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        _print_success("记忆系统已初始化")


def _now():
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    run_setup()
