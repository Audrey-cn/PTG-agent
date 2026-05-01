"""🐚 Shell Hooks - Shell 脚本钩子."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 60
MAX_TIMEOUT_SECONDS = 300


@dataclass
class ShellHookSpec:
    """Shell 钩子规格"""

    event: str
    command: str
    matcher: str | None = None
    timeout: int = DEFAULT_TIMEOUT_SECONDS
    compiled_matcher: re.Pattern | None = field(default=None, repr=False)

    def __post_init__(self):
        if isinstance(self.matcher, str):
            stripped = self.matcher.strip()
            self.matcher = stripped if stripped else None
        if self.matcher:
            try:
                self.compiled_matcher = re.compile(self.matcher)
            except re.error as exc:
                logger.warning(f"shell hook matcher {self.matcher!r} is invalid: {exc}")
                self.compiled_matcher = None

    def matches_tool(self, tool_name: str | None) -> bool:
        if not self.matcher:
            return True
        if tool_name is None:
            return False
        if self.compiled_matcher is not None:
            return self.compiled_matcher.fullmatch(tool_name) is not None
        return tool_name == self.matcher


class ShellHookRunner:
    """Shell 钩子运行器"""

    VALID_HOOKS = {
        "pre_tool_call",
        "post_tool_call",
        "pre_llm_call",
        "post_llm_call",
        "on_session_start",
        "on_session_end",
    }

    def __init__(self):
        self._hooks: dict[str, list[ShellHookSpec]] = {}
        self._lock = threading.Lock()

    def register(self, spec: ShellHookSpec) -> bool:
        """注册钩子"""
        if spec.event not in self.VALID_HOOKS:
            logger.warning(f"Unknown hook event: {spec.event}")
            return False

        with self._lock:
            if spec.event not in self._hooks:
                self._hooks[spec.event] = []
            self._hooks[spec.event].append(spec)
        return True

    def run_pre_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        session_id: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any] | None:
        """在工具调用前运行钩子"""
        return self._run_hook(
            "pre_tool_call",
            tool_name=tool_name,
            tool_input=args,
            session_id=session_id or "unknown",
            extra={"task_id": task_id},
        )

    def run_post_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: Any,
        session_id: str | None = None,
    ) -> dict[str, Any] | None:
        """在工具调用后运行钩子"""
        return self._run_hook(
            "post_tool_call",
            tool_name=tool_name,
            tool_input=args,
            tool_result=str(result)[:1000],
            session_id=session_id or "unknown",
        )

    def run_pre_llm_call(
        self,
        model: str,
        messages: list[dict[str, Any]],
        session_id: str | None = None,
    ) -> dict[str, Any] | None:
        """在 LLM 调用前运行钩子"""
        return self._run_hook(
            "pre_llm_call",
            model=model,
            messages_count=len(messages),
            session_id=session_id or "unknown",
        )

    def _run_hook(
        self,
        event: str,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """运行指定事件的钩子"""
        specs = self._hooks.get(event, [])
        if not specs:
            return None

        results = []
        for spec in specs:
            try:
                result = self._execute_script(spec, kwargs)
                if result is not None:
                    results.append(result)
            except Exception as exc:
                logger.error(f"Hook execution failed for {event}: {exc}")

        if not results:
            return None

        first_result = results[0]
        if event == "pre_tool_call" and isinstance(first_result, dict):
            if first_result.get("action") == "block" or first_result.get("decision") == "block":
                return first_result

        return first_result

    def _execute_script(
        self,
        spec: ShellHookSpec,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        """执行 Shell 脚本"""
        serialized = json.dumps(payload, ensure_ascii=False, default=str)

        try:
            process = subprocess.Popen(
                ["bash", "-c", spec.command],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=spec.timeout,
            )

            stdout, stderr = process.communicate(input=serialized, timeout=spec.timeout)

            if stderr:
                logger.warning(f"Hook stderr: {stderr[:200]}")

            if not stdout or not stdout.strip():
                return None

            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                logger.warning(f"Hook output is not valid JSON: {stdout[:200]}")
                return None

        except subprocess.TimeoutExpired:
            logger.error(f"Hook timed out after {spec.timeout}s")
            return None
        except Exception as exc:
            logger.error(f"Hook execution error: {exc}")
            return None

    def list_hooks(self) -> dict[str, list[ShellHookSpec]]:
        """列出所有注册的钩子"""
        with self._lock:
            return dict(self._hooks)


_hooks_instance: ShellHookRunner | None = None
_hooks_lock = threading.Lock()


def get_hook_runner() -> ShellHookRunner:
    """获取全局钩子运行器实例"""
    global _hooks_instance
    with _hooks_lock:
        if _hooks_instance is None:
            _hooks_instance = ShellHookRunner()
        return _hooks_instance


def get_shell_hooks() -> ShellHookRunner:
    """获取全局钩子运行器实例 (兼容旧 API)"""
    return get_hook_runner()


def register_shell_hooks(config: dict[str, Any]) -> list[ShellHookSpec]:
    """从配置注册 Shell 钩子

    配置格式：
    ```yaml
    hooks:
      pre_tool_call:
        - command: "/path/to/script.sh"
          matcher: "terminal"
          timeout: 30
    ```
    """
    runner = get_hook_runner()
    registered = []

    hooks_cfg = config.get("hooks")
    if not isinstance(hooks_cfg, dict):
        return []

    for event_name, entries in hooks_cfg.items():
        if not isinstance(entries, list):
            continue

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            command = entry.get("command")
            if not command:
                continue

            spec = ShellHookSpec(
                event=event_name,
                command=command,
                matcher=entry.get("matcher"),
                timeout=int(entry.get("timeout", DEFAULT_TIMEOUT_SECONDS)),
            )

            if runner.register(spec):
                registered.append(spec)
                logger.info(f"Shell hook registered: {event_name} -> {command}")

    return registered
