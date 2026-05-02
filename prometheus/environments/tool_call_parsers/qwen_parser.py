"""Qwen 2.5 tool call parser."""

from environments.tool_call_parsers import register_parser
from environments.tool_call_parsers.prometheus_parser import PrometheusToolCallParser


@register_parser("qwen")
class QwenToolCallParser(PrometheusToolCallParser):
    pass
