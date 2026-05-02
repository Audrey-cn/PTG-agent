from __future__ import annotations

import contextlib
import json
import logging
import os
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

logger = logging.getLogger("prometheus.copilot_acp_client")


class CopilotAuthenticationError(Exception):
    pass


class CopilotPermissionError(Exception):
    pass


class CopilotRateLimitError(Exception):
    pass


@dataclass
class ToolCallResult:
    tool_name: str
    arguments: dict[str, Any]
    output: str
    error: str | None = None


@dataclass
class CopilotToken:
    value: str
    expires_at: float = 0.0
    refresh_token: str | None = None

    def is_valid(self) -> bool:
        if self.expires_at <= 0:
            return True
        return time.time() < self.expires_at


@dataclass
class FileReadRequest:
    path: str
    offset: int = 0
    length: int | None = None


@dataclass
class FileWriteRequest:
    path: str
    content: str
    offset: int | None = None


class CopilotACPClient:
    """GitHub Copilot ACP (Agent Communication Protocol) client.

    This implementation mirrors the Prometheus copilot_acp_client by:
    1. Running the copilot CLI as a subprocess
    2. Using JSON-RPC protocol over stdin/stdout
    3. Handling file system operations with permission checks
    4. Managing sessions and extracting tool calls from responses
    """

    def __init__(
        self,
        github_token: str | None = None,
        timeout: int = 60,
        max_retries: int = 3,
    ) -> None:
        self._token = github_token
        self._timeout = timeout
        self._max_retries = max_retries
        self._authenticated = False
        self._session_id: str | None = None
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._request_id = 0
        self._pending_requests: dict[int, threading.Event] = {}
        self._responses: dict[int, Any] = {}
        self._read_thread: threading.Thread | None = None
        self._allowed_directories: list[str] = []
        self._denied_directories: list[str] = []

    def authenticate(self, token: str | None = None) -> bool:
        """Authenticate with GitHub Copilot.

        Args:
            token: GitHub personal access token with copilot scope

        Returns:
            True if authentication successful
        """
        if token:
            self._token = token

        if not self._token:
            logger.error("No GitHub token provided for Copilot authentication")
            return False

        try:
            result = self._execute_copilot(["auth", "status", "--json"], check=True)
            if result.get("status") == "authenticated":
                self._authenticated = True
                logger.info("Successfully authenticated with GitHub Copilot")
                return True
            else:
                result = self._execute_copilot(
                    ["auth", "login", "--token", self._token], check=False
                )
                self._authenticated = result.get("status") == "authenticated"
                return self._authenticated
        except Exception as e:
            logger.error(f"Copilot authentication failed: {e}")
            self._authenticated = False
            return False

    def _ensure_process(self) -> subprocess.Popen:
        """Ensure the copilot CLI process is running."""
        if self._process is not None and self._process.poll() is None:
            return self._process

        self._start_process()
        return self._process

    def _start_process(self) -> None:
        """Start the copilot CLI subprocess."""
        if self._process is not None:
            self._process.terminate()
            self._process.wait(timeout=5)

        env = os.environ.copy()
        if self._token:
            env["GITHUB_TOKEN"] = self._token

        try:
            self._process = subprocess.Popen(
                ["copilot", "agent", "stream"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=1,
            )
            self._read_thread = threading.Thread(target=self._read_responses, daemon=True)
            self._read_thread.start()
            logger.info("Started copilot CLI subprocess")
        except FileNotFoundError:
            raise CopilotAuthenticationError(
                "Copilot CLI not found. Install with: npm install -g @githubnext/github-copilot"
            )

    def _read_responses(self) -> None:
        """Read responses from the copilot subprocess."""
        if self._process is None or self._process.stdout is None:
            return

        buffer = ""
        while True:
            try:
                char = self._process.stdout.read(1)
                if not char:
                    break
                buffer += char
                if char == "\n":
                    try:
                        response = json.loads(buffer)
                        self._handle_response(response)
                        buffer = ""
                    except json.JSONDecodeError:
                        buffer = ""
            except Exception as e:
                logger.error(f"Error reading copilot response: {e}")
                break

    def _handle_response(self, response: dict[str, Any]) -> None:
        """Handle a response from the copilot subprocess."""
        request_id = response.get("id")
        if request_id in self._pending_requests:
            self._responses[request_id] = response
            self._pending_requests[request_id].set()

    def _send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC request to the copilot subprocess."""
        with self._lock:
            self._request_id += 1
            request_id = self._request_id

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        event = threading.Event()
        self._pending_requests[request_id] = event

        try:
            process = self._ensure_process()
            if process.stdin is None:
                raise CopilotAuthenticationError("Copilot stdin not available")

            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()

            if not event.wait(timeout=self._timeout):
                raise CopilotRateLimitError(f"Request {request_id} timed out")

            response = self._responses.pop(request_id, {})
            if "error" in response:
                error = response["error"]
                raise CopilotAuthenticationError(f"Copilot error: {error}")
            return response.get("result", {})
        finally:
            self._pending_requests.pop(request_id, None)

    def _execute_copilot(
        self, args: list[str], check: bool = True, input_data: str | None = None
    ) -> dict[str, Any]:
        """Execute a copilot CLI command."""
        env = os.environ.copy()
        if self._token:
            env["GITHUB_TOKEN"] = self._token

        try:
            result = subprocess.run(
                ["copilot"] + args,
                capture_output=True,
                text=True,
                env=env,
                input=input_data,
                timeout=self._timeout,
            )

            if result.stdout.strip():
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError:
                    return {"output": result.stdout, "error": None}

            if check and result.returncode != 0:
                raise CopilotAuthenticationError(f"Copilot command failed: {result.stderr}")
            return {"output": result.stdout, "error": result.stderr}
        except subprocess.TimeoutExpired:
            raise CopilotRateLimitError(f"Copilot command timed out after {self._timeout}s")
        except FileNotFoundError:
            raise CopilotAuthenticationError("Copilot CLI not found")

    def get_models(self) -> list[str]:
        """Get available Copilot models."""
        if not self._authenticated:
            try:
                self.authenticate()
            except Exception:
                return []
        try:
            result = self._execute_copilot(["models", "--json"])
            return result.get("models", [])
        except Exception as e:
            logger.warning(f"Failed to get models: {e}")
            return ["gpt-4", "claude-3-sonnet"]

    def is_authenticated(self) -> bool:
        return self._authenticated

    def logout(self) -> None:
        """Log out from GitHub Copilot."""
        with contextlib.suppress(Exception):
            self._execute_copilot(["auth", "logout"], check=False)
        self._authenticated = False
        self._session_id = None
        if self._process:
            self._process.terminate()
            self._process = None
        logger.info("Logged out from GitHub Copilot")

    def set_allowed_directories(self, directories: list[str]) -> None:
        """Set directories that file operations are allowed in."""
        self._allowed_directories = [str(Path(d).resolve()) for d in directories]

    def set_denied_directories(self, directories: list[str]) -> None:
        """Set directories that file operations are denied in."""
        self._denied_directories = [str(Path(d).resolve()) for d in directories]

    def _check_path_permission(self, path: str, operation: str = "read") -> bool:
        """Check if a path operation is permitted."""
        resolved = str(Path(path).resolve())

        for denied in self._denied_directories:
            if resolved.startswith(denied):
                logger.warning(f"Path {path} is in denied directory {denied}")
                return False

        if self._allowed_directories:
            allowed = any(resolved.startswith(d) for d in self._allowed_directories)
            if not allowed:
                logger.warning(f"Path {path} is not in allowed directories")
                return False

        return True

    def read_file(self, path: str, offset: int = 0, length: int | None = None) -> str:
        """Read a file through Copilot."""
        if not self._check_path_permission(path, "read"):
            raise CopilotPermissionError(f"Permission denied to read: {path}")

        try:
            return self._execute_copilot(["file", "read", path])["content"]
        except Exception as e:
            logger.error(f"Failed to read file {path}: {e}")
            return ""

    def write_file(self, path: str, content: str, offset: int | None = None) -> bool:
        """Write to a file through Copilot."""
        if not self._check_path_permission(path, "write"):
            raise CopilotPermissionError(f"Permission denied to write: {path}")

        try:
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
                f.write(content)
                temp_path = f.name

            try:
                self._execute_copilot(["file", "write", path, "--source", temp_path])
                return True
            finally:
                Path(temp_path).unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"Failed to write file {path}: {e}")
            return False

    def complete(
        self,
        prompt: str,
        model: str = "gpt-4",
        system_prompt: str | None = None,
        context: list[str] | None = None,
    ) -> tuple[str, list[ToolCallResult]]:
        """Get a completion from Copilot.

        Returns:
            Tuple of (text_response, tool_calls)
        """
        if not self._authenticated and not self.authenticate():
            raise CopilotAuthenticationError("Not authenticated with Copilot")

        session_id = self._session_id or self._create_session()
        params: dict[str, Any] = {
            "session_id": session_id,
            "prompt": prompt,
            "model": model,
        }
        if system_prompt:
            params["system_prompt"] = system_prompt
        if context:
            params["context"] = context

        try:
            response = self._send_request("complete", params)
            text = self._extract_text(response)
            tool_calls = self._extract_tool_calls(response)
            return text, tool_calls
        except Exception as e:
            logger.error(f"Completion failed: {e}")
            return f"Error: {str(e)}", []

    def stream_complete(
        self,
        prompt: str,
        model: str = "gpt-4",
        system_prompt: str | None = None,
        context: list[str] | None = None,
        callback: Callable[[str], None] | None = None,
    ) -> Iterator[str]:
        """Stream a completion from Copilot.

        Args:
            prompt: User prompt
            model: Model to use
            system_prompt: Optional system prompt
            context: Optional list of context files
            callback: Optional callback for each chunk

        Yields:
            Text chunks as they arrive
        """
        if not self._authenticated and not self.authenticate():
            raise CopilotAuthenticationError("Not authenticated with Copilot")

        session_id = self._session_id or self._create_session()
        params: dict[str, Any] = {
            "session_id": session_id,
            "prompt": prompt,
            "model": model,
            "stream": True,
        }
        if system_prompt:
            params["system_prompt"] = system_prompt
        if context:
            params["context"] = context

        try:
            response = self._send_request("complete", params)
            text = self._extract_text(response)
            for chunk in text.split():
                if callback:
                    callback(chunk)
                yield chunk + " "
        except Exception as e:
            logger.error(f"Stream completion failed: {e}")
            yield f"Error: {str(e)}"

    def _create_session(self) -> str:
        """Create a new Copilot session."""
        session_id = f"prometheus_{int(time.time())}_{os.getpid()}"
        self._session_id = session_id
        return session_id

    def _extract_text(self, response: dict[str, Any]) -> str:
        """Extract text content from a Copilot response."""
        content = response.get("content", [])
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
                elif isinstance(item, str):
                    parts.append(item.strip())
            return "\n".join(parts).strip()
        return str(content).strip() if content else ""

    def _extract_tool_calls(self, response: dict[str, Any]) -> list[ToolCallResult]:
        """Extract tool calls from a Copilot response."""
        tool_calls = []
        content = response.get("content", [])

        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    tool_name = item.get("name", "unknown")
                    tool_input = item.get("input", {})
                    tool_output = item.get("output", "")

                    tool_calls.append(
                        ToolCallResult(
                            tool_name=tool_name,
                            arguments=tool_input,
                            output=str(tool_output) if tool_output else "",
                        )
                    )

        return tool_calls

    def get_completion_options(self, model: str) -> dict[str, Any]:
        """Get completion options for a model."""
        return {
            "model": model,
            "temperature": 0.7,
            "max_tokens": 2048,
            "top_p": 1.0,
            "stream": False,
        }

    def set_token(self, token: str) -> None:
        """Set the GitHub token."""
        self._token = token
        self._authenticated = False

    def __del__(self) -> None:
        """Cleanup on deletion."""
        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                pass
