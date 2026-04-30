"""
交互式初始化向导。

对标 openclaw onboard: 5步引导式初始化流程。
"""

import os
import sys
from datetime import datetime, timezone
from typing import Optional
from .workspace import ensure_workspace, complete_bootstrap, resolve_workspace_dir


_AVAILABLE_PROVIDERS = [
    {"name": "openrouter", "display": "OpenRouter (推荐，多模型切换)", "env_key": "OPENROUTER_API_KEY"},
    {"name": "anthropic", "display": "Anthropic Claude", "env_key": "ANTHROPIC_API_KEY"},
    {"name": "deepseek", "display": "DeepSeek", "env_key": "DEEPSEEK_API_KEY"},
    {"name": "openai", "display": "OpenAI", "env_key": "OPENAI_API_KEY"},
    {"name": "google", "display": "Google Gemini", "env_key": "GOOGLE_API_KEY"},
    {"name": "local", "display": "本地模型 (无需API Key)", "env_key": None},
]

_AVAILABLE_TOOLS = [
    {"id": "memory", "name": "记忆系统", "desc": "MD+SQLite混合存储，三层记忆模型", "required": True},
    {"id": "knowledge", "name": "知识编译器", "desc": "蒸馏→汇聚→合成知识管线", "required": False},
    {"id": "seed_editor", "name": "种子编辑", "desc": "知识种子创建/编辑/演化", "required": False},
    {"id": "accelerator", "name": "网络加速", "desc": "多节点负载均衡+fallback(国内环境推荐)", "required": False},
    {"id": "self_correction", "name": "自修正", "desc": "输出反思与二次校正", "required": False},
    {"id": "semantic_dict", "name": "语义字典", "desc": "术语定义/同义词映射", "required": False},
    {"id": "backup", "name": "备份恢复", "desc": "自动BAK+手动归档", "required": False},
]


def _print_banner():
    """打印初始化向导横幅。"""
    banner = r"""
╔══════════════════════════════════════════════╗
║                                              ║
║   🔥 普罗米修斯 · 初始化向导                  ║
║   Prometheus Initiation Wizard              ║
║                                              ║
║   创建者: Audrey · 001X                      ║
║   版本:   1.0                                ║
║                                              ║
╚══════════════════════════════════════════════╝
"""
    print(banner)


def _step_model_provider() -> dict:
    """第一步: 模型提供者选择。"""
    print("\n📡 第一步: 模型提供者配置")
    print("-" * 50)

    print("\n可用提供者 (已自动检测环境变量中的API Key):\n")
    for i, provider in enumerate(_AVAILABLE_PROVIDERS):
        marker = ""
        if provider["env_key"]:
            if os.environ.get(provider["env_key"]):
                marker = " ✅ 已检测到密钥"
            else:
                marker = " ⚪ 未设置密钥"
        else:
            marker = " ⚪ 无需密钥"
        print(f"  [{i + 1}] {provider['display']}{marker}")

    print("\n  [0] 跳过，稍后配置")

    while True:
        try:
            choice = input("\n请选择模型提供者 [1-6, 默认: 1]: ").strip()
            if not choice:
                choice = "1"
            idx = int(choice)
            if idx == 0:
                return {"provider": None, "model": None}
            if 1 <= idx <= len(_AVAILABLE_PROVIDERS):
                break
            print("请输入有效选项 (1-6)")
        except (ValueError, KeyboardInterrupt):
            if isinstance(sys.exc_info()[1], KeyboardInterrupt):
                print("\n\n初始化已取消。")
                sys.exit(0)
            print("请输入有效数字")

    provider = _AVAILABLE_PROVIDERS[idx - 1]
    provider_name = provider["name"]

    if provider["env_key"]:
        env_value = os.environ.get(provider["env_key"], "")
        if env_value:
            masked = env_value[:8] + "..." if len(env_value) > 8 else "***"
            print(f"\n  已使用环境变量 {provider['env_key']}: {masked}")
        else:
            print(f"\n  未检测到 {provider['env_key']} 环境变量。")
            print("  你可以稍后在 config.yaml 或环境变量中配置。")

    print(f"\n  已选择: {provider['display']}")

    return {"provider": provider_name, "model": "auto"}


def _step_workspace() -> dict:
    """第二步: 工作空间设置。"""
    print("\n📂 第二步: 工作空间配置")
    print("-" * 50)

    default_dir = resolve_workspace_dir()
    print(f"\n默认工作空间路径: {default_dir}")

    custom = input("\n使用自定义路径? (直接回车使用默认): ").strip()
    workspace_dir = custom if custom else default_dir

    print(f"\n正在创建/检查工作空间: {workspace_dir}")
    result = ensure_workspace(workspace_dir)

    print(f"\n  工作空间: {result['dir']}")
    if result["created_files"]:
        print(f"  已播种引导文件 ({len(result['created_files'])}个):")
        for fname in result["created_files"]:
            print(f"    ✅ {fname}")
    else:
        print("  引导文件已存在，跳过播种。")

    return {"workspace_dir": workspace_dir, "bootstrap_pending": result["bootstrap_pending"]}


def _step_tools() -> dict:
    """第三步: 工具配置。"""
    print("\n🛠️  第三步: 工具模块配置")
    print("-" * 50)

    print("\n可用工具模块:\n")
    for i, tool in enumerate(_AVAILABLE_TOOLS):
        req_mark = " [必须]" if tool["required"] else ""
        print(f"  [{i + 1}] {tool['name']}{req_mark}")
        print(f"      {tool['desc']}")

    print("\n输入要启用的工具编号 (用空格分隔，如: 1 2 3 4 5)")
    print("必须模块(1)始终启用。直接回车启用全部。")

    choice = input("\n选择工具 [默认: 全部]: ").strip()
    if not choice:
        enabled = {t["id"] for t in _AVAILABLE_TOOLS}
    else:
        try:
            indices = [int(x) for x in choice.split()]
            enabled = set()
            for idx in indices:
                if 1 <= idx <= len(_AVAILABLE_TOOLS):
                    enabled.add(_AVAILABLE_TOOLS[idx - 1]["id"])
            for tool in _AVAILABLE_TOOLS:
                if tool["required"]:
                    enabled.add(tool["id"])
        except ValueError:
            print("输入无效，启用全部模块。")
            enabled = {t["id"] for t in _AVAILABLE_TOOLS}

    print("\n  已启用的工具模块:")
    for tool in _AVAILABLE_TOOLS:
        status = "✅" if tool["id"] in enabled else "⛔"
        print(f"  {status} {tool['name']}")

    return {"enabled_tools": sorted(enabled)}


def _step_channels() -> dict:
    """第四步: 频道配置(可选)。"""
    print("\n💬 第四步: 消息频道配置 (可选)")
    print("-" * 50)

    print("\n当前支持的频道:")
    print("  [1] CLI — 命令行界面 (始终启用)")
    print("  [2] HTTP Webhook — 接收HTTP回调")
    print("  [3] 文件监听 — 监听目录变化")

    print("\nCLI频道始终启用。")
    print("(更多频道如 Telegram/Discord 将在后续版本中支持)")

    enabled_channels = ["cli"]

    choice = input("\n额外启用频道? (用空格分隔编号，直接回车跳过): ").strip()
    if choice:
        try:
            indices = [int(x) for x in choice.split()]
            channel_map = {2: "http_webhook", 3: "file_watch"}
            for idx in indices:
                if idx in channel_map:
                    enabled_channels.append(channel_map[idx])
        except ValueError:
            pass

    print(f"\n  已启用的频道: {', '.join(enabled_channels)}")

    return {"enabled_channels": enabled_channels}


def _step_verify(result: dict) -> dict:
    """第五步: 初始化验证。"""
    print("\n✅ 第五步: 初始化验证")
    print("-" * 50)

    checks = []

    workspace_dir = result.get("workspace_dir", resolve_workspace_dir())
    checks.append({
        "name": "工作空间",
        "path": workspace_dir,
        "status": "pass" if os.path.isdir(workspace_dir) else "fail",
    })

    agents_md = os.path.join(workspace_dir, "AGENTS.md")
    checks.append({
        "name": "AGENTS.md",
        "path": agents_md,
        "status": "pass" if os.path.exists(agents_md) else "fail",
    })

    soul_md = os.path.join(workspace_dir, "SOUL.md")
    checks.append({
        "name": "SOUL.md",
        "path": soul_md,
        "status": "pass" if os.path.exists(soul_md) else "fail",
    })

    identity_md = os.path.join(workspace_dir, "IDENTITY.md")
    checks.append({
        "name": "IDENTITY.md",
        "path": identity_md,
        "status": "pass" if os.path.exists(identity_md) else "fail",
    })

    user_md = os.path.join(workspace_dir, "USER.md")
    checks.append({
        "name": "USER.md",
        "path": user_md,
        "status": "pass" if os.path.exists(user_md) else "fail",
    })

    print("\n  检查结果:")
    all_pass = True
    for check in checks:
        icon = "✅" if check["status"] == "pass" else "❌"
        print(f"  {icon} {check['name']} — {check['path']}")
        if check["status"] == "fail":
            all_pass = False

    if not all_pass:
        print("\n  ⚠️ 部分检查未通过，可稍后运行 `ptg doctor` 进行诊断。")
    else:
        print("\n  🎉 所有检查通过！普罗米修斯已就绪。")

    return {"checks": checks, "all_pass": all_pass}


def run_onboard(workspace_dir: Optional[str] = None, non_interactive: bool = False) -> dict:
    """
    运行交互式初始化向导。

    对标 openclaw onboard: 5步引导流程。

    参数:
        workspace_dir: 自定义工作空间路径
        non_interactive: 非交互模式 (跳过用户输入，使用默认值)

    返回: dict 包含完整的初始化结果
    """
    if non_interactive:
        return _run_non_interactive(workspace_dir)

    _print_banner()

    print("\n欢迎使用普罗米修斯初始化向导！")
    print("本向导将通过 5 个步骤帮助你完成 Agent 的初始配置。")
    print("按 Ctrl+C 可随时退出。")

    input("\n按回车键开始...")

    try:
        model_cfg = _step_model_provider()
    except KeyboardInterrupt:
        print("\n\n初始化已取消。")
        sys.exit(0)

    try:
        workspace_cfg = _step_workspace()
    except KeyboardInterrupt:
        print("\n\n初始化已取消。")
        sys.exit(0)

    try:
        tools_cfg = _step_tools()
    except KeyboardInterrupt:
        print("\n\n初始化已取消。")
        sys.exit(0)

    try:
        channels_cfg = _step_channels()
    except KeyboardInterrupt:
        print("\n\n初始化已取消。")
        sys.exit(0)

    result = {
        **model_cfg,
        **workspace_cfg,
        **tools_cfg,
        **channels_cfg,
    }

    try:
        verify = _step_verify(result)
    except KeyboardInterrupt:
        print("\n\n初始化已取消。")
        sys.exit(0)

    result.update(verify)

    print("\n" + "=" * 50)
    print("  🔥 普罗米修斯初始化完成！")
    print("=" * 50)
    print(f"\n  工作空间: {result['workspace_dir']}")
    print(f"  模型提供者: {result['provider'] or '未配置'}")
    print(f"  启用工具: {', '.join(result['enabled_tools'])}")
    print(f"  启用频道: {', '.join(result['enabled_channels'])}")
    print(f"\n  💡 提示: 首次运行时会触发 BOOTSTRAP.md 引导流程。")
    print(f"  💡 运行 'ptg sync' 进行记忆同步。")
    print(f"  💡 运行 'ptg doctor' 进行系统诊断。")

    result["onboarded_at"] = datetime.now(timezone.utc).isoformat()

    return result


def _run_non_interactive(workspace_dir: Optional[str] = None) -> dict:
    """非交互模式：使用默认配置快速初始化。"""
    ws_dir = resolve_workspace_dir(workspace_dir)
    ws_result = ensure_workspace(ws_dir)

    result = {
        "provider": "openrouter",
        "model": "auto",
        "workspace_dir": ws_dir,
        "bootstrap_pending": ws_result["bootstrap_pending"],
        "enabled_tools": [t["id"] for t in _AVAILABLE_TOOLS],
        "enabled_channels": ["cli"],
        "checks": [],
        "all_pass": True,
        "onboarded_at": datetime.now(timezone.utc).isoformat(),
        "non_interactive": True,
    }

    print(f"非交互模式初始化完成。工作空间: {ws_dir}")
    return result
