"""Interactive TUI improvements for Prometheus."""

import readline
import shlex
from collections.abc import Callable
from typing import Any

from prometheus._paths import get_paths

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.syntax import Syntax

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

console = Console() if RICH_AVAILABLE else None


class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


class Colors256:
    """256-color palette for richer output."""

    GOLD = "\033[38;5;220m"
    ORANGE = "\033[38;5;214m"
    PURPLE = "\033[38;5;141m"
    CORAL = "\033[38;5;210m"
    TEAL = "\033[38;5;80m"


PROMPT_COLORS = {
    "default": Colors.CYAN,
    "error": Colors.RED,
    "success": Colors.GREEN,
    "warning": Colors.YELLOW,
    "info": Colors.BLUE,
}


def colorize(text: str, color: str) -> str:
    """Colorize text with ANSI color."""
    return f"{color}{text}{Colors.RESET}"


def bold(text: str) -> str:
    """Make text bold."""
    return f"{Colors.BOLD}{text}{Colors.RESET}"


def prompt(
    message: str,
    color: str = Colors.CYAN,
    default: str | None = None,
) -> str:
    """Display a prompt and get user input.

    Args:
        message: Prompt message
        color: Color for the prompt
        default: Default value

    Returns:
        User input string
    """
    prompt_text = f"{color}{message}{Colors.RESET}"

    if default:
        prompt_text += f" [{Colors.DIM}{default}{Colors.RESET}]"

    try:
        return input(prompt_text + ": ").strip() or default or ""
    except (EOFError, KeyboardInterrupt):
        return ""


def confirm(message: str, default: bool = False) -> bool:
    """Ask for user confirmation.

    Args:
        message: Confirmation message
        default: Default value

    Returns:
        True if user confirmed
    """
    suffix = " [Y/n]" if default else " [y/N]"
    response = input(f"{Colors.YELLOW}{message}{suffix}{Colors.RESET}: ").strip().lower()

    if not response:
        return default

    return response in ("y", "yes")


class ProgressIndicator:
    """Show progress for long-running operations."""

    def __init__(self, description: str = "Working..."):
        self.description = description
        self._progress: Any | None = None
        self._task: Any | None = None

    def __enter__(self):
        if RICH_AVAILABLE:
            self._progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            )
            self._progress.__enter__()
            self._task = self._progress.add_task(self.description, total=None)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._progress:
            self._progress.__exit__(exc_type, exc_val, exc_tb)

    def update(self, message: str):
        """Update the progress message."""
        if self._task is not None:
            self._progress.update(self._task, description=message)


class InteractiveInput:
    """Enhanced interactive input with history and completion."""

    def __init__(self, history_file: str | None = None):
        self._history_file = history_file
        self._history: list[str] = []
        self._completions: dict[str, list[str]] = {}
        self._current_completion_index = 0
        self._completions_matches: list[str] = []

        if history_file:
            self._load_history()

        readline.parse_and_bind("tab: complete")
        readline.set_completer(self._complete)

    def _load_history(self):
        """Load input history from file."""
        try:
            history_path = get_paths().home / "input_history"
            if history_path.exists():
                with open(history_path) as f:
                    self._history = [line.strip() for line in f if line.strip()]
        except Exception:
            pass

    def _save_history(self):
        """Save input history to file."""
        try:
            history_path = get_paths().home / "input_history"
            history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(history_path, "w") as f:
                for line in self._history[-1000:]:
                    f.write(f"{line}\n")
        except Exception:
            pass

    def add_completions(self, command: str, completions: list[str]):
        """Add completions for a command."""
        self._completions[command] = completions

    def _complete(self, text: str, state: int) -> str | None:
        """Readline completion callback."""
        if state == 0:
            line = readline.get_line_buffer()
            parts = shlex.split(line)

            if not parts:
                self._completions_matches = []
                return None

            if len(parts) == 1:
                self._completions_matches = [c for c in self._completions if c.startswith(text)]
            else:
                cmd = parts[0]
                if cmd in self._completions:
                    prefix = text
                    self._completions_matches = [
                        c for c in self._completions[cmd] if c.startswith(prefix)
                    ]
                else:
                    self._completions_matches = []

        if state < len(self._completions_matches):
            return self._completions_matches[state]
        return None

    def input(self, prompt_text: str = "> ") -> str:
        """Get input from user."""
        try:
            user_input = input(prompt_text)
            if user_input.strip():
                self._history.append(user_input)
                self._save_history()
            return user_input
        except (EOFError, KeyboardInterrupt):
            return ""

    def get_history(self) -> list[str]:
        """Get input history."""
        return self._history.copy()


class CommandRegistry:
    """Registry of available commands with metadata."""

    def __init__(self):
        self._commands: dict[str, dict[str, Any]] = {}

    def register(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        aliases: list[str] | None = None,
        args: list[dict[str, str]] | None = None,
    ):
        """Register a command."""
        self._commands[name] = {
            "name": name,
            "handler": handler,
            "description": description,
            "aliases": aliases or [],
            "args": args or [],
        }

        for alias in aliases or []:
            self._commands[alias] = self._commands[name]

    def get_command(self, name: str) -> dict[str, Any] | None:
        """Get command by name."""
        return self._commands.get(name)

    def list_commands(self) -> list[dict[str, Any]]:
        """List all registered commands."""
        seen = set()
        commands = []
        for cmd in self._commands.values():
            if cmd["name"] not in seen:
                seen.add(cmd["name"])
                commands.append(cmd)
        return commands

    def get_completions(self) -> dict[str, list[str]]:
        """Get completions for all commands."""
        return {
            name: [cmd["name"]] + cmd.get("aliases", [])
            for name, cmd in self._commands.items()
            if name == cmd["name"]
        }


_global_registry: CommandRegistry | None = None


def get_command_registry() -> CommandRegistry:
    """Get the global command registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = CommandRegistry()
    return _global_registry


def display_markdown(text: str):
    """Display markdown formatted text."""
    if RICH_AVAILABLE and console:
        md = Markdown(text)
        console.print(md)
    else:
        print(text)


def display_panel(
    content: str,
    title: str = "",
    border_color: str = Colors.CYAN,
):
    """Display content in a panel."""
    if RICH_AVAILABLE and console:
        panel = Panel(
            content,
            title=title,
            border_style=border_color,
        )
        console.print(panel)
    else:
        if title:
            print(f"=== {title} ===")
        print(content)


def display_error(message: str):
    """Display an error message."""
    print(f"{Colors.RED}Error: {message}{Colors.RESET}")


def display_success(message: str):
    """Display a success message."""
    print(f"{Colors.GREEN}Success: {message}{Colors.RESET}")


def display_warning(message: str):
    """Display a warning message."""
    print(f"{Colors.YELLOW}Warning: {message}{Colors.RESET}")


def display_info(message: str):
    """Display an info message."""
    print(f"{Colors.BLUE}Info: {message}{Colors.RESET}")


def display_table(headers: list[str], rows: list[list[str]]):
    """Display data as a table."""
    if RICH_AVAILABLE and console:
        from rich.table import Table

        table = Table(show_header=True, header_style="bold")
        for header in headers:
            table.add_column(header)

        for row in rows:
            table.add_row(*row)

        console.print(table)
    else:
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))

        header_line = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
        separator = "-+-".join("-" * w for w in col_widths)

        print(header_line)
        print(separator)
        for row in rows:
            print(" | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)))


class InteractiveShell:
    """Interactive shell for Prometheus."""

    def __init__(self):
        self._registry = get_command_registry()
        self._input = InteractiveInput()
        self._running = False

        self._setup_default_completions()

    def _setup_default_completions(self):
        """Set up default command completions."""
        self._input.add_completions("help", ["help", "status", "exit", "quit"])
        self._input.add_completions("exit", ["exit", "quit"])
        self._input.add_completions("set", ["model", "provider", "temperature", "max_tokens"])

    def run(self):
        """Run the interactive shell."""
        self._running = True

        print(f"{Colors.CYAN}Prometheus Interactive Shell{Colors.RESET}")
        print(f"{Colors.DIM}Type 'help' for available commands{Colors.RESET}\n")

        while self._running:
            try:
                user_input = self._input.input(f"{Colors.CYAN}prometheus> {Colors.RESET}")

                if not user_input.strip():
                    continue

                parts = shlex.split(user_input)
                command = parts[0]
                args = parts[1:]

                self._execute_command(command, args)

            except KeyboardInterrupt:
                print()
            except EOFError:
                break

        print(f"\n{Colors.DIM}Goodbye!{Colors.RESET}")

    def _execute_command(self, command: str, args: list[str]):
        """Execute a command."""
        cmd_info = self._registry.get_command(command)

        if not cmd_info:
            display_error(f"Unknown command: {command}")
            display_info("Type 'help' for available commands")
            return

        try:
            handler = cmd_info["handler"]
            handler(args)
        except Exception as e:
            display_error(f"Command failed: {e}")

    def stop(self):
        """Stop the shell."""
        self._running = False


def create_shell() -> InteractiveShell:
    """Create an interactive shell instance."""
    return InteractiveShell()


if __name__ == "__main__":
    shell = create_shell()
    shell.run()
