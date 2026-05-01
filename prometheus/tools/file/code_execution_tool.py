"""代码执行工具 - CodeExecutionTool."""

from __future__ import annotations

import logging
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """执行结果"""

    success: bool
    output: str
    error: str | None = None
    exit_code: int = 0
    execution_time: float = 0.0


class CodeExecutionTool:
    """代码执行工具"""

    SUPPORTED_LANGUAGES = {
        "python": ["python3", "python"],
        "javascript": ["node", "nodejs"],
        "bash": ["bash", "sh"],
        "shell": ["bash", "sh"],
    }

    def __init__(self, timeout: int = 60, max_output_size: int = 10000):
        self.timeout = timeout
        self.max_output_size = max_output_size
        self._execution_count = 0

    def execute(
        self,
        code: str,
        language: str = "python",
        cleanup: bool = True,
    ) -> ExecutionResult:
        """执行代码

        Args:
            code: 要执行的代码
            language: 编程语言 (python/javascript/bash)
            cleanup: 是否清理临时文件

        Returns:
            ExecutionResult 对象
        """
        import time

        start_time = time.time()

        self._execution_count += 1

        normalized_lang = language.lower().strip()
        if normalized_lang not in self.SUPPORTED_LANGUAGES:
            return ExecutionResult(
                success=False,
                output="",
                error=f"Unsupported language: {language}. Supported: {list(self.SUPPORTED_LANGUAGES.keys())}",
            )

        executors = self.SUPPORTED_LANGUAGES[normalized_lang]
        executor = self._find_executor(executors)
        if not executor:
            return ExecutionResult(
                success=False,
                output="",
                error=f"No executor found for {language}. Please install: {', '.join(executors)}",
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            script_path = self._create_script(tmpdir_path, code, normalized_lang)

            if not script_path:
                return ExecutionResult(
                    success=False,
                    output="",
                    error="Failed to create temporary script file",
                )

            try:
                result = subprocess.run(
                    [executor, str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=tmpdir_path,
                )

                execution_time = time.time() - start_time

                output = result.stdout + result.stderr
                if len(output) > self.max_output_size:
                    output = (
                        output[: self.max_output_size]
                        + f"\n... (output truncated, total {len(output)} chars)"
                    )

                return ExecutionResult(
                    success=result.returncode == 0,
                    output=output,
                    error=result.stderr if result.returncode != 0 else None,
                    exit_code=result.returncode,
                    execution_time=execution_time,
                )

            except subprocess.TimeoutExpired:
                return ExecutionResult(
                    success=False,
                    output="",
                    error=f"Execution timed out after {self.timeout} seconds",
                    exit_code=-1,
                    execution_time=time.time() - start_time,
                )
            except Exception as e:
                return ExecutionResult(
                    success=False,
                    output="",
                    error=str(e),
                    exit_code=-1,
                    execution_time=time.time() - start_time,
                )

    def _find_executor(self, executors: list[str]) -> str | None:
        """查找可用的执行器"""
        for executor in executors:
            try:
                result = subprocess.run(
                    [executor, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    return executor
            except Exception:
                continue
        return None

    def _create_script(self, tmpdir: Path, code: str, language: str) -> Path | None:
        """创建临时脚本文件"""
        try:
            if language == "python":
                ext = ".py"
            elif language in ("javascript", "node"):
                ext = ".js"
            elif language in ("bash", "shell"):
                ext = ".sh"
            else:
                ext = ".txt"

            script_path = tmpdir / f"script_{uuid.uuid4().hex[:8]}{ext}"
            script_path.write_text(code, encoding="utf-8")

            if language in ("bash", "shell"):
                script_path.chmod(0o755)

            return script_path

        except Exception as e:
            logger.error(f"Failed to create script: {e}")
            return None

    @property
    def execution_count(self) -> int:
        """获取执行次数"""
        return self._execution_count


def execute_python(code: str, **kwargs) -> ExecutionResult:
    """快捷函数：执行 Python 代码"""
    tool = CodeExecutionTool()
    return tool.execute(code, language="python", **kwargs)


def execute_javascript(code: str, **kwargs) -> ExecutionResult:
    """快捷函数：执行 JavaScript 代码"""
    tool = CodeExecutionTool()
    return tool.execute(code, language="javascript", **kwargs)


def execute_bash(code: str, **kwargs) -> ExecutionResult:
    """快捷函数：执行 Bash 代码"""
    tool = CodeExecutionTool()
    return tool.execute(code, language="bash", **kwargs)
