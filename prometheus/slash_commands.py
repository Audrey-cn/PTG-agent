from __future__ import annotations

import copy
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True)
class CommandDef:
    name: str
    description: str
    category: str = "General"
    aliases: Tuple[str, ...] = ()
    args_hint: str = ""
    subcommands: Tuple[str, ...] = ()
    cli_only: bool = False
    gateway_only: bool = False


COMMAND_REGISTRY: list[CommandDef] = [
    CommandDef("new", "开始新会话（清除历史）", "Session", aliases=("reset",)),
    CommandDef("clear", "清屏并开始新会话", "Session", cli_only=True),
    CommandDef("history", "显示对话历史", "Session", cli_only=True),
    CommandDef("save", "保存当前对话到文件", "Session", cli_only=True, args_hint="[path]"),
    CommandDef("retry", "重试上一条消息", "Session"),
    CommandDef("undo", "撤销上一轮对话", "Session"),
    CommandDef("title", "设置当前会话标题", "Session", args_hint="[name]"),
    CommandDef("compress", "手动压缩对话上下文", "Session", args_hint="[focus topic]"),
    CommandDef("stop", "停止当前运行的 Agent", "Session"),
    CommandDef("background", "在后台运行提示词", "Session", aliases=("bg",), args_hint="<prompt>"),
    CommandDef("queue", "排队下一条提示", "Session", aliases=("q",), args_hint="<prompt>"),
    CommandDef("status", "显示会话信息", "Session"),
    CommandDef("config", "显示当前配置", "Configuration", cli_only=True),
    CommandDef(
        "model", "切换或查看当前模型", "Configuration", aliases=("provider",), args_hint="[model]"
    ),
    CommandDef("personality", "设置预定义个性", "Configuration", args_hint="[name]"),
    CommandDef("yolo", "切换 YOLO 模式（跳过危险命令审批）", "Configuration"),
    CommandDef(
        "reasoning",
        "管理推理力度",
        "Configuration",
        args_hint="[level|show|hide]",
        subcommands=("none", "low", "medium", "high", "show", "hide"),
    ),
    CommandDef("skin", "显示或切换皮肤/主题", "Configuration", cli_only=True, args_hint="[name]"),
    CommandDef("verbose", "切换工具进度显示", "Configuration", cli_only=True),
    CommandDef(
        "tools",
        "管理工具：/tools [list|disable|enable]",
        "Tools & Skills",
        args_hint="[list|disable|enable] [name...]",
    ),
    CommandDef("toolsets", "列出可用工具集", "Tools & Skills", cli_only=True),
    CommandDef(
        "skills",
        "搜索、安装、检查或管理技能",
        "Tools & Skills",
        cli_only=True,
        subcommands=("search", "browse", "inspect", "install"),
    ),
    CommandDef(
        "cron",
        "管理定时任务",
        "Tools & Skills",
        cli_only=True,
        subcommands=("list", "add", "remove", "run"),
    ),
    CommandDef("reload", "重载 .env 变量到运行会话", "Tools & Skills", cli_only=True),
    CommandDef("reload-mcp", "重载 MCP 服务器配置", "Tools & Skills", aliases=("reload_mcp",)),
    CommandDef(
        "browser",
        "连接浏览器工具到 Chrome (CDP)",
        "Tools & Skills",
        cli_only=True,
        subcommands=("connect", "disconnect", "status"),
    ),
    CommandDef("help", "显示可用命令", "Info"),
    CommandDef("usage", "显示当前会话的 Token 使用量", "Info"),
    CommandDef("insights", "显示使用洞察和分析", "Info", args_hint="[days]"),
    CommandDef("platforms", "显示网关/消息平台状态", "Info", cli_only=True, aliases=("gateway",)),
    CommandDef("copy", "复制上一条助手回复到剪贴板", "Info", cli_only=True),
    CommandDef("image", "附加本地图片文件到下一条提示", "Info", cli_only=True, args_hint="<path>"),
    CommandDef("update", "更新 Prometheus Agent 到最新版本", "Info"),
    CommandDef("debug", "上传调试报告并获取分享链接", "Info"),
    CommandDef("stamp", "在种子上烙印", "Chronicler", args_hint="<path> [mark]"),
    CommandDef("trace", "追溯种子历史", "Chronicler", args_hint="<path>"),
    CommandDef("append", "附加历史记录到种子", "Chronicler", args_hint="<path> <note>"),
    CommandDef("inspect", "检查种子", "Chronicler", args_hint="<path>"),
    CommandDef("stamps", "列出种子上的烙印", "Chronicler", args_hint="<path>"),
    CommandDef("quit", "退出 CLI", "Exit", cli_only=True, aliases=("exit",)),
]


def _build_command_lookup() -> Dict[str, CommandDef]:
    lookup: Dict[str, CommandDef] = {}
    for cmd in COMMAND_REGISTRY:
        lookup[cmd.name] = cmd
        for alias in cmd.aliases:
            lookup[alias] = cmd
    return lookup


_COMMAND_LOOKUP: Dict[str, CommandDef] = _build_command_lookup()


def resolve_command(name: str) -> CommandDef | None:
    return _COMMAND_LOOKUP.get(name.lower().lstrip("/"))


COMMANDS: Dict[str, str] = {}
for _cmd in COMMAND_REGISTRY:
    if not _cmd.gateway_only:
        COMMANDS[f"/{_cmd.name}"] = _cmd.description
        for _alias in _cmd.aliases:
            COMMANDS[f"/{_alias}"] = f"{_cmd.description} (alias for /{_cmd.name})"

COMMANDS_BY_CATEGORY: Dict[str, Dict[str, str]] = {}
for _cmd in COMMAND_REGISTRY:
    if not _cmd.gateway_only:
        _cat = COMMANDS_BY_CATEGORY.setdefault(_cmd.category, {})
        _cat[f"/{_cmd.name}"] = COMMANDS[f"/{_cmd.name}"]
        for _alias in _cmd.aliases:
            _cat[f"/{_alias}"] = COMMANDS[f"/{_alias}"]

SUBCOMMANDS: Dict[str, List[str]] = {}
for _cmd in COMMAND_REGISTRY:
    if _cmd.subcommands:
        SUBCOMMANDS[f"/{_cmd.name}"] = list(_cmd.subcommands)


class ChatSession:
    def __init__(self, agent, config_dict: dict):
        self.agent = agent
        self.config_dict = config_dict
        self.history: list[dict] = []
        self.title: str = ""
        self.yolo_mode: bool = False
        self.verbose: str = "new"
        self.total_tokens_in: int = 0
        self.total_tokens_out: int = 0
        self.tool_calls_count: int = 0
        self.turn_count: int = 0
        self._last_user_message: str = ""
        self._last_assistant_message: str = ""
        self._pending_image: str | None = None
        self._stopped: bool = False
        self._queued_prompt: str | None = None

    def add_exchange(self, user_msg: str, assistant_msg: str, cost: Dict | None = None):
        self.history.append({"role": "user", "content": user_msg})
        self.history.append({"role": "assistant", "content": assistant_msg})
        self._last_user_message = user_msg
        self._last_assistant_message = assistant_msg
        self.turn_count += 1
        if cost:
            self.total_tokens_in += cost.get("in_tokens", 0)
            self.total_tokens_out += cost.get("out_tokens", 0)

    def undo_last(self) -> bool:
        if len(self.history) < 2:
            return False
        self.history.pop()
        self.history.pop()
        self.turn_count = max(0, self.turn_count - 1)
        return True

    def clear(self):
        self.history = []
        self.turn_count = 0
        self.title = ""

    def get_history_copy(self) -> list[dict]:
        return copy.deepcopy(self.history)

    def estimate_tokens(self) -> int:
        total_chars = sum(len(m.get("content", "")) for m in self.history)
        return total_chars // 4


class SlashCommandDispatcher:
    def __init__(self, session: ChatSession):
        self.session = session
        self._handlers: Dict[str, Callable] = {
            "new": self._cmd_new,
            "reset": self._cmd_new,
            "clear": self._cmd_clear,
            "history": self._cmd_history,
            "save": self._cmd_save,
            "retry": self._cmd_retry,
            "undo": self._cmd_undo,
            "title": self._cmd_title,
            "compress": self._cmd_compress,
            "stop": self._cmd_stop,
            "status": self._cmd_status,
            "config": self._cmd_config,
            "model": self._cmd_model,
            "provider": self._cmd_model,
            "personality": self._cmd_personality,
            "yolo": self._cmd_yolo,
            "reasoning": self._cmd_reasoning,
            "skin": self._cmd_skin,
            "verbose": self._cmd_verbose,
            "tools": self._cmd_tools,
            "toolsets": self._cmd_toolsets,
            "skills": self._cmd_skills,
            "cron": self._cmd_cron,
            "reload": self._cmd_reload,
            "reload-mcp": self._cmd_reload_mcp,
            "reload_mcp": self._cmd_reload_mcp,
            "browser": self._cmd_browser,
            "help": self._cmd_help,
            "usage": self._cmd_usage,
            "insights": self._cmd_insights,
            "platforms": self._cmd_platforms,
            "gateway": self._cmd_platforms,
            "copy": self._cmd_copy,
            "image": self._cmd_image,
            "update": self._cmd_update,
            "debug": self._cmd_debug,
            "stamp": self._cmd_stamp,
            "trace": self._cmd_trace,
            "append": self._cmd_append,
            "inspect": self._cmd_inspect,
            "stamps": self._cmd_stamps,
            "quit": self._cmd_quit,
            "exit": self._cmd_quit,
        }

    def dispatch(self, raw_input: str) -> Tuple[bool, str | None]:
        stripped = raw_input.strip()
        if not stripped.startswith("/"):
            return False, None

        parts = stripped.split(maxsplit=1)
        cmd_name = parts[0].lower().lstrip("/")
        cmd_args = parts[1] if len(parts) > 1 else ""

        handler = self._handlers.get(cmd_name)
        if handler is None:
            resolved = resolve_command(cmd_name)
            if resolved:
                handler = self._handlers.get(resolved.name)
            if handler is None:
                print(f"  未知命令: /{cmd_name}  输入 /help 查看可用命令")
                return True, None

        result = handler(cmd_args)
        should_exit = result == "EXIT"
        return True, "EXIT" if should_exit else None

    def _cmd_new(self, args: str) -> None:
        self.session.clear()
        print("  ✨ 新会话已开始")

    def _cmd_clear(self, args: str) -> None:
        self.session.clear()
        os.system("cls" if os.name == "nt" else "clear")
        print("  ✨ 屏幕已清除，新会话已开始")

    def _cmd_history(self, args: str) -> None:
        if not self.session.history:
            print("  (无对话历史)")
            return
        for _i, msg in enumerate(self.session.history):
            role = msg.get("role", "?")
            content = msg.get("content", "")
            if role == "user":
                prefix = "  👤"
            elif role == "assistant":
                prefix = "  🤖"
            else:
                prefix = f"  [{role}]"
            display = content[:120] + ("..." if len(content) > 120 else "")
            print(f"{prefix} {display}")
        print(
            f"\n  共 {self.session.turn_count} 轮对话，约 {self.session.estimate_tokens()} tokens"
        )

    def _cmd_save(self, args: str) -> None:
        if not self.session.history:
            print("  (无对话可保存)")
            return
        from prometheus.config import get_prometheus_home

        save_dir = get_prometheus_home() / "saves"
        save_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        title_part = f"_{self.session.title[:20]}" if self.session.title else ""
        filename = args.strip() or f"chat_{ts}{title_part}.json"
        if not filename.endswith(".json"):
            filename += ".json"
        filepath = save_dir / filename
        data = {
            "title": self.session.title,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "turns": self.session.turn_count,
            "tokens_in": self.session.total_tokens_in,
            "tokens_out": self.session.total_tokens_out,
            "history": self.session.history,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  💾 对话已保存到 {filepath}")

    def _cmd_retry(self, args: str) -> None:
        if not self.session._last_user_message:
            print("  (没有可重试的消息)")
            return
        self.session.undo_last()
        print(f"  🔄 重试: {self.session._last_user_message[:80]}...")
        try:
            result = self.session.agent.run_conversation(
                self.session._last_user_message, history=self.session.history
            )
            text = result.get("text", "")
            print(f"\n{text}\n")
            self.session.add_exchange(self.session._last_user_message, text, result.get("cost"))
            self.session.tool_calls_count += result.get("tool_calls_made", 0)
        except Exception as e:
            print(f"\n  ❌ 重试失败: {e}")

    def _cmd_undo(self, args: str) -> None:
        if self.session.undo_last():
            print("  ↩️  已撤销上一轮对话")
        else:
            print("  (没有可撤销的对话)")

    def _cmd_title(self, args: str) -> None:
        if args.strip():
            self.session.title = args.strip()
            print(f"  📝 会话标题设置为: {self.session.title}")
        else:
            current = self.session.title or "(未设置)"
            print(f"  当前标题: {current}")

    def _cmd_compress(self, args: str) -> None:
        if not self.session.history:
            print("  (无上下文需要压缩)")
            return
        focus = args.strip() if args.strip() else None
        try:
            from prometheus.context_compressor import compress_history

            compressed = compress_history(self.session.history, focus=focus)
            old_count = len(self.session.history)
            self.session.history = compressed
            new_count = len(self.session.history)
            print(f"  🗜️  上下文已压缩: {old_count} → {new_count} 条消息")
        except ImportError:
            total = self.session.estimate_tokens()
            if total > 20000:
                half = len(self.session.history) // 2
                removed = len(self.session.history) - half
                self.session.history = (
                    self.session.history[-half:] if half > 0 else self.session.history
                )
                print(
                    f"  🗜️  简易压缩: 移除前 {removed} 条消息，保留最近 {len(self.session.history)} 条"
                )
            else:
                print(f"  当前上下文约 {total} tokens，无需压缩")

    def _cmd_stop(self, args: str) -> None:
        self.session._stopped = True
        print("  🛑 停止信号已发送")

    def _cmd_status(self, args: str) -> None:
        est = self.session.estimate_tokens()
        print("  📊 会话状态:")
        print(f"     轮次: {self.session.turn_count}")
        print(f"     消息: {len(self.session.history)} 条")
        print(f"     估算 Token: ~{est}")
        print(
            f"     实际 Token: {self.session.total_tokens_in}in / {self.session.total_tokens_out}out"
        )
        print(f"     工具调用: {self.session.tool_calls_count}")
        print(f"     YOLO: {'开' if self.session.yolo_mode else '关'}")
        print(f"     标题: {self.session.title or '(未设置)'}")

    def _cmd_config(self, args: str) -> None:
        from prometheus.config import Config as PrometheusConfig

        cfg = PrometheusConfig.load()
        d = cfg.to_dict()
        print("  ⚙️  当前配置:")
        for section, values in d.items():
            if isinstance(values, dict):
                print(f"\n  [{section}]")
                for k, v in values.items():
                    if k == "key" and v:
                        v = v[:8] + "..." if len(str(v)) > 8 else v
                    print(f"    {k} = {v}")

    def _cmd_model(self, args: str) -> None:
        if not args.strip():
            model = self.session.agent.model
            print(f"  🧠 当前模型: {model}")
            return
        new_model = args.strip()
        self.session.agent.model = new_model
        print(f"  🧠 模型已切换为: {new_model}")

    def _cmd_personality(self, args: str) -> None:
        if not args.strip():
            print("  用法: /personality <name>  或  /personality none")
            return
        name = args.strip()
        if name.lower() == "none":
            self.session.agent.system_prompt = (
                "You are Prometheus, the epic chronicler agent. "
                "You manage genetic seeds, maintain the chronicle, and assist with creative and technical tasks. "
                "Use tools when appropriate. Be concise and precise."
            )
            print("  个性已重置为默认")
            return
        try:
            from prometheus.config import Config as PrometheusConfig

            cfg = PrometheusConfig.load()
            d = cfg.to_dict()
            personalities = d.get("agent", {}).get("personalities", {})
            if name in personalities:
                p = personalities[name]
                prompt = p.get("system_prompt", str(p)) if isinstance(p, dict) else str(p)
                self.session.agent.system_prompt = prompt
                print(f"  🎭 个性已切换为: {name}")
            else:
                print(
                    f"  未知个性: {name}。可用: {', '.join(personalities.keys()) if personalities else '(无)'}"
                )
        except Exception as e:
            print(f"  错误: {e}")

    def _cmd_yolo(self, args: str) -> None:
        self.session.yolo_mode = not self.session.yolo_mode
        state = "开 🔥" if self.session.yolo_mode else "关"
        print(f"  YOLO 模式: {state}")

    def _cmd_reasoning(self, args: str) -> None:
        sub = args.strip().lower()
        valid = ("none", "low", "medium", "high", "show", "hide")
        if not sub:
            print(f"  用法: /reasoning [{'|'.join(valid)}]")
            return
        if sub in ("show", "hide"):
            print(f"  推理显示: {sub}")
            return
        if sub in valid:
            print(f"  🧠 推理力度: {sub}")
        else:
            print(f"  未知级别: {sub}")

    def _cmd_skin(self, args: str) -> None:
        if not args.strip():
            try:
                from prometheus.skin_engine import get_active_skin_name, list_skins

                skins = list_skins()
                active = get_active_skin_name()
                print("  可用皮肤:")
                for s in skins:
                    marker = " (*)" if s["name"] == active else ""
                    print(f"    {s['name']:10} - {s['description']}{marker}")
            except Exception:
                print("  皮肤引擎不可用")
            return
        try:
            from prometheus.skin_engine import list_skins, set_active_skin

            available = {s["name"] for s in list_skins()}
            name = args.strip()
            if name not in available:
                print(f"  未知皮肤: {name}。可用: {', '.join(available)}")
                return
            set_active_skin(name)
            print(f"  ✨ 皮肤已切换为: {name}")
        except Exception as e:
            print(f"  错误: {e}")

    def _cmd_verbose(self, args: str) -> None:
        cycle = {"off": "new", "new": "all", "all": "verbose", "verbose": "off"}
        self.session.verbose = cycle.get(self.session.verbose, "new")
        print(f"  工具进度显示: {self.session.verbose}")

    def _cmd_tools(self, args: str) -> None:
        from prometheus.tools.registry import registry

        parts = args.strip().split()
        if not parts or parts[0] == "list":
            tool_names = registry.get_all_tool_names()
            print(f"\n  可用工具 ({len(tool_names)}):")
            tools_by_set: Dict[str, List[str]] = {}
            for name in tool_names:
                toolset = registry.get_toolset_for_tool(name) or "default"
                tools_by_set.setdefault(toolset, []).append(name)
            for toolset, names in sorted(tools_by_set.items()):
                emoji = registry.get_emoji(names[0], "") if names else ""
                print(f"\n  {emoji} {toolset}:")
                for name in sorted(names):
                    desc = registry.get_schema(name)
                    desc_text = desc.get("description", "")[:50] if desc else ""
                    print(f"    - {name}: {desc_text}")
            print()
        elif parts[0] == "disable" and len(parts) >= 2:
            print(f"  工具 {parts[1]} 已禁用（此功能待实现）")
        elif parts[0] == "enable" and len(parts) >= 2:
            print(f"  工具 {parts[1]} 已启用（此功能待实现）")
        else:
            print("  用法: /tools [list|disable|enable] [name...]")

    def _cmd_toolsets(self, args: str) -> None:
        from prometheus.tools.registry import registry

        tool_names = registry.get_all_tool_names()
        toolsets: Set[str] = set()
        for name in tool_names:
            toolsets.add(registry.get_toolset_for_tool(name) or "default")
        print(f"\n  可用工具集 ({len(toolsets)}):")
        for ts in sorted(toolsets):
            count = sum(
                1 for n in tool_names if (registry.get_toolset_for_tool(n) or "default") == ts
            )
            print(f"    - {ts} ({count} 工具)")
        print()

    def _cmd_skills(self, args: str) -> None:
        parts = args.strip().split()
        sub = parts[0] if parts else "browse"
        if sub == "browse":
            try:
                from prometheus.tools.skill_loader import list_available_skills

                skills = list_available_skills()
                if not skills:
                    print("  (无可用技能)")
                    return
                print(f"\n  可用技能 ({len(skills)}):")
                for s in skills:
                    name = s.get("name", "?")
                    desc = s.get("description", "")[:60]
                    print(f"    - {name}: {desc}")
                print()
            except Exception as e:
                print(f"  错误: {e}")
        else:
            print("  用法: /skills [browse|search|inspect|install]")

    def _cmd_cron(self, args: str) -> None:
        parts = args.strip().split()
        sub = parts[0] if parts else "list"
        if sub == "list":
            try:
                from prometheus.tools.cron import list_jobs

                jobs = list_jobs()
                if not jobs:
                    print("  (无定时任务)")
                    return
                for j in jobs:
                    print(f"    {j}")
            except Exception:
                print("  定时任务系统不可用")
        else:
            print("  用法: /cron [list|add|remove|run]")

    def _cmd_reload(self, args: str) -> None:
        from pathlib import Path

        env_file = Path(".") / ".env"
        if env_file.exists():
            from prometheus.config import Config as PrometheusConfig

            PrometheusConfig.load()
            print("  ✅ 配置已重新加载")
        else:
            print("  未找到 .env 文件")

    def _cmd_reload_mcp(self, args: str) -> None:
        print("  MCP 服务器配置已重新加载（此功能待完善）")

    def _cmd_browser(self, args: str) -> None:
        sub = args.strip().lower() or "status"
        if sub == "status":
            print("  浏览器: 未连接")
        elif sub == "connect":
            print("  浏览器: 正在连接...（此功能待实现）")
        elif sub == "disconnect":
            print("  浏览器: 已断开")

    def _cmd_help(self, args: str) -> None:
        print("\n  🔥 Prometheus 斜杠命令\n")
        for category, cmds in COMMANDS_BY_CATEGORY.items():
            print(f"  ── {category} ──")
            for cmd, desc in cmds.items():
                print(f"    {cmd:20} {desc}")
            print()
        print("  提示: 直接输入消息与 AI 对话，无需 / 前缀\n")

    def _cmd_usage(self, args: str) -> None:
        print("  📊 Token 使用量:")
        print(f"     输入: {self.session.total_tokens_in:,}")
        print(f"     输出: {self.session.total_tokens_out:,}")
        print(f"     总计: {self.session.total_tokens_in + self.session.total_tokens_out:,}")
        print(f"     工具调用: {self.session.tool_calls_count}")
        print(f"     对话轮次: {self.session.turn_count}")

    def _cmd_insights(self, args: str) -> None:
        print("  📈 使用洞察:")
        print(f"     总轮次: {self.session.turn_count}")
        print(f"     总 Token: {self.session.total_tokens_in + self.session.total_tokens_out:,}")
        avg = (self.session.total_tokens_in + self.session.total_tokens_out) / max(
            self.session.turn_count, 1
        )
        print(f"     平均每轮 Token: {avg:.0f}")

    def _cmd_platforms(self, args: str) -> None:
        try:
            from prometheus.gateway_manager import gateway_status

            status = gateway_status()
            if status.get("running"):
                print(f"  🌐 Gateway 运行中 (pid: {status.get('pid', '?')})")
            else:
                print("  🌐 Gateway 未运行")
        except Exception:
            print("  网关系统不可用")

    def _cmd_copy(self, args: str) -> None:
        if not self.session._last_assistant_message:
            print("  (没有可复制的回复)")
            return
        try:
            import subprocess

            process = subprocess.Popen(
                ["pbcopy"] if sys.platform == "darwin" else ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE,
            )
            process.communicate(self.session._last_assistant_message.encode())
            print("  📋 已复制到剪贴板")
        except Exception:
            print("  剪贴板不可用")

    def _cmd_image(self, args: str) -> None:
        path = args.strip()
        if not path:
            print("  用法: /image <path>")
            return
        if not os.path.exists(path):
            print(f"  文件不存在: {path}")
            return
        self.session._pending_image = path
        print(f"  🖼️  图片已附加: {path}")

    def _cmd_update(self, args: str) -> None:
        print("  🔄 正在检查更新...")
        try:
            from prometheus.cli.main import _cmd_update_check

            _cmd_update_check()
        except Exception as e:
            print(f"  更新检查失败: {e}")

    def _cmd_debug(self, args: str) -> None:
        print("  🐛 调试报告生成中...")
        info = {
            "turns": self.session.turn_count,
            "tokens_in": self.session.total_tokens_in,
            "tokens_out": self.session.total_tokens_out,
            "history_len": len(self.session.history),
            "model": self.session.agent.model,
        }
        print(f"  调试信息: {json.dumps(info, indent=2)}")

    def _cmd_stamp(self, args: str) -> None:
        parts = args.strip().split(maxsplit=1)
        if not parts:
            print("  用法: /stamp <path> [mark]")
            return
        seed_path = parts[0]
        mark = parts[1] if len(parts) > 1 else ""
        try:
            from prometheus.tools.registry import registry

            result = registry.dispatch("stamp_seed", {"seed_path": seed_path, "mark": mark})
            print(f"  {result}")
        except Exception as e:
            print(f"  错误: {e}")

    def _cmd_trace(self, args: str) -> None:
        path = args.strip()
        if not path:
            print("  用法: /trace <path>")
            return
        try:
            from prometheus.tools.registry import registry

            result = registry.dispatch("trace_seed", {"seed_path": path})
            print(f"  {result}")
        except Exception as e:
            print(f"  错误: {e}")

    def _cmd_append(self, args: str) -> None:
        parts = args.strip().split(maxsplit=1)
        if len(parts) < 2:
            print("  用法: /append <path> <note>")
            return
        try:
            from prometheus.tools.registry import registry

            result = registry.dispatch(
                "append_historical_note", {"seed_path": parts[0], "note": parts[1]}
            )
            print(f"  {result}")
        except Exception as e:
            print(f"  错误: {e}")

    def _cmd_inspect(self, args: str) -> None:
        path = args.strip()
        if not path:
            print("  用法: /inspect <path>")
            return
        try:
            from prometheus.tools.registry import registry

            result = registry.dispatch("inspect_seed", {"seed_path": path})
            print(f"  {result}")
        except Exception as e:
            print(f"  错误: {e}")

    def _cmd_stamps(self, args: str) -> None:
        path = args.strip()
        if not path:
            print("  用法: /stamps <path>")
            return
        try:
            from prometheus.tools.registry import registry

            result = registry.dispatch("list_stamps", {"seed_path": path})
            print(f"  {result}")
        except Exception as e:
            print(f"  错误: {e}")

    def _cmd_quit(self, args: str) -> str:
        return "EXIT"
