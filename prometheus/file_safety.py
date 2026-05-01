from __future__ import annotations

import os
import re
from pathlib import Path

DANGEROUS_PATTERNS: list[str] = [
    r"rm\s+-rf",
    r"rm\s+-fr",
    r"sudo\s+",
    r"chmod\s+777",
    r"chmod\s+-R\s+777",
    r"mkfs",
    r"dd\s+if=",
    r">\s*/dev/sd",
    r"curl\s+.*\|\s*bash",
    r"wget\s+.*\|\s*sh",
    r"eval\s+",
    r"exec\s+",
    r">\s*/dev/null\s*2>&1",
    r":()\s*{\s*:\|:&\s*}\s*;:",
    r"fork\s*bomb",
]

DANGEROUS_PATHS: list[str] = [
    "/",
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/root",
    "/home",
    "/var",
    "/sys",
    "/proc",
    "/dev",
    "~/.ssh",
    "~/.gnupg",
    "~/.config",
    "~/.aws",
    "~/.kube",
]

_SAFE_EXTENSIONS: set[str] = {
    ".txt", ".md", ".json", ".yaml", ".yml", ".toml",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs",
    ".java", ".kt", ".swift", ".c", ".cpp", ".h", ".hpp",
    ".html", ".css", ".scss", ".less", ".xml", ".sql",
    ".sh", ".bash", ".zsh", ".fish",
    ".csv", ".tsv", ".log",
}

_COMPILED_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS
]


def is_dangerous_command(command: str) -> tuple[bool, str]:
    if not command or not command.strip():
        return False, ""
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(command):
            return True, f"Command matches dangerous pattern: {pattern.pattern}"
    return False, ""


def is_dangerous_path(path: str) -> tuple[bool, str]:
    if not path:
        return False, ""
    expanded = os.path.expanduser(path)
    try:
        resolved = os.path.abspath(os.path.realpath(expanded))
    except (OSError, ValueError):
        resolved = os.path.abspath(expanded)
    normalized = os.path.normpath(resolved)
    for dangerous in DANGEROUS_PATHS:
        d_expanded = os.path.expanduser(dangerous)
        d_normalized = os.path.normpath(os.path.abspath(d_expanded))
        if normalized == d_normalized or normalized.startswith(d_normalized + os.sep):
            return True, f"Path is in protected directory: {dangerous}"
    return False, ""


def check_file_operation(operation: str, path: str, content: str | None = None) -> tuple[bool, str]:
    if operation not in ("read", "write", "delete", "execute"):
        return False, f"Unknown operation: {operation}"
    is_dangerous, reason = is_dangerous_path(path)
    if is_dangerous:
        return False, reason
    if operation == "write" and content:
        cmd_dangerous, cmd_reason = is_dangerous_command(content)
        if cmd_dangerous:
            return False, f"Content contains dangerous command: {cmd_reason}"
    if operation == "execute":
        cmd_dangerous, cmd_reason = is_dangerous_command(path)
        if cmd_dangerous:
            return False, cmd_reason
    return True, ""


def sanitize_path(path: str) -> str:
    if not path:
        return ""
    expanded = os.path.expanduser(path)
    try:
        resolved = os.path.abspath(os.path.realpath(expanded))
    except (OSError, ValueError):
        resolved = os.path.abspath(expanded)
    normalized = os.path.normpath(resolved)
    is_dangerous, reason = is_dangerous_path(normalized)
    if is_dangerous:
        raise ValueError(f"Path is not safe: {reason}")
    return normalized


def is_safe_extension(path: str) -> bool:
    ext = Path(path).suffix.lower()
    return ext in _SAFE_EXTENSIONS


def validate_file_path(path: str, must_exist: bool = False) -> tuple[bool, str]:
    try:
        sanitized = sanitize_path(path)
    except ValueError as e:
        return False, str(e)
    if must_exist and not os.path.exists(sanitized):
        return False, f"File does not exist: {sanitized}"
    return True, sanitized
