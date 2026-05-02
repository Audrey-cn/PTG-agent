"""
Prometheus 交互式 REPL
参考 Prometheus 的设计实现
"""

import json
import os

from prometheus._paths import get_paths

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.styles import Style

    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False

    class Completer:
        pass

    class Completion:
        pass


from prometheus.tools.registry import discover_builtin_tools, registry


class PrometheusREPL:
    """Prometheus 交互式 REPL 类"""

    def __init__(self):
        self.session = None
        self.history_path = get_paths().home / ".prometheus_history"
        self.running = False

        # 发现并加载工具
        discover_builtin_tools()

        if HAS_PROMPT_TOOLKIT:
            self._init_prompt_session()

    def _get_prompt_symbol(self):
        """获取当前皮肤的提示符"""
        try:
            from prometheus.skin_engine import get_active_prompt_symbol

            return get_active_prompt_symbol()
        except Exception:
            return "❯ "

    def _get_help_header(self):
        """获取帮助头"""
        try:
            from prometheus.skin_engine import get_active_help_header

            return get_active_help_header()
        except Exception:
            return "(🔥) Epic Commands"

    def _get_welcome(self):
        """获取欢迎语"""
        try:
            from prometheus.skin_engine import get_active_welcome

            return get_active_welcome()
        except Exception:
            return "Welcome to Prometheus! 🔥"

    def _get_goodbye(self):
        """获取告别语"""
        try:
            from prometheus.skin_engine import get_active_goodbye

            return get_active_goodbye()
        except Exception:
            return "The fire burns eternal! 🔥"

    def _init_prompt_session(self):
        """初始化 prompt_toolkit 会话"""
        history = FileHistory(str(self.history_path))

        style = Style.from_dict(
            {
                "prompt": "#ff8800 bold",
                "info": "#00ff00",
                "error": "#ff0000",
                "warning": "#ffff00",
            }
        )

        self.session = PromptSession(
            history=history,
            completer=PrometheusCompleter(),
            style=style,
            enable_history_search=True,
        )

    def get_prompt(self) -> str:
        """获取提示符"""
        return self._get_prompt_symbol()

    def list_skins(self):
        """列出所有皮肤"""
        try:
            from prometheus.skin_engine import get_active_skin_name, list_skins

            skins = list_skins()
            active_name = get_active_skin_name()
            print("\n  Available skins:")
            for skin in skins:
                marker = " (*)" if skin["name"] == active_name else ""
                print(f"    {skin['name']:10} - {skin['description']}{marker}")
            print()
        except Exception as e:
            print(f"  Error: {e}")

    def set_skin(self, skin_name):
        """切换皮肤"""
        try:
            from prometheus.skin_engine import list_skins, set_active_skin

            available = {s["name"] for s in list_skins()}
            if skin_name not in available:
                print(f"  Error: Unknown skin '{skin_name}'. Available: {', '.join(available)}")
                return
            set_active_skin(skin_name)
            print(f"  Skin switched to '{skin_name}'! ✨")
        except Exception as e:
            print(f"  Error: {e}")

    def print_banner(self):
        """打印史诗级欢迎横幅"""
        try:
            from prometheus.display.banner import HAS_RICH, print_simple_banner

            if HAS_RICH:
                try:
                    from rich.console import Console

                    console = Console()
                    from prometheus.display.banner import build_welcome_banner

                    console.print(build_welcome_banner(console))
                    return
                except Exception:
                    pass
            print_simple_banner()
        except Exception:
            lines = [
                "",
                "=" * 70,
                "",
                "        (  )@(   )@   )@   (   @(    )",
                "     (@@@@)  (@@@@@@)  (@@@@@@)  (@@)",
                "   (   @@    (   @@   (@@@   )  (   )",
                "   (@@@@  @@@@)  (@@@@@@)  (@@@@@@@)",
                "   (    @@       (@@@          @@    )",
                "    @@@@   @@@@   (@@@@)    (@@@@",
                "      (@@@@)        (@@@@@@@@)   @@",
                "         (   @@@@)@@)     (@@@   @@",
                "    (@@@@)  @@   )@@)@@)  (@@@@@@@",
                "       (     )    )@)@@@)   (    )",
                "     )@@@)   @@  (@@@@)@@)  @@   )",
                "   (@@@@)    (@@)  )@@)@@@)   @@",
                "     (   )   (   )   )@@)   )",
                "      )       )   (   ) )   )",
                "",
                "  Prometheus · Teach-To-Grow",
                "  Version: 0.8.0 · Epic Chronicler",
                "  Founder: Audrey · 001X",
                "",
                "  Available Commands:",
                "    System: /setup, /doctor, /status, /update, /repl",
                "    Config: /config show, /model show, /model providers",
                "    Seeds: /seed list, /seed search, /seed view",
                "    Genes: /gene list",
                "    Memory: /memory recall, /memory stats",
                "    Knowledge: /kb search, /dict",
                "    Skills: /skills",
                "",
                "  Tip: Run /help for interactive commands",
                "  Tip: Run ptg doctor to check system health",
                "",
                "=" * 70,
                "",
            ]
            print("\n".join(lines))

    def print_help(self):
        """打印史诗级帮助信息"""
        help_text = f"""
Prometheus 命令帮助: {self._get_help_header()}

  help                    显示此帮助信息
  exit / quit / Ctrl+D    退出 REPL

  tools                   列出所有可用工具
  tool <name>             显示工具详情
  run <tool> <args>       运行工具（JSON 参数）

  stamp <path> [mark]     在种子上烙印
  trace <path>            追溯种子历史
  append <path> <note>    附加历史记录
  inspect <path>          检查种子
  stamps <path>           列出种子上的烙印

  skin                    显示当前皮肤
  skin <name>             切换皮肤 (default/zeus/athena/hades)

  clear / cls             清空屏幕
        """
        print(help_text)

    def list_tools(self):
        """列出所有可用工具"""
        tool_names = registry.get_all_tool_names()
        print(f"\n可用工具 ({len(tool_names)}):")

        # 按工具集分组
        tools_by_set: dict[str, list[str]] = {}
        for name in tool_names:
            toolset = registry.get_toolset_for_tool(name) or "default"
            if toolset not in tools_by_set:
                tools_by_set[toolset] = []
            tools_by_set[toolset].append(name)

        for toolset, names in sorted(tools_by_set.items()):
            emoji = ""
            if names:
                emoji = registry.get_emoji(names[0], "")
            print(f"\n  {emoji} {toolset}:")
            for name in sorted(names):
                desc = registry.get_schema(name)
                desc_text = desc.get("description", "") if desc else ""
                print(f"    - {name}: {desc_text[:50]}{'...' if len(desc_text) > 50 else ''}")
        print()

    def show_tool(self, tool_name: str):
        """显示工具详情"""
        schema = registry.get_schema(tool_name)
        if not schema:
            print(f"错误: 工具 '{tool_name}' 不存在")
            return

        emoji = registry.get_emoji(tool_name)
        toolset = registry.get_toolset_for_tool(tool_name)

        print(f"\n{emoji} {tool_name} (工具集: {toolset})")
        print(f"描述: {schema.get('description', '')}")

        params = schema.get("parameters", {})
        if params:
            print("\n参数:")
            props = params.get("properties", {})
            required = set(params.get("required", []))

            for name, prop in sorted(props.items()):
                req_marker = "*" if name in required else " "
                print(f"  {req_marker} {name}: {prop.get('type', 'any')}")
                desc = prop.get("description", "")
                if desc:
                    print(f"      {desc}")
        print()

    def run_tool(self, tool_name: str, args_str: str):
        """运行工具"""
        try:
            args = json.loads(args_str) if args_str else {}
        except json.JSONDecodeError:
            print(f"错误: 无效的 JSON 参数: {args_str}")
            return

        try:
            result = registry.dispatch(tool_name, args)
            print(result)
        except Exception as e:
            print(f"错误: 工具执行失败: {e}")

    def handle_command(self, command: str) -> bool:
        """处理命令，返回是否继续运行"""
        command = command.strip()

        if not command:
            return True

        parts = command.split(maxsplit=2)
        cmd = parts[0].lower()

        if cmd in ["exit", "quit"]:
            return False

        if cmd in ["help", "?"]:
            self.print_help()
            return True

        if cmd == "tools":
            self.list_tools()
            return True

        if cmd == "skin":
            if len(parts) >= 2:
                self.set_skin(parts[1])
            else:
                self.list_skins()
            return True

        if cmd == "tool" and len(parts) >= 2:
            self.show_tool(parts[1])
            return True

        if cmd == "run" and len(parts) >= 2:
            tool_name = parts[1]
            args_str = parts[2] if len(parts) >= 3 else ""
            self.run_tool(tool_name, args_str)
            return True

        # 便捷命令
        if cmd == "stamp" and len(parts) >= 2:
            seed_path = parts[1]
            mark = parts[2] if len(parts) >= 3 else ""
            self.run_tool("stamp_seed", json.dumps({"seed_path": seed_path, "mark": mark}))
            return True

        if cmd == "trace" and len(parts) >= 2:
            seed_path = parts[1]
            self.run_tool("trace_seed", json.dumps({"seed_path": seed_path}))
            return True

        if cmd == "append" and len(parts) >= 3:
            seed_path = parts[1]
            note = parts[2]
            self.run_tool(
                "append_historical_note", json.dumps({"seed_path": seed_path, "note": note})
            )
            return True

        if cmd == "inspect" and len(parts) >= 2:
            seed_path = parts[1]
            detail = parts[2] if len(parts) >= 3 else "basic"
            self.run_tool(
                "inspect_seed", json.dumps({"seed_path": seed_path, "detail_level": detail})
            )
            return True

        if cmd == "stamps" and len(parts) >= 2:
            seed_path = parts[1]
            self.run_tool("list_stamps", json.dumps({"seed_path": seed_path}))
            return True

        if cmd in ["clear", "cls"]:
            os.system("cls" if os.name == "nt" else "clear")
            return True

        print(f"未知命令: {cmd}。输入 'help' 获取帮助。")
        return True

    def run_interactive(self):
        """运行交互式 REPL"""
        self.print_banner()
        self.running = True

        if HAS_PROMPT_TOOLKIT:
            self._run_with_prompt_toolkit()
        else:
            self._run_simple()

    def _run_with_prompt_toolkit(self):
        """使用 prompt_toolkit 运行"""
        try:
            while self.running:
                try:
                    prompt = HTML("<prompt>prometheus> </prompt>")
                    command = self.session.prompt(prompt)
                    if not self.handle_command(command):
                        break
                except EOFError:
                    break
                except KeyboardInterrupt:
                    continue
        except Exception as e:
            print(f"\n错误: {e}")
        finally:
            print("\n再见！")

    def _run_simple(self):
        """使用简单的 input() 运行（无 prompt_toolkit）"""
        print("注意: 未安装 prompt_toolkit，使用简单输入模式")
        print("安装提示: pip install prompt_toolkit\n")

        try:
            while self.running:
                try:
                    command = input(self.get_prompt())
                    if not self.handle_command(command):
                        break
                except EOFError:
                    break
                except KeyboardInterrupt:
                    print("^C")
                    continue
        except Exception as e:
            print(f"\n错误: {e}")
        finally:
            print("\n再见！")


class PrometheusCompleter(Completer):
    """命令补全器"""

    def __init__(self):
        self.commands = [
            "help",
            "exit",
            "quit",
            "tools",
            "tool",
            "run",
            "stamp",
            "trace",
            "append",
            "inspect",
            "stamps",
            "clear",
            "cls",
        ]

        # 预先加载工具
        discover_builtin_tools()
        self.tool_names = registry.get_all_tool_names()

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        words = text.split()

        if len(words) == 0:
            for cmd in sorted(self.commands):
                yield Completion(cmd, start_position=0)
        elif len(words) == 1:
            for cmd in sorted(self.commands):
                if cmd.startswith(words[0]):
                    yield Completion(cmd, start_position=-len(words[0]))
        elif len(words) == 2 and words[0] in ["tool", "run"]:
            for name in sorted(self.tool_names):
                if name.startswith(words[1]):
                    yield Completion(name, start_position=-len(words[1]))


def main():
    """主函数"""
    repl = PrometheusREPL()
    repl.run_interactive()


if __name__ == "__main__":
    main()
