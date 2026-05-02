"""Tool Call Parser Registry."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Type

from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
)

logger = logging.getLogger(__name__)

ParseResult = tuple[str | None, list[ChatCompletionMessageToolCall] | None]


class ToolCallParser(ABC):
    @abstractmethod
    def parse(self, text: str) -> ParseResult:
        raise NotImplementedError


PARSER_REGISTRY: dict[str, type[ToolCallParser]] = {}


def register_parser(name: str):
    def decorator(cls: type[ToolCallParser]) -> type[ToolCallParser]:
        PARSER_REGISTRY[name] = cls
        return cls

    return decorator


def get_parser(name: str) -> ToolCallParser:
    if name not in PARSER_REGISTRY:
        available = sorted(PARSER_REGISTRY.keys())
        raise KeyError(f"Tool call parser '{name}' not found. Available parsers: {available}")
    return PARSER_REGISTRY[name]()


def list_parsers() -> list[str]:
    return sorted(PARSER_REGISTRY.keys())


from environments.tool_call_parsers.deepseek_v3_1_parser import (
    DeepSeekV31ToolCallParser,  # noqa: F401
)
from environments.tool_call_parsers.deepseek_v3_parser import (
    DeepSeekV3ToolCallParser,  # noqa: F401
)
from environments.tool_call_parsers.glm45_parser import Glm45ToolCallParser  # noqa: E402, F401
from environments.tool_call_parsers.glm47_parser import Glm47ToolCallParser  # noqa: E402, F401
from environments.tool_call_parsers.prometheus_parser import PrometheusToolCallParser  # noqa: E402, F401
from environments.tool_call_parsers.kimi_k2_parser import KimiK2ToolCallParser  # noqa: E402, F401
from environments.tool_call_parsers.llama_parser import LlamaToolCallParser  # noqa: E402, F401
from environments.tool_call_parsers.longcat_parser import LongcatToolCallParser  # noqa: E402, F401
from environments.tool_call_parsers.mistral_parser import MistralToolCallParser  # noqa: E402, F401
from environments.tool_call_parsers.qwen3_coder_parser import (
    Qwen3CoderToolCallParser,  # noqa: F401
)
from environments.tool_call_parsers.qwen_parser import QwenToolCallParser  # noqa: E402, F401
