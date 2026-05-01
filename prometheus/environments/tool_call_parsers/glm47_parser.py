"""GLM 4.7 tool call parser."""

import re

from environments.tool_call_parsers import register_parser
from environments.tool_call_parsers.glm45_parser import Glm45ToolCallParser


@register_parser("glm47")
class Glm47ToolCallParser(Glm45ToolCallParser):
    def __init__(self):
        super().__init__()
        self.FUNC_DETAIL_REGEX = re.compile(
            r"<tool_call>(.*?)(<arg_key>.*?)?</tool_call>", re.DOTALL
        )
        self.FUNC_ARG_REGEX = re.compile(
            r"<arg_key>(.*?)</arg_key>(?:\\n|\s)*<arg_value>(.*?)</arg_value>",
            re.DOTALL,
        )
