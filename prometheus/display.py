
"""
Prometheus 史诗级显示系统
"""

import sys
import time
import threading
import os


def _get_skin():
    try:
        from prometheus import skin_engine
        return skin_engine.get_active_skin()
    except Exception:
        return None


def get_tool_emoji(tool_name, default="⚡"):
    skin = _get_skin()
    if skin:
        override = skin.tool_emojis.get(tool_name)
        if override:
            return override
    try:
        from prometheus.tools.registry import registry
        emoji = registry.get_emoji(tool_name, default="")
        if emoji:
            return emoji
    except Exception:
        pass
    return default


def get_skin_tool_prefix():
    try:
        from prometheus import skin_engine
        return skin_engine.get_tool_prefix()
    except Exception:
        return "┊"


class KawaiiSpinner:
    SPINNERS = {
        "dots": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
    }

    def __init__(self, message="", spinner_type="dots", print_fn=None):
        self.message = message
        self.spinner_frames = self.SPINNERS.get(spinner_type, self.SPINNERS["dots"])
        self.running = False
        self.thread = None
        self.frame_idx = 0
        self.start_time = None
        self.last_line_len = 0
        self._print_fn = print_fn
        self._out = sys.stdout

    @classmethod
    def get_waiting_faces(cls):
        try:
            skin = _get_skin()
            if skin:
                faces = skin.spinner.get("waiting_faces", [])
                if faces:
                    return faces
        except Exception:
            pass
        return ["(🔥)", "(✦)", "(⚡)", "(✧)", "(★)"]

    @classmethod
    def get_thinking_faces(cls):
        try:
            skin = _get_skin()
            if skin:
                faces = skin.spinner.get("thinking_faces", [])
                if faces:
                    return faces
        except Exception:
            pass
        return ["(🔥)", "(⚡)", "(✦)", "(⌁)", "(✧)"]

    @classmethod
    def get_thinking_verbs(cls):
        try:
            skin = _get_skin()
            if skin:
                verbs = skin.spinner.get("thinking_verbs", [])
                if verbs:
                    return verbs
        except Exception:
            pass
        return ["forging wisdom"]

    def _write(self, text, end="\n", flush=False):
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
        except Exception:
            pass

    @property
    def _is_tty(self):
        try:
            return hasattr(self._out, "isatty") and self._out.isatty()
        except Exception:
            return False

    def start(self):
        if self.running:
            return
        self.running = True
        self.start_time = time.time()
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()

    def _animate(self):
        if not self._is_tty:
            self._write(f"  [tool] {self.message}", flush=True)
            while self.running:
                time.sleep(0.5)
            return

    def stop(self, final_message=None):
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.5)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False


def get_cute_tool_message(tool_name, args, duration, result=None):
    prefix = get_skin_tool_prefix()
    emoji = get_tool_emoji(tool_name)
    return f"{prefix} {emoji} {tool_name}"


def build_tool_preview(tool_name, args, max_len=None):
    return None


def extract_edit_diff(tool_name, result=None, **kwargs):
    return None

