"""Prometheus tool call parser."""

import json
import re
import uuid

from environments.tool_call_parsers import ParseResult, ToolCallParser, register_parser
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)


@register_parser("prometheus")
class PrometheusToolCallParser(ToolCallParser):
    PATTERN = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>|<tool_call>\s*(.*)", re.DOTALL)

    def parse(self, text: str) -> ParseResult:
        if "<tool_call>" not in text:
            return text, None

        try:
            matches = self.PATTERN.findall(text)
            if not matches:
                return text, None

            tool_calls: list[ChatCompletionMessageToolCall] = []
            for match in matches:
                raw_json = match[0] if match[0] else match[1]
                if not raw_json.strip():
                    continue

                tc_data = json.loads(raw_json)
                if "name" not in tc_data:
                    continue
                tool_calls.append(
                    ChatCompletionMessageToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        type="function",
                        function=Function(
                            name=tc_data["name"],
                            arguments=json.dumps(tc_data.get("arguments", {}), ensure_ascii=False),
                        ),
                    )
                )

            if not tool_calls:
                return text, None

            content = text[: text.find("<tool_call>")].strip()
            return content if content else None, tool_calls

        except Exception:
            return text, None
