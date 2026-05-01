"""Llama 3.x / 4 tool call parser."""

import json
import re
import uuid

from environments.tool_call_parsers import ParseResult, ToolCallParser, register_parser
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)


@register_parser("llama3_json")
@register_parser("llama4_json")
class LlamaToolCallParser(ToolCallParser):
    BOT_TOKEN = "<|python_tag|>"
    JSON_START = re.compile(r"\{")

    def parse(self, text: str) -> ParseResult:
        if self.BOT_TOKEN not in text and "{" not in text:
            return text, None

        try:
            decoder = json.JSONDecoder()
            tool_calls: list[ChatCompletionMessageToolCall] = []
            end_index = -1

            for match in self.JSON_START.finditer(text):
                start = match.start()
                if start <= end_index:
                    continue

                try:
                    obj, json_end = decoder.raw_decode(text[start:])
                    end_index = start + json_end

                    name = obj.get("name")
                    args = obj.get("arguments", obj.get("parameters"))

                    if not name or args is None:
                        continue

                    if isinstance(args, dict) or not isinstance(args, str):
                        args = json.dumps(args, ensure_ascii=False)

                    tool_calls.append(
                        ChatCompletionMessageToolCall(
                            id=f"call_{uuid.uuid4().hex[:8]}",
                            type="function",
                            function=Function(name=name, arguments=args),
                        )
                    )
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

            if not tool_calls:
                return text, None

            first_tc_start = text.find("{")
            if self.BOT_TOKEN in text:
                first_tc_start = text.find(self.BOT_TOKEN)
            content = text[:first_tc_start].strip() if first_tc_start > 0 else None

            return content, tool_calls

        except Exception:
            return text, None
