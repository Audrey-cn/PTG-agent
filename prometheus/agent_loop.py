#!/usr/bin/env python3
import json
import os
import re
import sys
import threading
import time
import logging
from pathlib import Path
from typing import Any, Optional

from openai import OpenAI

try:
    from .constants import get_prometheus_home, PROMETHEUS_VERSION
    from .tool_registry import ToolRegistry
except ImportError:
    from constants import get_prometheus_home, PROMETHEUS_VERSION
    from tool_registry import ToolRegistry

logger = logging.getLogger("prometheus.agent_loop")

_SURROGATE_RE = re.compile(r'[\ud800-\udfff]')

_DESTRUCTIVE_PATTERNS = re.compile(
    r"""(?:^|\s|&&|\|\||;|`)(?:
        rm\s|rmdir\s|
        cp\s|install\s|
        mv\s|
        sed\s+-i|
        truncate\s|
        dd\s|
        shred\s|
        git\s+(?:reset|clean|checkout)\s
    )""",
    re.VERBOSE,
)

_REDIRECT_OVERWRITE = re.compile(r'[^>]>[^>]|^>[^>]')


def _is_destructive_command(cmd: str) -> bool:
    if not cmd:
        return False
    if _DESTRUCTIVE_PATTERNS.search(cmd):
        return True
    if _REDIRECT_OVERWRITE.search(cmd):
        return True
    return False


def _sanitize_surrogates(text: str) -> str:
    if _SURROGATE_RE.search(text):
        return _SURROGATE_RE.sub('\ufffd', text)
    return text


def _sanitize_messages_surrogates(messages: list) -> bool:
    found = False
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if isinstance(content, str) and _SURROGATE_RE.search(content):
            msg["content"] = _SURROGATE_RE.sub('\ufffd', content)
            found = True
        name = msg.get("name")
        if isinstance(name, str) and _SURROGATE_RE.search(name):
            msg["name"] = _SURROGATE_RE.sub('\ufffd', name)
            found = True
    return found


class IterationBudget:
    def __init__(self, max_total: int):
        self.max_total = max_total
        self._used = 0
        self._lock = threading.Lock()

    def consume(self) -> bool:
        with self._lock:
            if self._used >= self.max_total:
                return False
            self._used += 1
            return True

    def refund(self) -> None:
        with self._lock:
            if self._used > 0:
                self._used -= 1

    @property
    def used(self) -> int:
        return self._used

    @property
    def remaining(self) -> int:
        with self._lock:
            return max(0, self.max_total - self._used)


class AIAgent:
    def __init__(
        self,
        system_prompt: str = "",
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        model: str = "",
        max_iterations: int = 50,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools_config: Optional[dict] = None,
        callback=None,
        agent_config: Optional[dict] = None,
    ):
        self.system_prompt = system_prompt
        self.model = model
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.callback = callback
        self.agent_config = agent_config or {}

        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=300,
            max_retries=2,
        )

        self._budget = IterationBudget(max_iterations)
        self._tools_config = tools_config or {}

    def _get_tool_definitions(self) -> list:
        tools = []
        try:
            from .tools.registry import registry as tool_registry
        except ImportError:
            from tools.registry import registry as tool_registry

        for name, entry in tool_registry._tools.items():
            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": entry.schema.description or entry.description,
                    "parameters": entry.schema.parameters,
                },
            })
        return tools

    def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
        try:
            from .tools.registry import registry as tool_registry
        except ImportError:
            from tools.registry import registry as tool_registry

        entry = tool_registry.get(tool_name)
        if entry is None:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        try:
            result = entry.handler(tool_args)
            if isinstance(result, dict):
                return json.dumps(result, ensure_ascii=False)
            return str(result)
        except Exception as e:
            logger.warning("Tool %s failed: %s", tool_name, e)
            return json.dumps({"error": str(e)})

    def run_conversation(
        self,
        user_message: str,
        history: Optional[list] = None,
        context: Optional[dict] = None,
    ) -> dict:
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})

        _sanitize_messages_surrogates(messages)

        tool_defs = self._get_tool_definitions()

        iteration = 0
        while self._budget.consume():
            iteration += 1
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                }
                if tool_defs:
                    kwargs["tools"] = tool_defs

                response = self._client.chat.completions.create(**kwargs)

                choice = response.choices[0]
                msg = choice.message

                if msg.tool_calls:
                    messages.append({
                        "role": "assistant",
                        "content": msg.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in msg.tool_calls
                        ],
                    })

                    for tc in msg.tool_calls:
                        tool_name = tc.function.name
                        try:
                            tool_args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            tool_args = {}

                        if self.callback:
                            self.callback("tool_start", {
                                "tool": tool_name,
                                "args": tool_args,
                            })

                        tool_result = self._execute_tool(tool_name, tool_args)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": tool_result,
                        })

                        if self.callback:
                            self.callback("tool_end", {
                                "tool": tool_name,
                                "result": tool_result,
                            })
                else:
                    text = msg.content or ""
                    cost = {
                        "in_tokens": response.usage.prompt_tokens if response.usage else 0,
                        "out_tokens": response.usage.completion_tokens if response.usage else 0,
                    }
                    return {
                        "text": text,
                        "iterations": iteration,
                        "tool_calls_made": iteration - 1,
                        "cost": cost,
                    }

            except Exception as e:
                logger.error("Agent iteration %d failed: %s", iteration, e)
                if iteration <= 1:
                    raise
                return {
                    "text": f"Error after {iteration} iterations: {e}",
                    "iterations": iteration,
                    "error": str(e),
                }

        return {
            "text": f"Max iterations ({self.max_iterations}) reached without final answer.",
            "iterations": iteration,
            "tool_calls_made": iteration - 1,
        }


def create_agent_from_config(cfg: dict) -> AIAgent:
    api = cfg.get("api", {})
    model_cfg = cfg.get("model", {})
    agent_cfg = cfg.get("agent", {})

    return AIAgent(
        system_prompt=agent_cfg.get("system_prompt", ""),
        api_key=api.get("key", os.getenv("OPENAI_API_KEY", "")),
        base_url=api.get("base_url", "https://api.openai.com/v1"),
        model=model_cfg.get("name", ""),
        max_iterations=agent_cfg.get("max_iterations", 50),
        max_tokens=model_cfg.get("max_tokens", 4096),
        temperature=model_cfg.get("temperature", 0.7),
    )
