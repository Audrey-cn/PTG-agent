"""
CLI 参数解析模块 - 从 main.py 中提取的参数解析功能
"""

import argparse
import sys
from typing import Optional


def _add_accept_hooks_flag(parser) -> None:
    """Attach the ``--accept-hooks`` flag.  Shared across every agent
    subparser so the flag works regardless of CLI position."""
    parser.add_argument(
        "--accept-hooks",
        action="store_true",
        default=argparse.SUPPRESS,
        help=(
            "Auto-approve unseen shell hooks without a TTY prompt "
            "(equivalent to PROMETHEUS_ACCEPT_HOOKS=1 / hooks_auto_accept: true)."
        ),
    )


def _require_tty(command_name: str) -> None:
    """Exit with a clear error if stdin is not a terminal.

    Interactive TUI commands (prometheus tools, prometheus setup, prometheus model) use
    curses or input() prompts that spin at 100% CPU when stdin is a pipe.
    This guard prevents accidental non-interactive invocation.
    """
    if not sys.stdin.isatty():
        print(
            f"Error: 'prometheus {command_name}' requires an interactive terminal.\n"
            f"It cannot be run through a pipe or non-interactive subprocess.\n"
            f"Run it directly in your terminal instead.",
            file=sys.stderr,
        )
        sys.exit(1)


def create_main_parser() -> argparse.ArgumentParser:
    """创建主命令行解析器"""
    parser = argparse.ArgumentParser(
        prog="prometheus",
        description="Prometheus — Teach-To-Grow 种子基因编辑器，史诗编史官系统",
        epilog="""
Examples:
    prometheus                     # Interactive chat (default)
    prometheus chat                # Interactive chat
    prometheus gateway             # Run gateway in foreground
    prometheus setup               # Interactive setup wizard
    prometheus status              # Show status of all components
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 主命令
    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        description="Available commands",
        metavar="COMMAND",
    )

    # chat 命令
    chat_parser = subparsers.add_parser(
        "chat",
        help="Interactive chat (default)",
        description="Start an interactive chat session.",
    )
    _add_accept_hooks_flag(chat_parser)
    chat_parser.add_argument(
        "--session",
        metavar="SESSION",
        help="Session name or ID to resume",
    )
    chat_parser.add_argument(
        "--toolsets",
        metavar="TOOLSETS",
        help="Comma-separated list of toolsets to enable",
    )
    chat_parser.add_argument(
        "--model",
        metavar="MODEL",
        help="Override default model",
    )
    chat_parser.add_argument(
        "--provider",
        metavar="PROVIDER",
        help="Override default provider",
    )
    chat_parser.add_argument(
        "--no-tools",
        action="store_true",
        help="Disable all tools",
    )

    # gateway 命令
    gateway_parser = subparsers.add_parser(
        "gateway",
        help="Gateway management",
        description="Manage the Prometheus gateway service.",
    )
    gateway_subparsers = gateway_parser.add_subparsers(
        dest="gateway_command",
        title="gateway commands",
        metavar="COMMAND",
    )

    gateway_subparsers.add_parser(
        "start",
        help="Start gateway service",
    )
    gateway_subparsers.add_parser(
        "stop", 
        help="Stop gateway service",
    )
    gateway_subparsers.add_parser(
        "status",
        help="Show gateway status",
    )
    gateway_subparsers.add_parser(
        "install",
        help="Install gateway service",
    )
    gateway_subparsers.add_parser(
        "uninstall",
        help="Uninstall gateway service",
    )

    # setup 命令
    setup_parser = subparsers.add_parser(
        "setup",
        help="Interactive setup wizard",
        description="Run the interactive setup wizard.",
    )
    _add_accept_hooks_flag(setup_parser)

    # status 命令
    subparsers.add_parser(
        "status",
        help="Show status of all components",
        description="Show status of Prometheus components.",
    )

    # version 命令
    subparsers.add_parser(
        "version",
        help="Show version",
        description="Show Prometheus version.",
    )

    return parser


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数"""
    parser = create_main_parser()
    
    # 如果没有提供命令，默认使用 chat
    if len(sys.argv) == 1:
        sys.argv.append("chat")
    
    return parser.parse_args()