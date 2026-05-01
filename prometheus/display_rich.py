from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
    from rich.status import Status
    from rich.syntax import Syntax
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

_console: Any = None


def _get_console() -> Any:
    global _console
    if _console is None:
        if RICH_AVAILABLE:
            _console = Console()
        else:
            _console = None
    return _console


class RichDisplay:
    def __init__(self) -> None:
        self._console = _get_console()

    def progress_bar(
        self,
        iterable: Iterable[Any],
        description: str = "Processing",
    ) -> Iterator[Any]:
        if RICH_AVAILABLE and self._console:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self._console,
            ) as progress:
                task = progress.add_task(
                    description, total=len(iterable) if hasattr(iterable, "__len__") else None
                )
                for item in iterable:
                    yield item
                    progress.advance(task)
        else:
            count = 0
            for item in iterable:
                yield item
                count += 1
                print(f"\r{description}: {count}", end="", flush=True)
            print()

    def table(
        self,
        headers: list[str],
        rows: list[list[Any]],
        title: str | None = None,
    ) -> None:
        if RICH_AVAILABLE and self._console:
            table = Table(title=title, show_header=True, header_style="bold magenta")
            for header in headers:
                table.add_column(header)
            for row in rows:
                table.add_row(*[str(cell) for cell in row])
            self._console.print(table)
        else:
            if title:
                print(f"\n{title}\n")
            widths = [
                max(len(str(row[i])) for row in [headers] + rows) for i in range(len(headers))
            ]
            header_line = " | ".join(h.ljust(w) for h, w in zip(headers, widths, strict=False))
            print(header_line)
            print("-" * len(header_line))
            for row in rows:
                print(" | ".join(str(cell).ljust(w) for cell, w in zip(row, widths, strict=False)))

    def panel(
        self,
        content: str,
        title: str | None = None,
        style: str = "blue",
    ) -> None:
        if RICH_AVAILABLE and self._console:
            self._console.print(Panel(content, title=title, border_style=style))
        else:
            if title:
                print(f"\n{'=' * 10} {title} {'=' * 10}")
            print(content)
            print("=" * 40)

    @contextmanager
    def status_spinner(self, message: str = "Loading...") -> Iterator[None]:
        if RICH_AVAILABLE and self._console:
            with self._console.status(message, spinner="dots"):
                yield
        else:
            print(f"{message}...")
            yield

    def print_markdown(self, text: str) -> None:
        if RICH_AVAILABLE and self._console:
            self._console.print(Markdown(text))
        else:
            print(text)

    def print_code(self, code: str, language: str = "python") -> None:
        if RICH_AVAILABLE and self._console:
            self._console.print(Syntax(code, language, theme="monokai", line_numbers=True))
        else:
            print(f"```{language}")
            print(code)
            print("```")

    def print(self, message: str, style: str | None = None) -> None:
        if RICH_AVAILABLE and self._console:
            self._console.print(message, style=style)
        else:
            print(message)


def progress_bar(iterable: Iterable[Any], description: str = "Processing") -> Iterator[Any]:
    display = RichDisplay()
    yield from display.progress_bar(iterable, description)


def table(headers: list[str], rows: list[list[Any]], title: str | None = None) -> None:
    display = RichDisplay()
    display.table(headers, rows, title)


def panel(content: str, title: str | None = None, style: str = "blue") -> None:
    display = RichDisplay()
    display.panel(content, title, style)


@contextmanager
def status_spinner(message: str = "Loading...") -> Iterator[None]:
    display = RichDisplay()
    with display.status_spinner(message):
        yield


def print_markdown(text: str) -> None:
    display = RichDisplay()
    display.print_markdown(text)


def print_code(code: str, language: str = "python") -> None:
    display = RichDisplay()
    display.print_code(code, language)
