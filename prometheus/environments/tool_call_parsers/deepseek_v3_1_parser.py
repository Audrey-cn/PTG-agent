"""DeepSeek V3.1 tool call parser."""

import re
import uuid

from environments.tool_call_parsers import ParseResult, ToolCallParser, register_parser
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)


@register_parser("deepseek_v3_1")
@register_parser("deepseek_v31")
class DeepSeekV31ToolCallParser(ToolCallParser):
    START_TOKEN = "<｜tool▁calls▁begin｜>"

    PATTERN = re.compile(
        r"<｜tool▁call▁begin｜>(?P<function_name>.*?)<｜tool▁sep｜>(?P<function_arguments>.*?)<｜tool▁call▁end｜>",
        re.DOTALL,
    )

    def parse(self, text: str) -> ParseResult:
        if self.START_TOKEN not in text:
            return text, None

        try:
            matches = self.PATTERN.findall(text)
            if not matches:
                return text, None

            tool_calls: list[ChatCompletionMessageToolCall] = []
            for match in matches:
                func_name, func_args = match
                tool_calls.append(
                    ChatCompletionMessageToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        type="function",
                        function=Function(
                            name=func_name.strip(),
                            arguments=func_args.strip(),
                        ),
                    )
                )

            if not tool_calls:
                return text, None

            content = text[: text.find(self.START_TOKEN)].strip()
            return content if content else None, tool_calls

        except Exception:
            return text, None
