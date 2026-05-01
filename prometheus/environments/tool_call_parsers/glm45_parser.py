"""GLM 4.5 (GLM-4-MoE) tool call parser."""

import ast
import json
import re
import uuid
from typing import Any

from environments.tool_call_parsers import ParseResult, ToolCallParser, register_parser
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)


def _deserialize_value(value: str) -> Any:
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        pass

    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError, TypeError):
        pass

    return value


@register_parser("glm45")
class Glm45ToolCallParser(ToolCallParser):
    FUNC_CALL_REGEX = re.compile(r"<tool_call>.*?</tool_call>", re.DOTALL)
    FUNC_DETAIL_REGEX = re.compile(r"<tool_call>([^\n]*)\n(.*)</tool_call>", re.DOTALL)
    FUNC_ARG_REGEX = re.compile(
        r"<arg_key>(.*?)</arg_key>\s*<arg_value>(.*?)</arg_value>", re.DOTALL
    )

    START_TOKEN = "<tool_call>"

    def parse(self, text: str) -> ParseResult:
        if self.START_TOKEN not in text:
            return text, None

        try:
            matched_calls = self.FUNC_CALL_REGEX.findall(text)
            if not matched_calls:
                return text, None

            tool_calls: list[ChatCompletionMessageToolCall] = []

            for match in matched_calls:
                detail = self.FUNC_DETAIL_REGEX.search(match)
                if not detail:
                    continue

                func_name = detail.group(1).strip()
                func_args_raw = detail.group(2)

                pairs = self.FUNC_ARG_REGEX.findall(func_args_raw) if func_args_raw else []
                arg_dict: dict[str, Any] = {}
                for key, value in pairs:
                    arg_key = key.strip()
                    arg_val = _deserialize_value(value.strip())
                    arg_dict[arg_key] = arg_val

                tool_calls.append(
                    ChatCompletionMessageToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        type="function",
                        function=Function(
                            name=func_name,
                            arguments=json.dumps(arg_dict, ensure_ascii=False),
                        ),
                    )
                )

            if not tool_calls:
                return text, None

            content = text[: text.find(self.START_TOKEN)].strip()
            return content if content else None, tool_calls

        except Exception:
            return text, None
