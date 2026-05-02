"""Code execution tool registration."""
from __future__ import annotations

import json
from prometheus.tools.file.code_execution_tool import CodeExecutionTool
from prometheus.tools.security.registry import registry

_CODE_TOOL = CodeExecutionTool()

EXECUTE_CODE_SCHEMA = {
    "name": "execute_code",
    "description": "Execute code in Python, JavaScript, or Bash. Returns stdout and stderr.",
    "parameters": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The code to execute",
            },
            "language": {
                "type": "string",
                "enum": ["python", "javascript", "bash"],
                "description": "Programming language (default: python)",
            },
        },
        "required": ["code"],
    },
}


def _execute_code_wrapper(code: str, language: str = "python") -> str:
    """Wrapper that returns JSON string."""
    result = _CODE_TOOL.execute(code, language=language)
    return json.dumps({
        "success": result.success,
        "output": result.output,
        "error": result.error,
        "exit_code": result.exit_code,
        "execution_time": result.execution_time,
    }, ensure_ascii=False)


registry.register(
    name="execute_code",
    toolset="file",
    schema=EXECUTE_CODE_SCHEMA,
    handler=_execute_code_wrapper,
    emoji="💻",
    max_result_size_chars=100_000,
)
