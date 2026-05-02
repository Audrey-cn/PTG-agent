"""Prometheus Banner System."""

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


__version__ = "0.8.0"
__codename__ = "Prometheus"

TIPS = [
    "Type /help to see all available commands",
    "Try /doctor to check system health",
    "Use /skin to switch themes (default/zeus/athena/hades)",
    "Press Ctrl+D to exit the REPL",
    "Use /tools to list all available tools",
    "Try /seed list to see your saved seeds",
    "Use /memory recall to search your memories",
    "Type /status to see system status",
    "Use /config show to view your configuration",
    "Try /skills to list available skill workflows",
]


@dataclass(frozen=True)
class CommandDef:
    name: str
    description: str
    category: str
    aliases: tuple = ()
    args_hint: str = ""


COMMAND_REGISTRY: list[CommandDef] = [
    CommandDef("setup", "引导式初始化", "System"),
    CommandDef("doctor", "系统诊断与修复（守门员模式）", "System"),
    CommandDef("doctor --full", "深度诊断（全部 8 项检查）", "System"),
    CommandDef("doctor --fix", "自动修复网关问题", "System"),
    CommandDef("doctor --emergency", "紧急修复模式", "System"),
    CommandDef("status", "系统状态总览", "Info"),
    CommandDef("config", "配置管理", "Config"),
    CommandDef("config show", "查看完整配置", "Config"),
    CommandDef("model", "模型/提供者配置", "Config"),
    CommandDef("model show", "查看当前模型", "Config"),
    CommandDef("model providers", "列出支持的提供者", "Config"),
    CommandDef("seed list", "列出所有种子", "Seeds"),
    CommandDef("seed search", "搜索种子", "Seeds"),
    CommandDef("seed view", "查看种子 DNA", "Seeds"),
    CommandDef("seed decode", "解码种子", "Seeds"),
    CommandDef("seed health", "种子健康检查", "Seeds"),
    CommandDef("gene list", "列出基因位点", "Genes"),
    CommandDef("memory recall", "语义检索记忆", "Memory"),
    CommandDef("memory stats", "记忆统计", "Memory"),
    CommandDef("kb search", "统一知识检索", "Knowledge"),
    CommandDef("dict", "语义字典管理", "Knowledge"),
    CommandDef("update", "自我更新", "System"),
    CommandDef("skills", "列出 Skill 工作流", "Skills"),
    CommandDef("repl", "交互式 REPL 模式", "System"),
]


PROMPT_TOOLKIT_LOGO = """[bold #FF6B00]██╗  ██╗[/][bold #FF8C00]██╗  ██╗[/][bold #FFAA00]██╗  ██╗[/][bold #FFC800]██╗  ██╗[/][bold #FFE600]██╗  ██╗[/]
[bold #FF6B00]██║[/][bold #FF8C00] ██║[/][bold #FFAA00]██║[/][bold #FFC800] ██║[/][bold #FFE600]██║[/][bold #FF6B00] ██║[/][bold #FF8C00]██║[/][bold #FFAA00] ██║[/][bold #FFC800]██║[/][bold #FFE600] ██║[/][bold #FFAA00] ██║[/][bold #FFC800]██╗[/]
[bold #FFAA00]██║[/][bold #FFC800] ██║[/][bold #FFE600]██║[/][bold #FFAA00] ██║[/][bold #FFC800]██║[/][bold #FFE600] ██║[/][bold #FF8C00]██║[/][bold #FFAA00] ██║[/][bold #FFC800]██║[/][bold #FFE600] ██║[/][bold #FFAA00] ██║[/][bold #FF8C00]██║[/]
[bold #FF8C00]██║[/][bold #FFAA00] ██║[/][bold #FFC800]██║[/][bold #FFE600] ██║[/][bold #FF8C00]██║[/][bold #FFAA00] ██║[/][bold #FFC800]██║[/][bold #FFE600] ██║[/][bold #FF8C00]██║[/][bold #FFAA00] ██║[/][bold #FFC800]██║[/][bold #FF6B00]██║[/]
[bold #FF6B00]╚██╗[/][bold #FF8C00]██╔╝[/][bold #FFAA00]██╔╝[/][bold #FFC800]██╔╝[/][bold #FFE600]██╔╝[/][bold #FFAA00]██╔╝[/][bold #FFC800]██╔╝[/][bold #FFE600]██╔╝[/][bold #FF8C00]██╔╝[/]
[bold #FF6B00] ╚████╔╝[/] [bold #FF8C00]╚████╔╝[/] [bold #FFAA00]╚████╔╝[/] [bold #FFC800]╚████╔╝[/] [bold #FFE600] ╚████╔╝[/]
[bold #FF6B00]  ╚═══╝[/]  [bold #FF8C00] ╚═══╝[/]  [bold #FFAA00] ╚═══╝[/]  [bold #FFC800] ╚═══╝[/]  [bold #FFE600]  ╚═══╝[/]"""


SIMPLE_LOGO = """
        (  )@(   )@   )@   (   @(    )
     (@@@@)  (@@@@@@)  (@@@@@@)  (@@)
   (   @@    (   @@   (@@@   )  (   )
   (@@@@  @@@@)  (@@@@@@)  (@@@@@@@)
   (    @@       (@@@          @@    )
    @@@@   @@@@   (@@@@)    (@@@@
      (@@@@)        (@@@@@@@@)   @@
         (   @@@@)@@)     (@@@   @@
    (@@@@)  @@   )@@)@@)  (@@@@@@@
       (     )    )@)@@@)   (    )
     )@@@)   @@  (@@@@)@@)  @@   )
   (@@@@)    (@@)  )@@)@@@)   @@
     (   )   (   )   )@@)   )
      )       )   (   ) )   )
"""


def get_commands_by_category() -> dict[str, list[str]]:
    """按分类返回命令列表"""
    categories: dict[str, list[str]] = {}
    for cmd in COMMAND_REGISTRY:
        cat = cmd.category
        if cat not in categories:
            categories[cat] = []
        cmd_str = f"/{cmd.name}"
        if cmd.args_hint:
            cmd_str += f" {cmd.args_hint}"
        categories[cat].append(cmd_str)
    return categories


def get_system_info() -> dict[str, str]:
    """获取系统信息"""
    info = {}
    info["Python"] = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    info["Version"] = f"v{__version__}"
    info["CWD"] = os.getcwd()
    home = Path.home() / ".prometheus"
    if home.exists():
        config_path = home / "config.yaml"
        if config_path.exists():
            info["Config"] = "OK"
        else:
            info["Config"] = "Missing"
    return info


def _get_term_width() -> int:
    """获取终端宽度"""
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return 80


def build_welcome_banner(console=None) -> str:
    """构建欢迎 banner 并返回字符串"""
    import random
    
    lines = []
    lines.append("=" * 70)
    lines.append("")

    if HAS_RICH and console:
        term_width = _get_term_width()
        if term_width >= 90:
            lines.append(PROMPT_TOOLKIT_LOGO)
        else:
            lines.append(SIMPLE_LOGO)
    else:
        lines.append(SIMPLE_LOGO)

    lines.append("")
    lines.append("  [bold #FFD700]Prometheus[/] · [dim]Teach-To-Grow[/]")
    lines.append(f"  [dim]Version:[/] [bold]{__version__}[/] · [dim]Epic Chronicler[/]")
    lines.append("  [dim]Founder:[/] Audrey · 001X")
    
    # 获取工具数量
    try:
        from prometheus.tools.registry import registry
        tool_count = len(registry.get_all_tool_names())
        lines.append(f"  [dim]Tools:[/] [bold]{tool_count}[/] loaded")
    except Exception:
        pass
    
    # 获取当前模型和 provider
    try:
        from prometheus.config import PrometheusConfig
        config = PrometheusConfig.load()
        model_name = config.get("model.name", "gpt-4")
        provider = config.get("model.provider", "openai")
        lines.append(f"  [dim]Model:[/] [bold]{model_name}[/] ([dim]{provider}[/])")
    except Exception:
        pass
    
    lines.append("")

    categories = get_commands_by_category()

    lines.append("  [bold #FF8C00]Available Commands[/]")
    lines.append("")

    for cat_name, commands in sorted(categories.items()):
        lines.append(f"  [dim #CD7F32]{cat_name}:[/]")
        for cmd in commands[:6]:
            lines.append(f"    {cmd}")
        if len(commands) > 6:
            lines.append(f"    ... (+{len(commands) - 6} more)")
        lines.append("")

    # 随机 Tip
    tip = random.choice(TIPS)
    lines.append(f"  [dim]Tip:[/] {tip}")
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def print_banner(console=None):
    """打印 banner 到控制台"""
    if HAS_RICH and console:
        console.print(build_welcome_banner(console))
    else:
        print(build_welcome_banner())


def print_simple_banner():
    """打印简单 banner（无 Rich 库）"""
    banner = f"""
{"=" * 70}

{SIMPLE_LOGO}

  Prometheus · Teach-To-Grow
  Version: {__version__} · Epic Chronicler
  Founder: Audrey · 001X

  Available Commands:

    System:
      /setup          引导式初始化
      /doctor         系统诊断与修复
      /status         系统状态总览
      /update         自我更新
      /repl           交互式 REPL

    Config:
      /config show    查看完整配置
      /model show     查看当前模型
      /model providers 列出提供者

    Seeds:
      /seed list      列出所有种子
      /seed search    搜索种子
      /seed view      查看种子 DNA

    Genes:
      /gene list      列出基因位点

    Memory:
      /memory recall  语义检索记忆
      /memory stats   记忆统计

    Knowledge:
      /kb search      统一知识检索
      /dict           语义字典

    Skills:
      /skills         列出 Skill 工作流

  Tip: Run /help for interactive commands
  Tip: Run ptg doctor to check system health

{"=" * 70}
"""
    print(banner)
