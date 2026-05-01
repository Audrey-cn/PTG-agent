"""DeepSeek V3 tool call parser."""

import logging
import re
import uuid

from environments.tool_call_parsers import ParseResult, ToolCallParser, register_parser
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)

logger = logging.getLogger(__name__)


@register_parser("deepseek_v3")
class DeepSeekV3ToolCallParser(ToolCallParser):
    START_TOKEN = "<｜tool▁calls▁begin｜>"

    PATTERN = re.compile(
        r"<｜tool▁call▁begin｜>(?P<type>.*?)<｜tool▁sep｜>(?P<function_name>.*?)\s*```json\s*(?P<function_arguments>.*?)\s*```\s*<｜tool▁call▁end｜>",
        re.DOTALL,
    )

    def parse(self, text: str) -> ParseResult:
        if self.START_TOKEN not in text:
            return text, None

        try:
            matches = list(self.PATTERN.finditer(text))
            if not matches:
                return text, None

            tool_calls: list[ChatCompletionMessageToolCall] = []

            for match in matches:
                func_name = match.group("function_name").strip()
                func_args = match.group("function_arguments").strip()

                tool_calls.append(
                    ChatCompletionMessageToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        type="function",
                        function=Function(
                            name=func_name,
                            arguments=func_args,
                        ),
                    )
                )

            if tool_calls:
                content_index = text.find(self.START_TOKEN)
                content = text[:content_index].strip()
                return content if content else None, tool_calls

            return text, None

        except Exception as e:
            logger.error(f"Error parsing DeepSeek V3 tool calls: {e}")
            return text, None
