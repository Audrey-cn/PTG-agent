"""Qwen 2.5 tool call parser."""

from environments.tool_call_parsers import register_parser
from environments.tool_call_parsers.hermes_parser import HermesToolCallParser


@register_parser("qwen")
class QwenToolCallParser(HermesToolCallParser):
    pass
