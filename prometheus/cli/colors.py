from __future__ import annotations


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


def colorize(text: str, color: str) -> str:
    return f"{color}{text}{Colors.RESET}"


def color(text: str, *colors: str) -> str:
    """Color text with multiple color codes."""
    color_codes = "".join(colors)
    return f"{color_codes}{text}{Colors.RESET}"


def strip_colors(text: str) -> str:
    import re

    ansi_pattern = re.compile(r"\033\[[0-9;]*m")
    return ansi_pattern.sub("", text)
