#!/usr/bin/env python3
"""Prometheus AIAgent - 完整 Agent 循环实现."""

import json
import logging
import os
import re
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    from .context_compressor import CompressionStrategy, ContextCompressor
    from .memory_system import get_soul_path
    from .tools.registry import registry, tool_error, tool_result
except ImportError:
    from context_compressor import CompressionStrategy, ContextCompressor
    from memory_system import get_soul_path

    from prometheus.tools.registry import registry

logger = logging.getLogger("prometheus.agent")

SURROGATE_RE = re.compile(r"[\ud800-\udfff]")

DESTRUCTIVE_PATTERNS = re.compile(
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

REDIRECT_OVERWRITE = re.compile(r"[^>]>[^>]|^>[^>]")

REASONING_TAGS = (
    "REASONING_SCRATCHPAD",
    "think",
    "thinking",
    "reasoning",
    "thought",
)


def _sanitize_surrogates(text: str) -> str:
    if SURROGATE_RE.search(text):
        return SURROGATE_RE.sub("\ufffd", text)
    return text


def _strip_reasoning_tags(text: str) -> str:
    """移除 reasoning/thinking 块"""
    cleaned = text
    for tag in REASONING_TAGS:
        cleaned = re.sub(
            rf"<{tag}>.*?</{tag}>\s*",
            "",
            cleaned,
            flags=re.DOTALL | re.IGNORECASE,
        )
        cleaned = re.sub(
            rf"<{tag}>.*$",
            "",
            cleaned,
            flags=re.DOTALL | re.IGNORECASE,
        )
        cleaned = re.sub(
            rf"</{tag}>\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
    return cleaned.strip()


def _is_destructive_command(cmd: str) -> bool:
    if not cmd:
        return False
    if DESTRUCTIVE_PATTERNS.search(cmd):
        return True
    return bool(REDIRECT_OVERWRITE.search(cmd))


@dataclass
class IterationBudget:
    max_total: int = 90
    _used: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

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
    def remaining(self) -> int:
        with self._lock:
            return max(0, self.max_total - self._used)

    @property
    def used(self) -> int:
        return self._used


@dataclass
class AgentConfig:
    model: str = ""
    provider: str = "openai"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    max_iterations: int = 90
    max_tokens: int = 8192
    temperature: float = 0.7
    timeout: int = 300
    enabled_toolsets: list = None
    disabled_toolsets: list = None
    quiet_mode: bool = False
    save_trajectories: bool = False
    session_id: str = None
    skip_context_files: bool = False
    skip_memory: bool = False


@dataclass
class ToolCallResult:
    tool_name: str
    tool_args: dict
    result: str
    success: bool
    error: str | None = None
    duration_ms: float = 0


@dataclass
class AgentResponse:
    content: str
    reasoning: str | None = None
    tool_calls: list = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict = field(default_factory=dict)
    session_id: str = ""


class TransportFactory:
    """Transport 工厂 - 支持多种 Provider"""

    @staticmethod
    def create(provider: str, api_key: str = "", base_url: str = "", **kwargs):
        if provider in ("openai", "azure", "兼容"):
            return OpenAICompatTransport(api_key=api_key, base_url=base_url, **kwargs)
        elif provider == "anthropic":
            return AnthropicTransport(api_key=api_key, **kwargs)
        elif provider == "gemini":
            return GeminiTransport(api_key=api_key, **kwargs)
        else:
            return OpenAICompatTransport(api_key=api_key, base_url=base_url, **kwargs)


class OpenAICompatTransport:
    """OpenAI 兼容 Transport"""

    def __init__(self, api_key: str = "", base_url: str = "", **kwargs):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url or "https://api.openai.com/v1"
        self._client = None
        self._init_client()

    def _init_client(self):
        try:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=300,
                max_retries=2,
            )
        except ImportError:
            logger.warning("OpenAI SDK not installed")

    def create_completion(
        self,
        messages: list,
        model: str,
        tools: list = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        **kwargs,
    ) -> dict:
        if self._client is None:
            self._init_client()
        if self._client is None:
            raise RuntimeError("OpenAI client not initialized")

        params = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        response = self._client.chat.completions.create(**params)
        return self._parse_response(response)

    def _parse_response(self, response) -> dict:
        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            result = {
                "content": choice.message.content or "",
                "finish_reason": choice.finish_reason,
                "tool_calls": [],
            }
            if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    result["tool_calls"].append(
                        {
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    )
            if hasattr(response, "usage") and response.usage:
                result["usage"] = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            return result
        return {"content": "", "finish_reason": "stop", "tool_calls": []}


class AnthropicTransport:
    """Anthropic Transport"""

    def __init__(self, api_key: str = "", **kwargs):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    def create_completion(
        self,
        messages: list,
        model: str,
        tools: list = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        **kwargs,
    ) -> dict:
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("Anthropic SDK not installed")

        client = anthropic.Anthropic(api_key=self.api_key)
        params = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            params["tools"] = tools

        response = client.messages.create(**params)
        return self._parse_response(response)

    def _parse_response(self, response) -> dict:
        result = {
            "content": response.content[0].text if response.content else "",
            "finish_reason": response.stop_reason,
            "tool_calls": [],
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
            },
        }
        if hasattr(response.content[0], "tool_calls"):
            for tc in response.content[0].tool_calls:
                result["tool_calls"].append(
                    {
                        "id": tc.id,
                        "name": tc.name,
                        "arguments": json.dumps(tc.input),
                    }
                )
        return result


class GeminiTransport:
    """Google Gemini Transport"""

    def __init__(self, api_key: str = "", **kwargs):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")

    def create_completion(
        self,
        messages: list,
        model: str,
        tools: list = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        **kwargs,
    ) -> dict:
        try:
            import google.genai as genai
        except ImportError:
            raise RuntimeError("Google GenAI SDK not installed")

        client = genai.Client(api_key=self.api_key)
        contents = []
        for msg in messages:
            if msg["role"] == "user":
                contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
            else:
                contents.append({"role": "model", "parts": [{"text": msg["content"]}]})

        params = {
            "model": model,
            "contents": contents,
            "config": {"max_output_tokens": max_tokens, "temperature": temperature},
        }
        if tools:
            params["config"]["tools"] = tools

        response = client.models.generate_content(**params)
        return self._parse_response(response)

    def _parse_response(self, response) -> dict:
        return {
            "content": response.text or "",
            "finish_reason": "stop",
            "tool_calls": [],
        }


class TrajectoryTracker:
    """轨迹追踪器 - 保存 Agent 运行轨迹"""

    def __init__(self, save_dir: Path | None = None):
        self.save_dir = save_dir or Path.home() / ".prometheus" / "trajectories"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.entries: list = []

    def add_entry(
        self,
        step: int,
        role: str,
        content: str,
        tool_calls: list = None,
        reasoning: str = None,
    ):
        entry = {
            "step": step,
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content[:10000] if content else "",
            "tool_calls": tool_calls or [],
            "reasoning": reasoning,
        }
        self.entries.append(entry)

    def add_tool_result(self, step: int, tool_name: str, result: str, success: bool):
        entry = {
            "step": step,
            "timestamp": datetime.now().isoformat(),
            "type": "tool_result",
            "tool_name": tool_name,
            "result": result[:5000] if result else "",
            "success": success,
        }
        self.entries.append(entry)

    def save(self, session_id: str = None):
        if not session_id:
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.save_dir / f"trajectory_{session_id}.jsonl"
        with open(filepath, "w", encoding="utf-8") as f:
            for entry in self.entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return filepath

    def clear(self):
        self.entries.clear()


class AIAgent:
    """
    Prometheus AIAgent - 完整 Agent 实现

    基于 Hermes run_agent.py 的核心架构，提供：
    - 完整的工具调用循环
    - 多 Provider 支持 (OpenAI/Anthropic/Gemini)
    - 上下文压缩
    - 轨迹追踪
    - 错误恢复
    """

    def __init__(
        self,
        config: AgentConfig | None = None,
        system_prompt: str = "",
        callback: Callable = None,
    ):
        self.config = config or AgentConfig()
        self.system_prompt = system_prompt or self._load_default_system_prompt()
        self.callback = callback

        self._transport = TransportFactory.create(
            self.config.provider,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
        )
        self._budget = IterationBudget(max_total=self.config.max_iterations)
        self._session_id = self.config.session_id or str(uuid.uuid4())[:8]
        self._trajectory = None
        if self.config.save_trajectories:
            self._trajectory = TrajectoryTracker()
        self._compressor = ContextCompressor()
        self._interrupt_requested = False
        self._budget_grace_call = True

    def _load_default_system_prompt(self) -> str:
        soul_path = get_soul_path()
        if soul_path.exists():
            try:
                return soul_path.read_text(encoding="utf-8")
            except Exception:
                pass
        return """You are Prometheus, an AI assistant created by Audrey · 001X.
You are helpful, precise, and follow the user's instructions carefully."""

    def _get_tool_definitions(self) -> list:
        """获取所有可用工具定义"""
        tools = []
        for name, entry in registry._tools.items():
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": entry.schema.description or entry.description,
                        "parameters": entry.schema.parameters,
                    },
                }
            )
        return tools

    def _execute_tool(self, tool_name: str, tool_args: dict) -> ToolCallResult:
        """执行单个工具调用"""
        start_time = time.time()
        entry = registry.get(tool_name)

        if entry is None:
            return ToolCallResult(
                tool_name=tool_name,
                tool_args=tool_args,
                result="",
                success=False,
                error=f"Unknown tool: {tool_name}",
            )

        try:
            result = entry.handler(tool_args)
            duration_ms = (time.time() - start_time) * 1000

            if isinstance(result, dict):
                result_str = json.dumps(result, ensure_ascii=False, indent=2)
            else:
                result_str = str(result)

            return ToolCallResult(
                tool_name=tool_name,
                tool_args=tool_args,
                result=result_str,
                success=True,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return ToolCallResult(
                tool_name=tool_name,
                tool_args=tool_args,
                result="",
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

    def _format_tool_call_message(self, tc: dict, result: ToolCallResult) -> dict:
        """格式化工具调用消息"""
        return {
            "role": "tool",
            "tool_call_id": tc.get("id", f"call_{tc.get('name', 'unknown')}"),
            "name": tc.get("name"),
            "content": result.result if result.success else f"Error: {result.error}",
        }

    def _format_assistant_message(self, response: dict) -> dict:
        """格式化 Assistant 消息"""
        content = response.get("content", "")
        reasoning = None

        for tag in REASONING_TAGS:
            match = re.search(rf"<{tag}>(.*?)</{tag}>", content, re.DOTALL | re.IGNORECASE)
            if match:
                reasoning = match.group(1).strip()
                content = re.sub(
                    rf"<{tag}>.*?</{tag}>", "", content, flags=re.DOTALL | re.IGNORECASE
                ).strip()
                break

        msg = {"role": "assistant", "content": content}

        if response.get("tool_calls"):
            msg["tool_calls"] = response["tool_calls"]

        if reasoning:
            msg["reasoning"] = reasoning

        return msg

    def _should_compress_context(self, messages: list) -> bool:
        """检查是否需要压缩上下文"""
        return self._compressor.should_compress(messages)

    def _compress_if_needed(self, messages: list) -> list:
        """必要时压缩上下文"""
        if self._should_compress_context(messages):
            result = self._compressor.compress(messages, CompressionStrategy.SELECTIVE)
            logger.info(
                f"Compressed {result.original_count} -> {result.compressed_count} messages, "
                f"saved ~{result.tokens_saved} tokens"
            )
            return result.compressed_messages
        return messages

    def _build_messages(self, user_message: str, history: list = None) -> list:
        """构建消息列表"""
        messages = []

        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})

        for msg in messages:
            if isinstance(msg.get("content"), str):
                msg["content"] = _sanitize_surrogates(msg["content"])

        return messages

    def request_interrupt(self):
        """请求中断 Agent 循环"""
        self._interrupt_requested = True

    def chat(self, message: str, history: list = None) -> str:
        """
        简单接口 - 返回最终响应字符串
        """
        result = self.run_conversation(message, history=history)
        return result.content

    def run_conversation(
        self,
        user_message: str,
        system_message: str = None,
        conversation_history: list = None,
        task_id: str = None,
    ) -> AgentResponse:
        """
        完整接口 - 返回包含完整响应的 dict

        Returns:
            AgentResponse: 包含 content, reasoning, tool_calls, finish_reason 等
        """
        messages = self._build_messages(user_message, conversation_history)

        if system_message:
            messages.insert(1, {"role": "system", "content": system_message})

        api_call_count = 0
        iteration = 0
        tool_defs = self._get_tool_definitions()

        while (
            api_call_count < self.config.max_iterations and self._budget.remaining > 0
        ) or self._budget_grace_call:
            if self._interrupt_requested:
                logger.info("Interrupt requested, stopping loop")
                break

            iteration += 1

            try:
                response = self._transport.create_completion(
                    messages=messages,
                    model=self.config.model,
                    tools=tool_defs if tool_defs else None,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                )
            except Exception as e:
                logger.error(f"API call failed: {e}")
                return AgentResponse(
                    content=f"API call failed: {e}",
                    finish_reason="error",
                    session_id=self._session_id,
                )

            assistant_msg = self._format_assistant_message(response)
            messages.append(assistant_msg)

            if self._trajectory:
                self._trajectory.add_entry(
                    step=iteration,
                    role="assistant",
                    content=response.get("content", ""),
                    tool_calls=response.get("tool_calls", []),
                    reasoning=assistant_msg.get("reasoning"),
                )

            if self.callback:
                try:
                    self.callback(assistant_msg)
                except Exception as e:
                    logger.warning(f"Callback failed: {e}")

            if not response.get("tool_calls"):
                if self._trajectory:
                    self._trajectory.save(self._session_id)
                return AgentResponse(
                    content=response.get("content", ""),
                    finish_reason=response.get("finish_reason", "stop"),
                    usage=response.get("usage", {}),
                    session_id=self._session_id,
                )

            for tc in response["tool_calls"]:
                tc_name = tc.get("name", "")
                tc_args = {}
                try:
                    tc_args = json.loads(tc.get("arguments", "{}"))
                except json.JSONDecodeError:
                    tc_args = {"raw": tc.get("arguments", "")}

                result = self._execute_tool(tc_name, tc_args)
                tool_msg = self._format_tool_call_message(tc, result)
                messages.append(tool_msg)

                if self._trajectory:
                    self._trajectory.add_tool_result(
                        step=iteration,
                        tool_name=tc_name,
                        result=result.result,
                        success=result.success,
                    )

                api_call_count += 1

                if self.callback:
                    try:
                        self.callback(tool_msg)
                    except Exception as e:
                        logger.warning(f"Callback failed: {e}")

            if self._should_compress_context(messages):
                messages = self._compress_if_needed(messages)

        if self._trajectory:
            self._trajectory.save(self._session_id)

        final_content = messages[-1].get("content", "") if messages else ""
        return AgentResponse(
            content=final_content,
            finish_reason="max_iterations" if self._budget.remaining <= 0 else "stop",
            usage={},
            session_id=self._session_id,
        )

    def get_trajectory_path(self) -> Path | None:
        """获取轨迹文件路径"""
        if self._trajectory:
            return self._trajectory.save(self._session_id)
        return None


def create_agent(
    model: str = "",
    provider: str = "openai",
    api_key: str = "",
    base_url: str = "",
    max_iterations: int = 90,
    system_prompt: str = "",
    save_trajectories: bool = False,
    **kwargs,
) -> AIAgent:
    """创建 Agent 实例的便捷函数"""
    config = AgentConfig(
        model=model or os.environ.get("OPENAI_MODEL", "gpt-4"),
        provider=provider,
        api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
        base_url=base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        max_iterations=max_iterations,
        save_trajectories=save_trajectories,
        **kwargs,
    )
    return AIAgent(config=config, system_prompt=system_prompt)
