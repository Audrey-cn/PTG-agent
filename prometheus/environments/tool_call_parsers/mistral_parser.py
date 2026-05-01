"""Mistral tool call parser."""

import json

from environments.tool_call_parsers import ParseResult, ToolCallParser, register_parser
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)


def _generate_mistral_id() -> str:
    import random
    import string

    return "".join(random.choices(string.ascii_letters + string.digits, k=9))


@register_parser("mistral")
class MistralToolCallParser(ToolCallParser):
    BOT_TOKEN = "[TOOL_CALLS]"

    def parse(self, text: str) -> ParseResult:
        if self.BOT_TOKEN not in text:
            return text, None

        try:
            parts = text.split(self.BOT_TOKEN)
            content = parts[0].strip()
            raw_tool_calls = parts[1:]

            first_raw = raw_tool_calls[0].strip() if raw_tool_calls else ""
            is_pre_v11 = first_raw.startswith("[") or first_raw.startswith("{")

            tool_calls: list[ChatCompletionMessageToolCall] = []

            if not is_pre_v11:
                for raw in raw_tool_calls:
                    raw = raw.strip()
                    if not raw or "{" not in raw:
                        continue

                    brace_idx = raw.find("{")
                    tool_name = raw[:brace_idx].strip()
                    args_str = raw[brace_idx:]

                    try:
                        parsed_args = json.loads(args_str)
                        args_str = json.dumps(parsed_args, ensure_ascii=False)
                    except json.JSONDecodeError:
                        pass

                    tool_calls.append(
                        ChatCompletionMessageToolCall(
                            id=_generate_mistral_id(),
                            type="function",
                            function=Function(name=tool_name, arguments=args_str),
                        )
                    )
            else:
                try:
                    parsed = json.loads(first_raw)
                    if isinstance(parsed, dict):
                        parsed = [parsed]

                    for tc in parsed:
                        if "name" not in tc:
                            continue
                        args = tc.get("arguments", {})
                        if isinstance(args, dict):
                            args = json.dumps(args, ensure_ascii=False)

                        tool_calls.append(
                            ChatCompletionMessageToolCall(
                                id=_generate_mistral_id(),
                                type="function",
                                function=Function(name=tc["name"], arguments=args),
                            )
                        )
                except json.JSONDecodeError:
                    decoder = json.JSONDecoder()
                    idx = 0
                    while idx < len(first_raw):
                        try:
                            obj, end_idx = decoder.raw_decode(first_raw, idx)
                            if isinstance(obj, dict) and "name" in obj:
                                args = obj.get("arguments", {})
                                if isinstance(args, dict):
                                    args = json.dumps(args, ensure_ascii=False)
                                tool_calls.append(
                                    ChatCompletionMessageToolCall(
                                        id=_generate_mistral_id(),
                                        type="function",
                                        function=Function(name=obj["name"], arguments=args),
                                    )
                                )
                            idx = end_idx
                        except json.JSONDecodeError:
                            idx += 1

            if not tool_calls:
                return text, None

            return content if content else None, tool_calls

        except Exception:
            return text, None
