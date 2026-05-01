"""ToolContext -- Unrestricted Tool Access for Reward Functions."""

import asyncio
import concurrent.futures
import json
import logging
import os
from typing import Any

from model_tools import handle_function_call

from prometheus.tools.browser_tool import cleanup_browser
from prometheus.tools.terminal_tool import cleanup_vm

logger = logging.getLogger(__name__)

_tool_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _run_tool_in_thread(tool_name: str, arguments: dict[str, Any], task_id: str) -> str:
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(handle_function_call, tool_name, arguments, task_id)
            return future.result(timeout=300)
    except RuntimeError:
        return handle_function_call(tool_name, arguments, task_id)


class ToolContext:
    def __init__(self, task_id: str):
        self.task_id = task_id

    def terminal(self, command: str, timeout: int = 180) -> dict[str, Any]:
        import os

        backend = os.getenv("TERMINAL_ENV", "local")
        logger.debug(
            "ToolContext.terminal [%s backend] task=%s: %s",
            backend,
            self.task_id[:8],
            command[:100],
        )

        result = _run_tool_in_thread(
            "terminal",
            {"command": command, "timeout": timeout},
            self.task_id,
        )
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"exit_code": -1, "output": result}

    def read_file(self, path: str) -> dict[str, Any]:
        result = handle_function_call("read_file", {"path": path}, task_id=self.task_id)
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"error": result}

    def write_file(self, path: str, content: str) -> dict[str, Any]:
        result = handle_function_call(
            "write_file", {"path": path, "content": content}, task_id=self.task_id
        )
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"error": result}

    def upload_file(self, local_path: str, remote_path: str) -> dict[str, Any]:
        import base64
        from pathlib import Path as _Path

        local = _Path(local_path)
        if not local.exists():
            return {"exit_code": -1, "output": f"Local file not found: {local_path}"}

        raw = local.read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")

        parent = str(_Path(remote_path).parent)
        if parent not in (".", "/"):
            self.terminal(f"mkdir -p {parent}", timeout=10)

        chunk_size = 60_000
        if len(b64) <= chunk_size:
            result = self.terminal(
                f"printf '%s' '{b64}' | base64 -d > {remote_path}",
                timeout=30,
            )
        else:
            tmp_b64 = "/tmp/_prometheus_upload.b64"
            self.terminal(f": > {tmp_b64}", timeout=5)
            for i in range(0, len(b64), chunk_size):
                chunk = b64[i : i + chunk_size]
                self.terminal(f"printf '%s' '{chunk}' >> {tmp_b64}", timeout=15)
            result = self.terminal(
                f"base64 -d {tmp_b64} > {remote_path} && rm -f {tmp_b64}",
                timeout=30,
            )

        return result

    def upload_dir(self, local_dir: str, remote_dir: str) -> list[dict[str, Any]]:
        from pathlib import Path as _Path

        local = _Path(local_dir)
        if not local.exists() or not local.is_dir():
            return [{"exit_code": -1, "output": f"Local directory not found: {local_dir}"}]

        results = []
        for file_path in sorted(local.rglob("*")):
            if file_path.is_file():
                relative = file_path.relative_to(local)
                target = f"{remote_dir}/{relative}"
                results.append(self.upload_file(str(file_path), target))
        return results

    def download_file(self, remote_path: str, local_path: str) -> dict[str, Any]:
        import base64
        from pathlib import Path as _Path

        result = self.terminal(
            f"base64 {remote_path} 2>/dev/null",
            timeout=30,
        )

        if result.get("exit_code", -1) != 0:
            return {
                "success": False,
                "error": f"Failed to read remote file: {result.get('output', '')}",
            }

        b64_data = result.get("output", "").strip()
        if not b64_data:
            return {"success": False, "error": f"Remote file is empty or missing: {remote_path}"}

        try:
            raw = base64.b64decode(b64_data)
        except Exception as e:
            return {"success": False, "error": f"Base64 decode failed: {e}"}

        local = _Path(local_path)
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(raw)

        return {"success": True, "bytes": len(raw)}

    def download_dir(self, remote_dir: str, local_dir: str) -> list[dict[str, Any]]:
        from pathlib import Path as _Path

        ls_result = self.terminal(
            f"find {remote_dir} -type f 2>/dev/null",
            timeout=15,
        )

        if ls_result.get("exit_code", -1) != 0:
            return [{"success": False, "error": f"Failed to list remote dir: {remote_dir}"}]

        file_list = ls_result.get("output", "").strip()
        if not file_list:
            return [
                {"success": False, "error": f"Remote directory is empty or missing: {remote_dir}"}
            ]

        results = []
        for remote_file in file_list.splitlines():
            remote_file = remote_file.strip()
            if not remote_file:
                continue
            if remote_file.startswith(remote_dir):
                relative = remote_file[len(remote_dir) :].lstrip("/")
            else:
                relative = _Path(remote_file).name
            local_file = str(_Path(local_dir) / relative)
            results.append(self.download_file(remote_file, local_file))

        return results

    def search(self, query: str, path: str = ".") -> dict[str, Any]:
        result = handle_function_call(
            "search_files", {"pattern": query, "path": path}, task_id=self.task_id
        )
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"error": result}

    def web_search(self, query: str) -> dict[str, Any]:
        result = handle_function_call("web_search", {"query": query})
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"error": result}

    def web_extract(self, urls: list[str]) -> dict[str, Any]:
        result = handle_function_call("web_extract", {"urls": urls})
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"error": result}

    def browser_navigate(self, url: str) -> dict[str, Any]:
        result = handle_function_call("browser_navigate", {"url": url}, task_id=self.task_id)
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"error": result}

    def browser_snapshot(self) -> dict[str, Any]:
        result = handle_function_call("browser_snapshot", {}, task_id=self.task_id)
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"error": result}

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        return _run_tool_in_thread(tool_name, arguments, self.task_id)

    def cleanup(self):
        try:
            from prometheus.tools.process_registry import process_registry

            killed = process_registry.kill_all(task_id=self.task_id)
            if killed:
                logger.debug(
                    "Process cleanup for task %s: killed %d process(es)", self.task_id, killed
                )
        except Exception as e:
            logger.debug("Process cleanup for task %s: %s", self.task_id, e)

        try:
            cleanup_vm(self.task_id)
        except Exception as e:
            logger.debug("VM cleanup for task %s: %s", self.task_id, e)

        _prev_quiet = os.environ.get("PROMETHEUS_QUIET")
        os.environ["PROMETHEUS_QUIET"] = "1"
        try:
            cleanup_browser(self.task_id)
        except Exception as e:
            logger.debug("Browser cleanup for task %s: %s", self.task_id, e)
        finally:
            if _prev_quiet is None:
                os.environ.pop("PROMETHEUS_QUIET", None)
            else:
                os.environ["PROMETHEUS_QUIET"] = _prev_quiet
