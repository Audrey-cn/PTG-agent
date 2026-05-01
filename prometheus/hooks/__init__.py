"""🐚 Prometheus Hooks 模块."""

from prometheus.hooks.shell_hooks import (
    ShellHookRunner,
    ShellHookSpec,
    get_hook_runner,
    register_shell_hooks,
)

__all__ = [
    "ShellHookRunner",
    "ShellHookSpec",
    "get_hook_runner",
    "register_shell_hooks",
]
