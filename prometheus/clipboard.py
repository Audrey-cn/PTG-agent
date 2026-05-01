from __future__ import annotations

import os
import subprocess
import sys


def _get_platform_commands() -> Dict[str, Tuple[str, ...]]:
    if sys.platform == "darwin":
        return {
            "copy": ("pbcopy",),
            "paste": ("pbpaste",),
        }
    elif sys.platform == "win32":
        return {
            "copy": ("clip",),
            "paste": ("powershell", "-command", "Get-Clipboard"),
        }
    else:
        return {
            "copy": ("xclip", "-selection", "clipboard"),
            "paste": ("xclip", "-selection", "clipboard", "-o"),
        }


def _is_command_available(command: str) -> bool:
    try:
        result = subprocess.run(
            ["which", command] if sys.platform != "win32" else ["where", command],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def _get_fallback_commands() -> Dict[str, Tuple[str, ...]]:
    if sys.platform == "darwin" or sys.platform == "win32":
        return {}
    else:
        if _is_command_available("xclip"):
            return {}
        if _is_command_available("xsel"):
            return {
                "copy": ("xsel", "--clipboard", "--input"),
                "paste": ("xsel", "--clipboard", "--output"),
            }
        return {}


def copy_to_clipboard(text: str) -> bool:
    if not text:
        return False
    commands = _get_platform_commands()
    copy_cmd = commands.get("copy")
    if not copy_cmd:
        fallback = _get_fallback_commands()
        copy_cmd = fallback.get("copy")
    if not copy_cmd:
        return False
    try:
        process = subprocess.Popen(
            copy_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        process.communicate(input=text.encode("utf-8"))
        return process.returncode == 0
    except Exception:
        return False


def paste_from_clipboard() -> str:
    commands = _get_platform_commands()
    paste_cmd = commands.get("paste")
    if not paste_cmd:
        fallback = _get_fallback_commands()
        paste_cmd = fallback.get("paste")
    if not paste_cmd:
        return ""
    try:
        result = subprocess.run(
            paste_cmd,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout
        return ""
    except Exception:
        return ""


def copy_image_to_clipboard(image_path: str) -> bool:
    if not os.path.exists(image_path):
        return False
    if sys.platform == "darwin":
        try:
            ext = os.path.splitext(image_path)[1].lower()
            if ext in (".png",):
                result = subprocess.run(
                    [
                        "osascript",
                        "-e",
                        f'set the clipboard to (read (POSIX file "{image_path}") as PNG picture)',
                    ],
                    capture_output=True,
                    text=True,
                )
                return result.returncode == 0
            elif ext in (".jpg", ".jpeg"):
                result = subprocess.run(
                    [
                        "osascript",
                        "-e",
                        f'set the clipboard to (read (POSIX file "{image_path}") as JPEG picture)',
                    ],
                    capture_output=True,
                    text=True,
                )
                return result.returncode == 0
            return False
        except Exception:
            return False
    elif sys.platform == "win32":
        try:
            subprocess.run(
                ["powershell", "-command", f"Set-Clipboard -Path '{image_path}'"],
                capture_output=True,
            )
            return True
        except Exception:
            return False
    else:
        try:
            if _is_command_available("xclip"):
                with open(image_path, "rb") as f:
                    image_data = f.read()
                ext = os.path.splitext(image_path)[1].lower()
                mime_type = "image/png" if ext == ".png" else "image/jpeg"
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-t", mime_type, "-i"],
                    input=image_data,
                    capture_output=True,
                )
                return result.returncode == 0
            return False
        except Exception:
            return False


def get_clipboard_content_type() -> str:
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["osascript", "-e", "clipboard info"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                info = result.stdout.lower()
                if "png" in info or "jpeg" in info or "gif" in info or "tiff" in info:
                    return "image"
                elif "string" in info or "text" in info or "utf8" in info:
                    return "text"
            return "unknown"
        except Exception:
            return "unknown"
    elif sys.platform == "win32":
        try:
            result = subprocess.run(
                ["powershell", "-command", "Get-Clipboard -Format Image"],
                capture_output=True,
            )
            if result.returncode == 0 and result.stdout:
                return "image"
            return "text"
        except Exception:
            return "unknown"
    else:
        text = paste_from_clipboard()
        if text:
            return "text"
        return "unknown"


def is_clipboard_available() -> bool:
    commands = _get_platform_commands()
    copy_cmd = commands.get("copy")
    if copy_cmd and _is_command_available(copy_cmd[0]):
        return True
    fallback = _get_fallback_commands()
    copy_cmd = fallback.get("copy")
    return bool(copy_cmd and _is_command_available(copy_cmd[0]))


def clear_clipboard() -> bool:
    return copy_to_clipboard("")
