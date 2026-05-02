from __future__ import annotations

"""Rich-based TUI chat session for Prometheus.

Activate with: prometheus --tui  or  prometheus chat --tui
"""

import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime

from prometheus.interactive_tui import RICH_AVAILABLE, Colors, Colors256, console

if RICH_AVAILABLE:
    from rich.box import HEAVY, ROUNDED
    from rich.live import Live
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    LAYOUT_AVAILABLE = True
else:
    LAYOUT_AVAILABLE = False


@dataclass
class ChatMessage:
    role: str
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).strftime("%H:%M:%S")


def render_user_message(message: ChatMessage) -> Panel:
    user_text = Text(message.content, style=f"bold {Colors256.GOLD}")
    return Panel(
        user_text,
        title=f"[bold]{Colors256.ORANGE}You[/] {message.timestamp}",
        border_style=Colors256.ORANGE,
        box=ROUNDED,
    )


def render_assistant_message(message: ChatMessage) -> Panel:
    md = Markdown(message.content, code_theme="monokai")
    return Panel(
        md,
        title=f"[bold]{Colors256.PURPLE}Prometheus[/] {message.timestamp}",
        border_style=Colors256.PURPLE,
        box=ROUNDED,
    )


def render_tool_call(name: str, args: dict) -> Panel:
    table = Table(box=None, show_header=False, pad_edge=False)
    table.add_column("Param", style="dim", width=14)
    table.add_column("Value", style=Colors256.TEAL)
    for k, v in args.items():
        val = json.dumps(v, ensure_ascii=False)
        if len(val) > 80:
            val = val[:77] + "..."
        table.add_row(k, val)
    return Panel(
        table,
        title=f"[bold]{Colors256.CYAN}🔧 {name}[/]",
        border_style=Colors256.CYAN,
        box=HEAVY,
    )


def render_tool_result(name: str, result: str) -> Panel:
    preview = result[:500]
    if len(result) > 500:
        preview += f"\n... [{len(result) - 500} more chars]"
    return Panel(
        Text(preview, style=Colors256.TEAL),
        title=f"[bold]{Colors256.GREEN}✅ {name}[/]",
        border_style=Colors256.GREEN,
        box=HEAVY,
    )


def render_system_message(message: str) -> Panel:
    return Panel(
        Text(message, style="dim italic"),
        border_style="dim",
        box=ROUNDED,
    )


def render_status_bar(session_name: str, model: str, msg_count: int):
    left = Text(
        f" {session_name} ",
        style=f"bold white on {Colors256.PURPLE.replace(chr(27) + '[', '').replace('m', '').split(';')[-1] if ';' in Colors256.PURPLE else ''}",
    )
    mid = Text(f" {model} ", style="dim")
    right = Text(f" {msg_count} messages ", style="dim")
    return left


class TUIChatSession:
    def __init__(
        self,
        session_name: str = "chat",
        model: str = "default",
        system_prompt: str | None = None,
    ):
        self.session_name = session_name
        self.model = model
        self.system_prompt = system_prompt
        self.messages: list[ChatMessage] = []
        self._live: Live | None = None
        self._current_stream: str = ""

    def add_user_message(self, content: str):
        msg = ChatMessage(role="user", content=content)
        self.messages.append(msg)
        if LAYOUT_AVAILABLE and console:
            console.print(render_user_message(msg))

    def add_assistant_message(self, content: str):
        msg = ChatMessage(role="assistant", content=content)
        self.messages.append(msg)
        if LAYOUT_AVAILABLE and console:
            console.print(render_assistant_message(msg))

    def add_tool_call(self, name: str, args: dict):
        if LAYOUT_AVAILABLE and console:
            console.print(render_tool_call(name, args))

    def add_tool_result(self, name: str, result: str):
        if LAYOUT_AVAILABLE and console:
            console.print(render_tool_result(name, result))

    def add_system_message(self, content: str):
        if LAYOUT_AVAILABLE and console:
            console.print(render_system_message(content))

    def display_header(self):
        if not LAYOUT_AVAILABLE or not console:
            self._print_header_fallback()
            return
        console.print()
        header = Panel(
            Text("Prometheus Chat", style=f"bold {Colors256.GOLD}", justify="center"),
            subtitle=f"[dim]{self.model}[/]",
            border_style=Colors256.GOLD,
            box=HEAVY,
        )
        console.print(header)
        if self.system_prompt:
            console.print(render_system_message(self.system_prompt))

    def _print_header_fallback(self):
        print(f"\n{Colors256.GOLD}🔥 Prometheus Chat{Colors.RESET}")
        print(f"{Colors.DIM}Model: {self.model}{Colors.RESET}")
        if self.system_prompt:
            print(f"{Colors.DIM}{self.system_prompt}{Colors.RESET}")
        print()

    def start_streaming(self):
        self._current_stream = ""

    def append_stream(self, chunk: str):
        self._current_stream += chunk

    def finish_streaming(self) -> str:
        content = self._current_stream
        self._current_stream = ""
        self.add_assistant_message(content)
        return content

    @property
    def message_count(self) -> int:
        return len(self.messages)


def parse_tui_flag() -> bool:
    """Check if --tui flag is present in sys.argv."""
    return "--tui" in sys.argv


def run_tui_chat(
    model: str = "default",
    system_prompt: str | None = None,
    provider: str | None = None,
):
    if not LAYOUT_AVAILABLE:
        print("Rich library is required for TUI mode. Install with: pip install rich")
        sys.exit(1)

    session = TUIChatSession(
        session_name="chat",
        model=model,
        system_prompt=system_prompt,
    )
    session.display_header()
    session.add_system_message("Type your message and press Enter.  Type /help for commands.")

    while True:
        try:
            user_input = input(f"\n{Colors256.GOLD}You › {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Colors.DIM}Session ended.{Colors.RESET}")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            _handle_slash_command(user_input, session)
            continue

        session.add_user_message(user_input)
        session.add_system_message("(Model call would be dispatched here — connect to agent_loop)")
        print()


def _handle_slash_command(cmd: str, session: TUIChatSession):
    parts = cmd.split()
    action = parts[0].lower()

    if action == "/help":
        session.add_system_message(
            "Commands:\n"
            "  /help     Show this help\n"
            "  /clear    Clear session\n"
            "  /exit     End session\n"
            "  /model    Show current model\n"
            "  /history  Show message history"
        )
    elif action == "/clear":
        session.messages.clear()
        session.add_system_message("Session cleared.")
    elif action == "/exit":
        raise EOFError
    elif action == "/model":
        session.add_system_message(f"Current model: {session.model}")
    elif action == "/history":
        count = session.message_count
        session.add_system_message(f"Messages in session: {count}")
    else:
        session.add_system_message(f"Unknown command: {action}. Type /help for available commands.")
