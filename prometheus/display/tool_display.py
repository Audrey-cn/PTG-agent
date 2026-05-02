"""CLI presentation -- spinner, kawaii faces, tool preview formatting.

Pure display functions and classes with no AIAgent dependency.
Used by AIAgent._execute_tool_calls for CLI feedback.
"""

import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# ANSI escape codes for coloring
_ANSI_RESET = "\033[0m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_BLUE = "\033[34m"
_DIM = "\033[2m"

# =========================================================================
# Tool preview (one-line summary of a tool call's primary argument)
# =========================================================================

def _oneline(text: str) -> str:
    """Collapse whitespace (including newlines) to single spaces."""
    return " ".join(text.split())

# Primary argument keys for common tools
_primary_args = {
    "browser_navigate": "url",
    "browser_click": "ref",
    "browser_type": "text",
    "browser_snapshot": "full",
    "browser_scroll": "direction",
    "web_search": "query",
    "web_extract": "urls",
    "read_file": "path",
    "write_file": "path",
    "patch": "path",
    "search_files": "pattern",
    "terminal": "command",
    "memory": "action",
    "session_search": "query",
    "send_message": "message",
    "todo": "todos",
    "clarify": "question",
    "skill_manage": "name",
    "kanban_show": "filter",
    "kanban_create": "title",
    "cronjob": "action",
    "execute_code": "code",
    "delegate_task": "goal",
}

def build_tool_preview(tool_name: str, args: dict, max_len: int = 0) -> str | None:
    """Build a short preview of a tool call's primary argument for display.
    
    *max_len* controls truncation. 0 means unlimited.
    """
    if not args:
        return None
    
    # Special handling for specific tools
    if tool_name == "todo":
        todos_arg = args.get("todos")
        if todos_arg is None:
            return "reading task list"
        return f"planning {len(todos_arg)} task(s)"
    
    if tool_name == "session_search":
        query = _oneline(args.get("query", ""))
        return f"recall: \"{query[:25]}{'...' if len(query) > 25 else ''}\""
    
    if tool_name == "memory":
        action = args.get("action", "")
        target = args.get("target", "")
        if action == "add":
            content = _oneline(args.get("content", ""))
            return f"+{target}: \"{content[:25]}{'...' if len(content) > 25 else ''}\""
        elif action == "replace":
            old = _oneline(args.get("old_text") or "") or "<missing old_text>"
            return f"~{target}: \"{old[:20]}\""
        elif action == "remove":
            old = _oneline(args.get("old_text") or "") or "<missing old_text>"
            return f"-{target}: \"{old[:20]}\""
        return action
    
    if tool_name == "send_message":
        target = args.get("target", "?")
        msg = _oneline(args.get("message", ""))
        if len(msg) > 20:
            msg = msg[:17] + "..."
        return f"to {target}: \"{msg}\""
    
    if tool_name == "terminal":
        cmd = _oneline(args.get("command", ""))
        return f"$ {_oneline(cmd[:50])}"
    
    # Generic handling
    key = _primary_args.get(tool_name)
    if not key:
        for fallback_key in ("query", "text", "command", "path", "name", "prompt", "code", "goal", "url"):
            if fallback_key in args:
                key = fallback_key
                break
    
    if not key or key not in args:
        return None
    
    value = args[key]
    if isinstance(value, list):
        value = value[0] if value else ""
    
    preview = _oneline(str(value))
    if not preview:
        return None
    if max_len > 0 and len(preview) > max_len:
        preview = preview[:max_len - 3] + "..."
    return preview


# =========================================================================
# Tool emoji mapping
# =========================================================================

_tool_emojis = {
    "browser_navigate": "🌐",
    "browser_snapshot": "📸",
    "browser_click": "👆",
    "browser_type": "⌨️",
    "browser_scroll": "📜",
    "browser_back": "↩️",
    "browser_press": "👇",
    "browser_get_images": "🖼️",
    "browser_vision": "👁️",
    "browser_console": "📟",
    "browser_cdp": "🔗",
    "web_search": "🔍",
    "web_extract": "📄",
    "read_file": "📖",
    "write_file": "✍️",
    "patch": "🔧",
    "search_files": "🔎",
    "terminal": "💻",
    "memory": "🧠",
    "session_search": "🔍",
    "send_message": "💬",
    "todo": "✅",
    "clarify": "❓",
    "skill_manage": "🔧",
    "kanban_show": "📋",
    "kanban_create": "📝",
    "kanban_complete": "✅",
    "kanban_block": "🚫",
    "cronjob": "⏰",
    "execute_code": "💻",
    "delegate_task": "🤝",
}

def get_tool_emoji(tool_name: str, default: str = "⚡") -> str:
    """Get the display emoji for a tool."""
    return _tool_emojis.get(tool_name, default)


# =========================================================================
# KawaiiSpinner - Animated spinner with kawaii faces
# =========================================================================

class KawaiiSpinner:
    """Animated spinner with kawaii faces for CLI feedback during tool execution."""

    SPINNERS = {
        'dots': ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'],
        'bounce': ['⠁', '⠂', '⠄', '⡀', '⢀', '⠠', '⠐', '⠈'],
        'arrows': ['←', '↖', '↑', '↗', '→', '↘', '↓', '↙'],
        'pulse': ['◜', '◠', '◝', '◞', '◡', '◟'],
        'sparkle': ['⁺', '˚', '*', '✧', '✦', '✧', '*', '˚'],
    }

    PROMETHEUS_WAITING = [
        "🔥", "🧬", "📜", "💻", "⚡", "🌱", "🔮", "🌀", "✨", "🌟"
    ]

    PROMETHEUS_THINKING = [
        "🤔", "💭", "🧠", "🔍", "⚙️", "🔧", "📊", "🔬", "💡", "🎯",
        "📝", "🔮", "🌀", "⚗️", "🧪", "🔭", "📡", "💫", "🌌", "🪐"
    ]

    THINKING_VERBS = [
        "pondering", "contemplating", "musing", "cogitating", "ruminating",
        "deliberating", "mulling", "reflecting", "processing", "reasoning",
        "analyzing", "computing", "synthesizing", "formulating", "brainstorming",
    ]

    def __init__(self, message: str = "", spinner_type: str = 'dots', print_fn=None):
        self.message = message
        self.spinner_frames = self.SPINNERS.get(spinner_type, self.SPINNERS['dots'])
        self.running = False
        self.thread = None
        self.frame_idx = 0
        self.start_time = None
        self.last_line_len = 0
        self._print_fn = print_fn
        self._out = sys.stdout

    def _write(self, text: str, end: str = '\n', flush: bool = False):
        """Write to the stdout captured at spinner creation time."""
        if self._print_fn is not None:
            try:
                self._print_fn(text)
            except Exception:
                pass
            return
        try:
            self._out.write(text + end)
            if flush:
                self._out.flush()
        except (ValueError, OSError):
            pass

    @property
    def _is_tty(self) -> bool:
        """Check if output is a real terminal."""
        try:
            return hasattr(self._out, 'isatty') and self._out.isatty()
        except (ValueError, OSError):
            return False

    def _animate(self):
        """Animation loop."""
        if not self._is_tty:
            self._write(f"  [tool] {self.message}", flush=True)
            while self.running:
                time.sleep(0.5)
            return

        import random
        waiting_faces = self.PROMETHEUS_WAITING
        thinking_faces = self.PROMETHEUS_THINKING
        
        while self.running:
            frame = self.spinner_frames[self.frame_idx % len(self.spinner_frames)]
            elapsed = time.time() - self.start_time
            
            # Alternate between waiting and thinking faces
            if self.frame_idx % 20 < 10:
                face = waiting_faces[self.frame_idx % len(waiting_faces)]
            else:
                face = thinking_faces[self.frame_idx % len(thinking_faces)]
            
            line = f"  {face} {frame} {self.message} ({elapsed:.1f}s)"
            pad = max(self.last_line_len - len(line), 0)
            self._write(f"\r{line}{' ' * pad}", end='', flush=True)
            self.last_line_len = len(line)
            self.frame_idx += 1
            time.sleep(0.12)

    def start(self):
        """Start the spinner animation."""
        if self.running:
            return
        self.running = True
        self.start_time = time.time()
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()

    def update_text(self, new_message: str):
        """Update the spinner message."""
        self.message = new_message

    def stop(self, final_message: str = None):
        """Stop the spinner animation."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.5)

        is_tty = self._is_tty
        if is_tty:
            blanks = ' ' * max(self.last_line_len + 5, 40)
            self._write(f"\r{blanks}\r", end='', flush=True)
        if final_message:
            elapsed = f" ({time.time() - self.start_time:.1f}s)" if self.start_time else ""
            if is_tty:
                self._write(f"  {final_message}", flush=True)
            else:
                self._write(f"  [done] {final_message}{elapsed}", flush=True)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False


# =========================================================================
# Tool message formatting
# =========================================================================

def _detect_tool_failure(tool_name: str, result: str | None) -> tuple[bool, str]:
    """Inspect a tool result string for signs of failure."""
    if result is None:
        return False, ""

    try:
        data = json.loads(result)
        if isinstance(data, dict):
            # For terminal/web tools: check success field first
            if "success" in data and not data.get("success"):
                return True, " [failed]"
            
            # For terminal tool: check exit_code
            if tool_name == "terminal":
                exit_code = data.get("exit_code")
                if exit_code is not None and exit_code != 0:
                    return True, " [error]"
                # Terminal commands with stderr but exit_code 0 are still successful
                return False, ""
            
            # For web tools: check error field
            if tool_name.startswith("web_") or tool_name.startswith("browser_"):
                if data.get("error"):
                    return True, " [error]"
            
            # For file tools: check error field only if no success indicator
            if tool_name.startswith("read_") or tool_name.startswith("write_") or tool_name.startswith("search_"):
                if data.get("error") and not data.get("content") and data.get("bytes_written") is None:
                    return True, " [error]"
            
            # Default: if there's a success field or specific success indicators, trust it
            if "success" in data and data.get("success"):
                return False, ""
            if "bytes_written" in data or "content" in data or "matches" in data:
                return False, ""
    except (json.JSONDecodeError, TypeError):
        pass

    lower = result[:500].lower()
    if '"error"' in lower or '"failed"' in lower or result.startswith("Error"):
        # Re-parse to check if error field has an actual value (not null/empty)
        try:
            data = json.loads(result)
            if isinstance(data, dict):
                err = data.get("error")
                # Only treat as error if error field has a truthy value
                if err:
                    return True, " [error]"
                # If error is null/None/empty, it's not a failure
                return False, ""
        except (json.JSONDecodeError, TypeError):
            # If we can't parse it, treat as error
            return True, " [error]"

    return False, ""


def get_cute_tool_message(
    tool_name: str, args: dict, duration: float, result: str | None = None,
) -> str:
    """Generate a formatted tool completion line for CLI.
    
    Format: ``| {emoji} {verb:9} {detail}  {duration}``
    """
    dur = f"{duration:.1f}s"
    is_failure, failure_suffix = _detect_tool_failure(tool_name, result)

    def _trunc(s, n=40):
        s = str(s)
        return (s[:n-3] + "...") if len(s) > n else s

    def _path(p, n=35):
        p = str(p)
        return ("..." + p[-(n-3):]) if len(p) > n else p

    emoji = get_tool_emoji(tool_name)
    preview = build_tool_preview(tool_name, args) or ""

    # Format based on tool type
    if tool_name.startswith("browser_"):
        verb = "browse"
        line = f"┊ {emoji} {verb:9} {preview}  {dur}"
    elif tool_name.startswith("web_"):
        verb = "web"
        line = f"┊ {emoji} {verb:9} {preview}  {dur}"
    elif tool_name == "read_file":
        line = f"┊ {emoji} read      {_path(args.get('path', ''))}  {dur}"
    elif tool_name == "write_file":
        line = f"┊ {emoji} write     {_path(args.get('path', ''))}  {dur}"
    elif tool_name == "terminal":
        line = f"┊ {emoji} $         {_trunc(args.get('command', ''), 42)}  {dur}"
    elif tool_name == "memory":
        line = f"┊ {emoji} memory    {preview}  {dur}"
    elif tool_name == "session_search":
        line = f"┊ {emoji} recall    {preview}  {dur}"
    elif tool_name == "todo":
        line = f"┊ {emoji} todo      {preview}  {dur}"
    elif tool_name == "send_message":
        line = f"┊ {emoji} message   {preview}  {dur}"
    elif tool_name == "clarify":
        line = f"┊ {emoji} clarify   {preview}  {dur}"
    elif tool_name == "skill_manage":
        line = f"┊ {emoji} skill     {preview}  {dur}"
    elif tool_name.startswith("kanban_"):
        line = f"┊ {emoji} kanban    {preview}  {dur}"
    else:
        verb = tool_name.replace("_", " ")[:9]
        line = f"┊ {emoji} {verb:9} {preview}  {dur}"

    if is_failure:
        line = f"{_RED}{line}{_ANSI_RESET}{failure_suffix}"
    
    return line


# =========================================================================
# Status message formatting
# =========================================================================

def format_thinking_message(verb: str = None) -> str:
    """Format a thinking status message."""
    if verb is None:
        import random
        verb = random.choice(KawaiiSpinner.THINKING_VERBS)
    face = random.choice(KawaiiSpinner.PROMETHEUS_THINKING)
    return f"  {face} {verb}..."


def format_status_message(status_type: str, **kwargs) -> str:
    """Format a status message based on type."""
    if status_type == "thinking":
        return format_thinking_message()
    elif status_type == "calling_tool":
        tool_name = kwargs.get("tool_name", "")
        tool_args = kwargs.get("tool_args", {})
        emoji = get_tool_emoji(tool_name)
        preview = build_tool_preview(tool_name, tool_args) or ""
        if preview:
            return f"  {emoji} calling {tool_name}: {preview}"
        return f"  {emoji} calling {tool_name}"
    elif status_type == "error":
        error = kwargs.get("error", "")
        return f"  {_RED}✖ error: {error}{_ANSI_RESET}"
    elif status_type == "idle":
        return ""
    return f"  {status_type}"
