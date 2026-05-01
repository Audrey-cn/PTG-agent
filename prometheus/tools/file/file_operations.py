#!/usr/bin/env python3
"""File Operations Module."""

import contextlib
import difflib
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prometheus.file_safety import (
    build_write_denied_paths,
    build_write_denied_prefixes,
)
from prometheus.file_safety import (
    get_safe_write_root as _shared_get_safe_write_root,
)
from prometheus.file_safety import (
    is_write_denied as _shared_is_write_denied,
)
from prometheus.tools.binary_extensions import BINARY_EXTENSIONS

_HOME = str(Path.home())

WRITE_DENIED_PATHS = build_write_denied_paths(_HOME)

WRITE_DENIED_PREFIXES = build_write_denied_prefixes(_HOME)


def _get_safe_write_root() -> str | None:
    """Return the resolved PROMETHEUS_WRITE_SAFE_ROOT path, or None if unset.

    When set, all write_file/patch operations are constrained to this
    directory tree.  Writes outside it are denied even if the target is
    not on the static deny list.  Opt-in hardening for gateway/messaging
    deployments that should only touch a workspace checkout.
    """
    return _shared_get_safe_write_root()


def _is_write_denied(path: str) -> bool:
    """Return True if path is on the write deny list."""
    return _shared_is_write_denied(path)


# =============================================================================
# Result Data Classes
# =============================================================================


@dataclass
class ReadResult:
    """Result from reading a file."""

    content: str = ""
    total_lines: int = 0
    file_size: int = 0
    truncated: bool = False
    hint: str | None = None
    is_binary: bool = False
    is_image: bool = False
    base64_content: str | None = None
    mime_type: str | None = None
    dimensions: str | None = None
    error: str | None = None
    similar_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None and v != []}


@dataclass
class WriteResult:
    """Result from writing a file."""

    bytes_written: int = 0
    dirs_created: bool = False
    error: str | None = None
    warning: str | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class PatchResult:
    """Result from patching a file."""

    success: bool = False
    diff: str = ""
    files_modified: list[str] = field(default_factory=list)
    files_created: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    lint: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        result = {"success": self.success}
        if self.diff:
            result["diff"] = self.diff
        if self.files_modified:
            result["files_modified"] = self.files_modified
        if self.files_created:
            result["files_created"] = self.files_created
        if self.files_deleted:
            result["files_deleted"] = self.files_deleted
        if self.lint:
            result["lint"] = self.lint
        if self.error:
            result["error"] = self.error
        return result


@dataclass
class SearchMatch:
    """A single search match."""

    path: str
    line_number: int
    content: str
    mtime: float = 0.0


@dataclass
class SearchResult:
    """Result from searching."""

    matches: list[SearchMatch] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    total_count: int = 0
    truncated: bool = False
    error: str | None = None

    def to_dict(self) -> dict:
        result = {"total_count": self.total_count}
        if self.matches:
            result["matches"] = [
                {"path": m.path, "line": m.line_number, "content": m.content} for m in self.matches
            ]
        if self.files:
            result["files"] = self.files
        if self.counts:
            result["counts"] = self.counts
        if self.truncated:
            result["truncated"] = True
        if self.error:
            result["error"] = self.error
        return result


@dataclass
class LintResult:
    """Result from linting a file."""

    success: bool = True
    skipped: bool = False
    output: str = ""
    message: str = ""

    def to_dict(self) -> dict:
        if self.skipped:
            return {"status": "skipped", "message": self.message}
        return {"status": "ok" if self.success else "error", "output": self.output}


@dataclass
class ExecuteResult:
    """Result from executing a shell command."""

    stdout: str = ""
    exit_code: int = 0


# =============================================================================
# Abstract Interface
# =============================================================================


class FileOperations(ABC):
    """Abstract interface for file operations across terminal backends."""

    @abstractmethod
    def read_file(self, path: str, offset: int = 1, limit: int = 500) -> ReadResult:
        """Read a file with pagination support."""
        ...

    @abstractmethod
    def read_file_raw(self, path: str) -> ReadResult:
        """Read the complete file content as a plain string."""
        ...

    @abstractmethod
    def write_file(self, path: str, content: str) -> WriteResult:
        """Write content to a file, creating directories as needed."""
        ...

    @abstractmethod
    def patch_replace(
        self, path: str, old_string: str, new_string: str, replace_all: bool = False
    ) -> PatchResult:
        """Replace text in a file using fuzzy matching."""
        ...

    @abstractmethod
    def patch_v4a(self, patch_content: str) -> PatchResult:
        """Apply a V4A format patch."""
        ...

    @abstractmethod
    def delete_file(self, path: str) -> WriteResult:
        """Delete a file. Returns WriteResult with .error set on failure."""
        ...

    @abstractmethod
    def move_file(self, src: str, dst: str) -> WriteResult:
        """Move/rename a file from src to dst. Returns WriteResult with .error set on failure."""
        ...

    @abstractmethod
    def search(
        self,
        pattern: str,
        path: str = ".",
        target: str = "content",
        file_glob: str | None = None,
        limit: int = 50,
        offset: int = 0,
        output_mode: str = "content",
        context: int = 0,
    ) -> SearchResult:
        """Search for content or files."""
        ...


# =============================================================================
# Shell-based Implementation
# =============================================================================

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico"}

LINTERS = {
    ".py": "python -m py_compile {file} 2>&1",
    ".js": "node --check {file} 2>&1",
    ".ts": "npx tsc --noEmit {file} 2>&1",
    ".go": "go vet {file} 2>&1",
    ".rs": "rustfmt --check {file} 2>&1",
}

MAX_LINES = 2000
MAX_LINE_LENGTH = 2000
MAX_FILE_SIZE = 50 * 1024
DEFAULT_READ_OFFSET = 1
DEFAULT_READ_LIMIT = 500
DEFAULT_SEARCH_OFFSET = 0
DEFAULT_SEARCH_LIMIT = 50


def _coerce_int(value: Any, default: int) -> int:
    """Best-effort integer coercion for tool pagination inputs."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_read_pagination(
    offset: Any = DEFAULT_READ_OFFSET, limit: Any = DEFAULT_READ_LIMIT
) -> Tuple[int, int]:
    """Return safe read_file pagination bounds."""
    from prometheus.tools.tool_output_limits import get_max_lines

    max_lines = get_max_lines()
    normalized_offset = max(1, _coerce_int(offset, DEFAULT_READ_OFFSET))
    normalized_limit = _coerce_int(limit, DEFAULT_READ_LIMIT)
    normalized_limit = max(1, min(normalized_limit, max_lines))
    return normalized_offset, normalized_limit


def normalize_search_pagination(
    offset: Any = DEFAULT_SEARCH_OFFSET, limit: Any = DEFAULT_SEARCH_LIMIT
) -> Tuple[int, int]:
    """Return safe search pagination bounds for shell head/tail pipelines."""
    normalized_offset = max(0, _coerce_int(offset, DEFAULT_SEARCH_OFFSET))
    normalized_limit = max(1, _coerce_int(limit, DEFAULT_SEARCH_LIMIT))
    return normalized_offset, normalized_limit


class ShellFileOperations(FileOperations):
    """
    File operations implemented via shell commands.

    Works with ANY terminal backend that has execute(command, cwd) method.
    This includes local, docker, singularity, ssh, modal, and daytona environments.
    """

    def __init__(self, terminal_env, cwd: str = None):
        """
        Initialize file operations with a terminal environment.

        Args:
            terminal_env: Any object with execute(command, cwd) method.
                         Returns {"output": str, "returncode": int}
            cwd: Optional explicit fallback cwd when the terminal env has
                 no cwd attribute.
        """
        self.env = terminal_env
        self.cwd = (
            cwd
            or getattr(terminal_env, "cwd", None)
            or getattr(getattr(terminal_env, "config", None), "cwd", None)
            or "/"
        )

        self._command_cache: dict[str, bool] = {}

    def _exec(
        self, command: str, cwd: str = None, timeout: int = None, stdin_data: str = None
    ) -> ExecuteResult:
        """Execute command via terminal backend."""
        kwargs = {}
        if timeout:
            kwargs["timeout"] = timeout
        if stdin_data is not None:
            kwargs["stdin_data"] = stdin_data

        effective_cwd = cwd or getattr(self.env, "cwd", None) or self.cwd
        result = self.env.execute(command, cwd=effective_cwd, **kwargs)
        return ExecuteResult(stdout=result.get("output", ""), exit_code=result.get("returncode", 0))

    def _has_command(self, cmd: str) -> bool:
        """Check if a command exists in the environment (cached)."""
        if cmd not in self._command_cache:
            result = self._exec(f"command -v {cmd} >/dev/null 2>&1 && echo 'yes'")
            self._command_cache[cmd] = result.stdout.strip() == "yes"
        return self._command_cache[cmd]

    def _is_likely_binary(self, path: str, content_sample: str = None) -> bool:
        """
        Check if a file is likely binary.
        """
        ext = os.path.splitext(path)[1].lower()
        if ext in BINARY_EXTENSIONS:
            return True

        if content_sample:
            non_printable = sum(
                1 for c in content_sample[:1000] if ord(c) < 32 and c not in "\n\r\t"
            )
            return non_printable / min(len(content_sample), 1000) > 0.30

        return False

    def _is_image(self, path: str) -> bool:
        """Check if file is an image we can return as base64."""
        ext = os.path.splitext(path)[1].lower()
        return ext in IMAGE_EXTENSIONS

    def _add_line_numbers(self, content: str, start_line: int = 1) -> str:
        """Add line numbers to content in LINE_NUM|CONTENT format."""
        from prometheus.tools.tool_output_limits import get_max_line_length

        max_line_length = get_max_line_length()
        lines = content.split("\n")
        numbered = []
        for i, line in enumerate(lines, start=start_line):
            if len(line) > max_line_length:
                line = line[:max_line_length] + "... [truncated]"
            numbered.append(f"{i:6d}|{line}")
        return "\n".join(numbered)

    def _expand_path(self, path: str) -> str:
        """
        Expand shell-style paths like ~ and ~user to absolute paths.
        """
        if not path:
            return path

        if path.startswith("~"):
            result = self._exec("echo $HOME")
            if result.exit_code == 0 and result.stdout.strip():
                home = result.stdout.strip()
                if path == "~":
                    return home
                elif path.startswith("~/"):
                    return home + path[1:]
                rest = path[1:]
                slash_idx = rest.find("/")
                username = rest[:slash_idx] if slash_idx >= 0 else rest
                if username and re.fullmatch(r"[a-zA-Z0-9._-]+", username):
                    expand_result = self._exec(f"echo ~{username}")
                    if expand_result.exit_code == 0 and expand_result.stdout.strip():
                        user_home = expand_result.stdout.strip()
                        suffix = path[1 + len(username) :]
                        return user_home + suffix

        return path

    def _escape_shell_arg(self, arg: str) -> str:
        """Escape a string for safe use in shell commands."""
        return "'" + arg.replace("'", "'\"'\"'") + "'"

    def _unified_diff(self, old_content: str, new_content: str, filename: str) -> str:
        """Generate unified diff between old and new content."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines, new_lines, fromfile=f"a/{filename}", tofile=f"b/{filename}"
        )
        return "".join(diff)

    # =========================================================================
    # READ Implementation
    # =========================================================================

    def read_file(self, path: str, offset: int = 1, limit: int = 500) -> ReadResult:
        """
        Read a file with pagination, binary detection, and line numbers.
        """
        path = self._expand_path(path)

        offset, limit = normalize_read_pagination(offset, limit)

        stat_cmd = f"wc -c < {self._escape_shell_arg(path)} 2>/dev/null"
        stat_result = self._exec(stat_cmd)

        if stat_result.exit_code != 0:
            return self._suggest_similar_files(path)

        try:
            file_size = int(stat_result.stdout.strip())
        except ValueError:
            file_size = 0

        if self._is_image(path):
            return ReadResult(
                is_image=True,
                is_binary=True,
                file_size=file_size,
                hint=(
                    "Image file detected. Automatically redirected to vision_analyze tool. "
                    "Use vision_analyze with this file path to inspect the image contents."
                ),
            )

        sample_cmd = f"head -c 1000 {self._escape_shell_arg(path)} 2>/dev/null"
        sample_result = self._exec(sample_cmd)

        if self._is_likely_binary(path, sample_result.stdout):
            return ReadResult(
                is_binary=True,
                file_size=file_size,
                error="Binary file - cannot display as text. Use appropriate tools to handle this file type.",
            )

        end_line = offset + limit - 1
        read_cmd = f"sed -n '{offset},{end_line}p' {self._escape_shell_arg(path)}"
        read_result = self._exec(read_cmd)

        if read_result.exit_code != 0:
            return ReadResult(error=f"Failed to read file: {read_result.stdout}")

        wc_cmd = f"wc -l < {self._escape_shell_arg(path)}"
        wc_result = self._exec(wc_cmd)
        try:
            total_lines = int(wc_result.stdout.strip())
        except ValueError:
            total_lines = 0

        truncated = total_lines > end_line
        hint = None
        if truncated:
            hint = f"Use offset={end_line + 1} to continue reading (showing {offset}-{end_line} of {total_lines} lines)"

        return ReadResult(
            content=self._add_line_numbers(read_result.stdout, offset),
            total_lines=total_lines,
            file_size=file_size,
            truncated=truncated,
            hint=hint,
        )

    def _suggest_similar_files(self, path: str) -> ReadResult:
        """Suggest similar files when the requested file is not found."""
        dir_path = os.path.dirname(path) or "."
        filename = os.path.basename(path)
        basename_no_ext = os.path.splitext(filename)[0]
        ext = os.path.splitext(filename)[1].lower()
        lower_name = filename.lower()

        ls_cmd = f"ls -1 {self._escape_shell_arg(dir_path)} 2>/dev/null | head -50"
        ls_result = self._exec(ls_cmd)

        scored: list = []
        if ls_result.exit_code == 0 and ls_result.stdout.strip():
            for f in ls_result.stdout.strip().split("\n"):
                if not f:
                    continue
                lf = f.lower()
                score = 0

                if lf == lower_name:
                    score = 100
                elif os.path.splitext(f)[0].lower() == basename_no_ext.lower():
                    score = 90
                elif lf.startswith(lower_name) or lower_name.startswith(lf):
                    score = 70
                elif lower_name in lf:
                    score = 60
                elif lf in lower_name and len(lf) > 2:
                    score = 40
                elif ext and os.path.splitext(f)[1].lower() == ext:
                    common = set(lower_name) & set(lf)
                    if len(common) >= max(len(lower_name), len(lf)) * 0.4:
                        score = 30

                if score > 0:
                    scored.append((score, os.path.join(dir_path, f)))

        scored.sort(key=lambda x: -x[0])
        similar = [fp for _, fp in scored[:5]]

        return ReadResult(error=f"File not found: {path}", similar_files=similar)

    def read_file_raw(self, path: str) -> ReadResult:
        """Read the complete file content as a plain string."""
        path = self._expand_path(path)
        stat_cmd = f"wc -c < {self._escape_shell_arg(path)} 2>/dev/null"
        stat_result = self._exec(stat_cmd)
        if stat_result.exit_code != 0:
            return self._suggest_similar_files(path)
        try:
            file_size = int(stat_result.stdout.strip())
        except ValueError:
            file_size = 0
        if self._is_image(path):
            return ReadResult(is_image=True, is_binary=True, file_size=file_size)
        sample_result = self._exec(f"head -c 1000 {self._escape_shell_arg(path)} 2>/dev/null")
        if self._is_likely_binary(path, sample_result.stdout):
            return ReadResult(
                is_binary=True, file_size=file_size, error="Binary file — cannot display as text."
            )
        cat_result = self._exec(f"cat {self._escape_shell_arg(path)}")
        if cat_result.exit_code != 0:
            return ReadResult(error=f"Failed to read file: {cat_result.stdout}")
        return ReadResult(content=cat_result.stdout, file_size=file_size)

    def delete_file(self, path: str) -> WriteResult:
        """Delete a file via rm."""
        path = self._expand_path(path)
        if _is_write_denied(path):
            return WriteResult(error=f"Delete denied: {path} is a protected path")
        result = self._exec(f"rm -f {self._escape_shell_arg(path)}")
        if result.exit_code != 0:
            return WriteResult(error=f"Failed to delete {path}: {result.stdout}")
        return WriteResult()

    def move_file(self, src: str, dst: str) -> WriteResult:
        """Move a file via mv."""
        src = self._expand_path(src)
        dst = self._expand_path(dst)
        for p in (src, dst):
            if _is_write_denied(p):
                return WriteResult(error=f"Move denied: {p} is a protected path")
        result = self._exec(f"mv {self._escape_shell_arg(src)} {self._escape_shell_arg(dst)}")
        if result.exit_code != 0:
            return WriteResult(error=f"Failed to move {src} -> {dst}: {result.stdout}")
        return WriteResult()

    # =========================================================================
    # WRITE Implementation
    # =========================================================================

    def write_file(self, path: str, content: str) -> WriteResult:
        """
        Write content to a file, creating parent directories as needed.
        """
        path = self._expand_path(path)

        if _is_write_denied(path):
            return WriteResult(
                error=f"Write denied: '{path}' is a protected system/credential file."
            )

        parent = os.path.dirname(path)
        dirs_created = False

        if parent:
            mkdir_cmd = f"mkdir -p {self._escape_shell_arg(parent)}"
            mkdir_result = self._exec(mkdir_cmd)
            if mkdir_result.exit_code == 0:
                dirs_created = True

        write_cmd = f"cat > {self._escape_shell_arg(path)}"
        write_result = self._exec(write_cmd, stdin_data=content)

        if write_result.exit_code != 0:
            return WriteResult(error=f"Failed to write file: {write_result.stdout}")

        stat_cmd = f"wc -c < {self._escape_shell_arg(path)} 2>/dev/null"
        stat_result = self._exec(stat_cmd)

        try:
            bytes_written = int(stat_result.stdout.strip())
        except ValueError:
            bytes_written = len(content.encode("utf-8"))

        return WriteResult(bytes_written=bytes_written, dirs_created=dirs_created)

    # =========================================================================
    # PATCH Implementation (Replace Mode)
    # =========================================================================

    def patch_replace(
        self, path: str, old_string: str, new_string: str, replace_all: bool = False
    ) -> PatchResult:
        """
        Replace text in a file using fuzzy matching.
        """
        path = self._expand_path(path)

        if _is_write_denied(path):
            return PatchResult(
                error=f"Write denied: '{path}' is a protected system/credential file."
            )

        read_cmd = f"cat {self._escape_shell_arg(path)} 2>/dev/null"
        read_result = self._exec(read_cmd)

        if read_result.exit_code != 0:
            return PatchResult(error=f"Failed to read file: {path}")

        content = read_result.stdout

        from prometheus.tools.fuzzy_match import fuzzy_find_and_replace

        new_content, match_count, _strategy, error = fuzzy_find_and_replace(
            content, old_string, new_string, replace_all
        )

        if error or match_count == 0:
            err_msg = error or f"Could not find match for old_string in {path}"
            try:
                from prometheus.tools.fuzzy_match import format_no_match_hint

                err_msg += format_no_match_hint(err_msg, match_count, old_string, content)
            except Exception:
                pass
            return PatchResult(error=err_msg)
        write_result = self.write_file(path, new_content)
        if write_result.error:
            return PatchResult(error=f"Failed to write changes: {write_result.error}")

        verify_cmd = f"cat {self._escape_shell_arg(path)} 2>/dev/null"
        verify_result = self._exec(verify_cmd)
        if verify_result.exit_code != 0:
            return PatchResult(error=f"Post-write verification failed: could not re-read {path}")
        if verify_result.stdout != new_content:
            return PatchResult(
                error=(
                    f"Post-write verification failed for {path}: on-disk content "
                    f"differs from intended write "
                    f"(wrote {len(new_content)} chars, read back {len(verify_result.stdout)}). "
                    "The patch did not persist. Re-read the file and try again."
                )
            )

        diff = self._unified_diff(content, new_content, path)

        lint_result = self._check_lint(path)

        return PatchResult(
            success=True,
            diff=diff,
            files_modified=[path],
            lint=lint_result.to_dict() if lint_result else None,
        )

    def patch_v4a(self, patch_content: str) -> PatchResult:
        """
        Apply a V4A format patch.
        """
        from prometheus.tools.patch_parser import apply_v4a_operations, parse_v4a_patch

        operations, parse_error = parse_v4a_patch(patch_content)
        if parse_error:
            return PatchResult(error=f"Failed to parse patch: {parse_error}")

        result = apply_v4a_operations(operations, self)
        return result

    def _check_lint(self, path: str) -> LintResult:
        """
        Run syntax check on a file after editing.
        """
        ext = os.path.splitext(path)[1].lower()

        if ext not in LINTERS:
            return LintResult(skipped=True, message=f"No linter for {ext} files")

        linter_cmd = LINTERS[ext]
        base_cmd = linter_cmd.split()[0]

        if not self._has_command(base_cmd):
            return LintResult(skipped=True, message=f"{base_cmd} not available")

        cmd = linter_cmd.replace("{file}", self._escape_shell_arg(path))
        result = self._exec(cmd, timeout=30)

        return LintResult(
            success=result.exit_code == 0,
            output=result.stdout.strip() if result.stdout.strip() else "",
        )

    # =========================================================================
    # SEARCH Implementation
    # =========================================================================

    def search(
        self,
        pattern: str,
        path: str = ".",
        target: str = "content",
        file_glob: str | None = None,
        limit: int = 50,
        offset: int = 0,
        output_mode: str = "content",
        context: int = 0,
    ) -> SearchResult:
        """
        Search for content or files.
        """
        offset, limit = normalize_search_pagination(offset, limit)

        path = self._expand_path(path)

        check = self._exec(
            f"test -e {self._escape_shell_arg(path)} && echo exists || echo not_found"
        )
        if "not_found" in check.stdout:
            parent = os.path.dirname(path) or "."
            basename_query = os.path.basename(path)
            hint_parts = [f"Path not found: {path}"]
            parent_check = self._exec(
                f"test -d {self._escape_shell_arg(parent)} && echo yes || echo no"
            )
            if "yes" in parent_check.stdout and basename_query:
                ls_result = self._exec(
                    f"ls -1 {self._escape_shell_arg(parent)} 2>/dev/null | head -20"
                )
                if ls_result.exit_code == 0 and ls_result.stdout.strip():
                    lower_q = basename_query.lower()
                    candidates = []
                    for entry in ls_result.stdout.strip().split("\n"):
                        if not entry:
                            continue
                        le = entry.lower()
                        if lower_q in le or le in lower_q or le.startswith(lower_q[:3]):
                            candidates.append(os.path.join(parent, entry))
                    if candidates:
                        hint_parts.append("Similar paths: " + ", ".join(candidates[:5]))
            return SearchResult(error=". ".join(hint_parts), total_count=0)

        if target == "files":
            return self._search_files(pattern, path, limit, offset)
        else:
            return self._search_content(
                pattern, path, file_glob, limit, offset, output_mode, context
            )

    def _search_files(self, pattern: str, path: str, limit: int, offset: int) -> SearchResult:
        """Search for files by name pattern (glob-like)."""
        if not pattern.startswith("**/") and "/" not in pattern:
            search_pattern = pattern
        else:
            search_pattern = pattern.split("/")[-1]

        if self._has_command("rg"):
            return self._search_files_rg(search_pattern, path, limit, offset)

        if not self._has_command("find"):
            return SearchResult(
                error="File search requires 'rg' (ripgrep) or 'find'. "
                "Install ripgrep for best results: "
                "https://github.com/BurntSushi/ripgrep#installation"
            )

        hidden_exclude = "-not -path '*/.*'"

        cmd = (
            f"find {self._escape_shell_arg(path)} {hidden_exclude} -type f -name {self._escape_shell_arg(search_pattern)} "
            f"-printf '%T@ %p\\n' 2>/dev/null | sort -rn | tail -n +{offset + 1} | head -n {limit}"
        )

        result = self._exec(cmd, timeout=60)

        if not result.stdout.strip():
            cmd_simple = (
                f"find {self._escape_shell_arg(path)} {hidden_exclude} -type f -name {self._escape_shell_arg(search_pattern)} "
                f"2>/dev/null | head -n {limit + offset} | tail -n +{offset + 1}"
            )
            result = self._exec(cmd_simple, timeout=60)

        files = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split(" ", 1)
            if len(parts) == 2 and parts[0].replace(".", "").isdigit():
                files.append(parts[1])
            else:
                files.append(line)

        return SearchResult(files=files, total_count=len(files))

    def _search_files_rg(self, pattern: str, path: str, limit: int, offset: int) -> SearchResult:
        """Search for files by name using ripgrep's --files mode."""
        if "/" not in pattern and not pattern.startswith("*"):
            glob_pattern = f"*{pattern}"
        else:
            glob_pattern = pattern

        fetch_limit = limit + offset
        cmd_sorted = (
            f"rg --files --sortr=modified -g {self._escape_shell_arg(glob_pattern)} "
            f"{self._escape_shell_arg(path)} 2>/dev/null "
            f"| head -n {fetch_limit}"
        )
        result = self._exec(cmd_sorted, timeout=60)
        all_files = [f for f in result.stdout.strip().split("\n") if f]

        if not all_files:
            cmd_plain = (
                f"rg --files -g {self._escape_shell_arg(glob_pattern)} "
                f"{self._escape_shell_arg(path)} 2>/dev/null "
                f"| head -n {fetch_limit}"
            )
            result = self._exec(cmd_plain, timeout=60)
            all_files = [f for f in result.stdout.strip().split("\n") if f]

        page = all_files[offset : offset + limit]

        return SearchResult(
            files=page,
            total_count=len(all_files),
            truncated=len(all_files) >= fetch_limit,
        )

    def _search_content(
        self,
        pattern: str,
        path: str,
        file_glob: str | None,
        limit: int,
        offset: int,
        output_mode: str,
        context: int,
    ) -> SearchResult:
        """Search for content inside files (grep-like)."""
        if self._has_command("rg"):
            return self._search_with_rg(
                pattern, path, file_glob, limit, offset, output_mode, context
            )
        elif self._has_command("grep"):
            return self._search_with_grep(
                pattern, path, file_glob, limit, offset, output_mode, context
            )
        else:
            return SearchResult(
                error="Content search requires ripgrep (rg) or grep. "
                "Install ripgrep: https://github.com/BurntSushi/ripgrep#installation"
            )

    def _search_with_rg(
        self,
        pattern: str,
        path: str,
        file_glob: str | None,
        limit: int,
        offset: int,
        output_mode: str,
        context: int,
    ) -> SearchResult:
        """Search using ripgrep."""
        cmd_parts = ["rg", "--line-number", "--no-heading", "--with-filename"]

        if context > 0:
            cmd_parts.extend(["-C", str(context)])

        if file_glob:
            cmd_parts.extend(["--glob", self._escape_shell_arg(file_glob)])

        if output_mode == "files_only":
            cmd_parts.append("-l")
        elif output_mode == "count":
            cmd_parts.append("-c")

        cmd_parts.append(self._escape_shell_arg(pattern))
        cmd_parts.append(self._escape_shell_arg(path))

        fetch_limit = limit + offset + 200 if context > 0 else limit + offset
        cmd_parts.extend(["|", "head", "-n", str(fetch_limit)])

        cmd = " ".join(cmd_parts)
        result = self._exec(cmd, timeout=60)

        if result.exit_code == 2 and not result.stdout.strip():
            error_msg = (
                result.stderr.strip()
                if hasattr(result, "stderr") and result.stderr
                else "Search error"
            )
            return SearchResult(error=f"Search failed: {error_msg}", total_count=0)

        if output_mode == "files_only":
            all_files = [f for f in result.stdout.strip().split("\n") if f]
            total = len(all_files)
            page = all_files[offset : offset + limit]
            return SearchResult(files=page, total_count=total)

        elif output_mode == "count":
            counts = {}
            for line in result.stdout.strip().split("\n"):
                if ":" in line:
                    parts = line.rsplit(":", 1)
                    if len(parts) == 2:
                        with contextlib.suppress(ValueError):
                            counts[parts[0]] = int(parts[1])
            return SearchResult(counts=counts, total_count=sum(counts.values()))

        else:
            _match_re = re.compile(r"^([A-Za-z]:)?(.*?):(\d+):(.*)$")
            _ctx_re = re.compile(r"^([A-Za-z]:)?(.*?)-(\d+)-(.*)$")
            matches = []
            for line in result.stdout.strip().split("\n"):
                if not line or line == "--":
                    continue

                m = _match_re.match(line)
                if m:
                    matches.append(
                        SearchMatch(
                            path=(m.group(1) or "") + m.group(2),
                            line_number=int(m.group(3)),
                            content=m.group(4)[:500],
                        )
                    )
                    continue

                if context > 0:
                    m = _ctx_re.match(line)
                    if m:
                        matches.append(
                            SearchMatch(
                                path=(m.group(1) or "") + m.group(2),
                                line_number=int(m.group(3)),
                                content=m.group(4)[:500],
                            )
                        )

            total = len(matches)
            page = matches[offset : offset + limit]
            return SearchResult(matches=page, total_count=total, truncated=total > offset + limit)

    def _search_with_grep(
        self,
        pattern: str,
        path: str,
        file_glob: str | None,
        limit: int,
        offset: int,
        output_mode: str,
        context: int,
    ) -> SearchResult:
        """Fallback search using grep."""
        cmd_parts = ["grep", "-rnH"]

        cmd_parts.append("--exclude-dir='.*'")

        if context > 0:
            cmd_parts.extend(["-C", str(context)])

        if file_glob:
            cmd_parts.extend(["--include", self._escape_shell_arg(file_glob)])

        if output_mode == "files_only":
            cmd_parts.append("-l")
        elif output_mode == "count":
            cmd_parts.append("-c")

        cmd_parts.append(self._escape_shell_arg(pattern))
        cmd_parts.append(self._escape_shell_arg(path))

        fetch_limit = limit + offset + (200 if context > 0 else 0)
        cmd_parts.extend(["|", "head", "-n", str(fetch_limit)])

        cmd = " ".join(cmd_parts)
        result = self._exec(cmd, timeout=60)

        if result.exit_code == 2 and not result.stdout.strip():
            error_msg = (
                result.stderr.strip()
                if hasattr(result, "stderr") and result.stderr
                else "Search error"
            )
            return SearchResult(error=f"Search failed: {error_msg}", total_count=0)

        if output_mode == "files_only":
            all_files = [f for f in result.stdout.strip().split("\n") if f]
            total = len(all_files)
            page = all_files[offset : offset + limit]
            return SearchResult(files=page, total_count=total)

        elif output_mode == "count":
            counts = {}
            for line in result.stdout.strip().split("\n"):
                if ":" in line:
                    parts = line.rsplit(":", 1)
                    if len(parts) == 2:
                        with contextlib.suppress(ValueError):
                            counts[parts[0]] = int(parts[1])
            return SearchResult(counts=counts, total_count=sum(counts.values()))

        else:
            _match_re = re.compile(r"^([A-Za-z]:)?(.*?):(\d+):(.*)$")
            _ctx_re = re.compile(r"^([A-Za-z]:)?(.*?)-(\d+)-(.*)$")
            matches = []
            for line in result.stdout.strip().split("\n"):
                if not line or line == "--":
                    continue

                m = _match_re.match(line)
                if m:
                    matches.append(
                        SearchMatch(
                            path=(m.group(1) or "") + m.group(2),
                            line_number=int(m.group(3)),
                            content=m.group(4)[:500],
                        )
                    )
                    continue

                if context > 0:
                    m = _ctx_re.match(line)
                    if m:
                        matches.append(
                            SearchMatch(
                                path=(m.group(1) or "") + m.group(2),
                                line_number=int(m.group(3)),
                                content=m.group(4)[:500],
                            )
                        )

            total = len(matches)
            page = matches[offset : offset + limit]
            return SearchResult(matches=page, total_count=total, truncated=total > offset + limit)
