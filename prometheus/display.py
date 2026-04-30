
"""
Prometheus 史诗级显示系统
包含动态旋转动画、工具emoji映射、工具执行显示
"""
import sys
import time
import threading
import os


def _get_skin():
    """获取皮肤（懒加载避免循环依赖）"""
    try:
        from prometheus import skin_engine
        return skin_engine.get_active_skin()
    except Exception:
        return None


_TOOL_EMOJIS = {
    "stamp_seed": "🔥",
    "trace_seed": "🔍",
    "append_historical_note": "📜",
    "inspect_seed": "🔬",
    "list_stamps": "📋",
}


def get_tool_emoji(tool_name, default="⚡"):
    """获取工具的emoji"""
    skin = _get_skin()
    if skin and tool_name in skin.tool_emojis:
        return skin.tool_emojis[tool_name]
    return _TOOL_EMOJIS.get(tool_name, default)


def get_skin_tool_prefix():
    """获取工具前缀"""
    try:
        from prometheus import skin_engine
        return skin_engine.get_active_tool_prefix()
    except Exception:
        return "┊"


class KawaiiSpinner:
    """史诗级动态旋转器"""
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
        """获取等待时的颜文字表情"""
        return ["(🔥)", "(✦)", "(⚡)", "(✧)", "(★)"]

    @classmethod
    def get_thinking_faces(cls):
        """获取思考时的颜文字表情"""
        return ["(🔥)", "(⚡)", "(✦)", "(⌁)", "(✧)"]

    def _write(self, text, end="\n", flush=False):
        """安全写入输出"""
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
        """是否为终端输出"""
        try:
            return hasattr(self._out, "isatty") and self._out.isatty()
        except Exception:
            return False

    def start(self):
        """启动动画"""
        if self.running:
            return
        self.running = True
        self.start_time = time.time()
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()

    def _animate(self):
        """动画循环（简化版本）"""
        pass

    def stop(self, final_message=None):
        """停止动画"""
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
    """生成格式化的工具完成信息"""
    prefix = get_skin_tool_prefix()
    emoji = get_tool_emoji(tool_name)
    return "%s %s %s" % (prefix, emoji, tool_name)


def build_tool_preview(tool_name, args, max_len=None):
    """构建工具调用预览"""
    return None


def extract_edit_diff(tool_name, result=None, **kwargs):
    """从工具结果提取差异"""
    return None

