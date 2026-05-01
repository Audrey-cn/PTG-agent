"""Clipboard image extraction for macOS, Windows, Linux, and WSL2."""

import base64
import logging
import os
import subprocess
import sys
from pathlib import Path

from prometheus.constants_core import is_wsl as _is_wsl

logger = logging.getLogger(__name__)


def save_clipboard_image(dest: Path) -> bool:
    """Extract an image from the system clipboard and save it as PNG."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        return _macos_save(dest)
    if sys.platform == "win32":
        return _windows_save(dest)
    return _linux_save(dest)


def has_clipboard_image() -> bool:
    """Quick check: does the clipboard currently contain an image?"""
    if sys.platform == "darwin":
        return _macos_has_image()
    if sys.platform == "win32":
        return _windows_has_image()
    if _is_wsl() and _wsl_has_image():
        return True
    if os.environ.get("WAYLAND_DISPLAY") and _wayland_has_image():
        return True
    return _xclip_has_image()


def _macos_save(dest: Path) -> bool:
    """Try pngpaste first (fast), fall back to osascript."""
    return _macos_pngpaste(dest) or _macos_osascript(dest)


def _macos_has_image() -> bool:
    """Check if macOS clipboard contains image data."""
    try:
        info = subprocess.run(
            ["osascript", "-e", "clipboard info"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return "«class PNGf»" in info.stdout or "«class TIFF»" in info.stdout
    except Exception:
        return False


def _macos_pngpaste(dest: Path) -> bool:
    """Use pngpaste (brew install pngpaste)."""
    try:
        r = subprocess.run(
            ["pngpaste", str(dest)],
            capture_output=True,
            timeout=3,
        )
        if r.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
            return True
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.debug("pngpaste failed: %s", e)
    return False


def _macos_osascript(dest: Path) -> bool:
    """Use osascript to extract PNG data from clipboard."""
    if not _macos_has_image():
        return False

    script = (
        "try\n"
        "  set imgData to the clipboard as «class PNGf»\n"
        f'  set f to open for access POSIX file "{dest}" with write permission\n'
        "  write imgData to f\n"
        "  close access f\n"
        "on error\n"
        '  return "fail"\n'
        "end try\n"
    )
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if (
            r.returncode == 0
            and "fail" not in r.stdout
            and dest.exists()
            and dest.stat().st_size > 0
        ):
            return True
    except Exception as e:
        logger.debug("osascript clipboard extract failed: %s", e)
    return False


_PS_CHECK_IMAGE = (
    "Add-Type -AssemblyName System.Windows.Forms;[System.Windows.Forms.Clipboard]::ContainsImage()"
)

_PS_EXTRACT_IMAGE = (
    "Add-Type -AssemblyName System.Windows.Forms;"
    "Add-Type -AssemblyName System.Drawing;"
    "$img = [System.Windows.Forms.Clipboard]::GetImage();"
    "if ($null -eq $img) { exit 1 }"
    "$ms = New-Object System.IO.MemoryStream;"
    "$img.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png);"
    "[System.Convert]::ToBase64String($ms.ToArray())"
)

_PS_CHECK_IMAGE_GET_CLIPBOARD = (
    "try { "
    "$img = Get-Clipboard -Format Image -ErrorAction Stop;"
    "if ($null -ne $img) { 'True' } else { 'False' }"
    "} catch { 'False' }"
)

_PS_EXTRACT_IMAGE_GET_CLIPBOARD = (
    "try { "
    "Add-Type -AssemblyName System.Drawing;"
    "Add-Type -AssemblyName PresentationCore;"
    "Add-Type -AssemblyName WindowsBase;"
    "$img = Get-Clipboard -Format Image -ErrorAction Stop;"
    "if ($null -eq $img) { exit 1 }"
    "$ms = New-Object System.IO.MemoryStream;"
    "if ($img -is [System.Drawing.Image]) {"
    "$img.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)"
    "} elseif ($img -is [System.Windows.Media.Imaging.BitmapSource]) {"
    "$enc = New-Object System.Windows.Media.Imaging.PngBitmapEncoder;"
    "$enc.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($img));"
    "$enc.Save($ms)"
    "} else { exit 2 }"
    "[System.Convert]::ToBase64String($ms.ToArray())"
    "} catch { exit 1 }"
)

_FILEDROP_IMAGE_EXTS = "'.png','.jpg','.jpeg','.gif','.webp','.bmp','.tiff','.tif'"

_PS_CHECK_FILEDROP_IMAGE = (
    "try { "
    "$files = Get-Clipboard -Format FileDropList -ErrorAction Stop;"
    f"$exts = @({_FILEDROP_IMAGE_EXTS});"
    "$hit = $files | Where-Object { $exts -contains ([System.IO.Path]::GetExtension($_).ToLowerInvariant()) } | Select-Object -First 1;"
    "if ($null -ne $hit) { 'True' } else { 'False' }"
    "} catch { 'False' }"
)

_PS_EXTRACT_FILEDROP_IMAGE = (
    "try { "
    "$files = Get-Clipboard -Format FileDropList -ErrorAction Stop;"
    f"$exts = @({_FILEDROP_IMAGE_EXTS});"
    "$hit = $files | Where-Object { $exts -contains ([System.IO.Path]::GetExtension($_).ToLowerInvariant()) } | Select-Object -First 1;"
    "if ($null -eq $hit) { exit 1 }"
    "[System.Convert]::ToBase64String([System.IO.File]::ReadAllBytes($hit))"
    "} catch { exit 1 }"
)

_POWERSHELL_HAS_IMAGE_SCRIPTS = (
    _PS_CHECK_IMAGE,
    _PS_CHECK_IMAGE_GET_CLIPBOARD,
    _PS_CHECK_FILEDROP_IMAGE,
)

_POWERSHELL_EXTRACT_IMAGE_SCRIPTS = (
    _PS_EXTRACT_IMAGE,
    _PS_EXTRACT_IMAGE_GET_CLIPBOARD,
    _PS_EXTRACT_FILEDROP_IMAGE,
)


def _run_powershell(exe: str, script: str, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        [exe, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _write_base64_image(dest: Path, b64_data: str) -> bool:
    image_bytes = base64.b64decode(b64_data, validate=True)
    dest.write_bytes(image_bytes)
    return dest.exists() and dest.stat().st_size > 0


def _powershell_has_image(exe: str, *, timeout: int, label: str) -> bool:
    for script in _POWERSHELL_HAS_IMAGE_SCRIPTS:
        try:
            r = _run_powershell(exe, script, timeout=timeout)
            if r.returncode == 0 and "True" in r.stdout:
                return True
        except FileNotFoundError:
            logger.debug("%s not found — clipboard unavailable", exe)
            return False
        except Exception as e:
            logger.debug("%s clipboard image check failed: %s", label, e)
    return False


def _powershell_save_image(exe: str, dest: Path, *, timeout: int, label: str) -> bool:
    for script in _POWERSHELL_EXTRACT_IMAGE_SCRIPTS:
        try:
            r = _run_powershell(exe, script, timeout=timeout)
            if r.returncode != 0:
                continue

            b64_data = r.stdout.strip()
            if not b64_data:
                continue

            if _write_base64_image(dest, b64_data):
                return True
        except FileNotFoundError:
            logger.debug("%s not found — clipboard unavailable", exe)
            return False
        except Exception as e:
            logger.debug("%s clipboard image extraction failed: %s", label, e)
            dest.unlink(missing_ok=True)
    return False


def _find_powershell() -> str | None:
    """Return the first available PowerShell executable, or None."""
    for name in ("powershell", "pwsh"):
        try:
            r = subprocess.run(
                [name, "-NoProfile", "-NonInteractive", "-Command", "echo ok"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if r.returncode == 0 and "ok" in r.stdout:
                return name
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return None


_ps_exe: str | None | bool = False


def _get_ps_exe() -> str | None:
    global _ps_exe
    if _ps_exe is False:
        _ps_exe = _find_powershell()
    return _ps_exe


def _windows_has_image() -> bool:
    """Check if the Windows clipboard contains an image."""
    ps = _get_ps_exe()
    if ps is None:
        return False
    return _powershell_has_image(ps, timeout=5, label="Windows")


def _windows_save(dest: Path) -> bool:
    """Extract clipboard image on native Windows via PowerShell → base64 PNG."""
    ps = _get_ps_exe()
    if ps is None:
        logger.debug("No PowerShell found — Windows clipboard image paste unavailable")
        return False
    return _powershell_save_image(ps, dest, timeout=15, label="Windows")


def _linux_save(dest: Path) -> bool:
    """Try clipboard backends in priority order: WSL → Wayland → X11."""
    if _is_wsl() and _wsl_save(dest):
        return True

    if os.environ.get("WAYLAND_DISPLAY") and _wayland_save(dest):
        return True

    return _xclip_save(dest)


def _wsl_has_image() -> bool:
    """Check if Windows clipboard has an image (via powershell.exe)."""
    return _powershell_has_image("powershell.exe", timeout=8, label="WSL")


def _wsl_save(dest: Path) -> bool:
    """Extract clipboard image via powershell.exe → base64 → decode to PNG."""
    return _powershell_save_image("powershell.exe", dest, timeout=15, label="WSL")


def _wayland_has_image() -> bool:
    """Check if Wayland clipboard has image content."""
    try:
        r = subprocess.run(
            ["wl-paste", "--list-types"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return r.returncode == 0 and any(t.startswith("image/") for t in r.stdout.splitlines())
    except FileNotFoundError:
        logger.debug("wl-paste not installed — Wayland clipboard unavailable")
    except Exception:
        pass
    return False


def _wayland_save(dest: Path) -> bool:
    """Use wl-paste to extract clipboard image (Wayland sessions)."""
    try:
        types_r = subprocess.run(
            ["wl-paste", "--list-types"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if types_r.returncode != 0:
            return False
        types = types_r.stdout.splitlines()

        mime = None
        for preferred in ("image/png", "image/jpeg", "image/bmp", "image/gif", "image/webp"):
            if preferred in types:
                mime = preferred
                break

        if not mime:
            return False

        with open(dest, "wb") as f:
            subprocess.run(
                ["wl-paste", "--type", mime],
                stdout=f,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=True,
            )

        if not dest.exists() or dest.stat().st_size == 0:
            dest.unlink(missing_ok=True)
            return False

        if mime == "image/bmp":
            return _convert_to_png(dest)

        return True

    except FileNotFoundError:
        logger.debug("wl-paste not installed — Wayland clipboard unavailable")
    except Exception as e:
        logger.debug("wl-paste clipboard extraction failed: %s", e)
        dest.unlink(missing_ok=True)
    return False


def _convert_to_png(path: Path) -> bool:
    """Convert an image file to PNG in-place (requires Pillow or ImageMagick)."""
    try:
        from PIL import Image

        img = Image.open(path)
        img.save(path, "PNG")
        return True
    except ImportError:
        pass
    except Exception as e:
        logger.debug("Pillow BMP→PNG conversion failed: %s", e)

    tmp = path.with_suffix(".bmp")
    try:
        path.rename(tmp)
        r = subprocess.run(
            ["convert", str(tmp), "png:" + str(path)],
            capture_output=True,
            timeout=5,
        )
        if r.returncode == 0 and path.exists() and path.stat().st_size > 0:
            tmp.unlink(missing_ok=True)
            return True
        else:
            tmp.rename(path)
    except FileNotFoundError:
        logger.debug("ImageMagick not installed — cannot convert BMP to PNG")
        if tmp.exists() and not path.exists():
            tmp.rename(path)
    except Exception as e:
        logger.debug("ImageMagick BMP→PNG conversion failed: %s", e)
        if tmp.exists() and not path.exists():
            tmp.rename(path)

    return path.exists() and path.stat().st_size > 0


def _xclip_has_image() -> bool:
    """Check if X11 clipboard has image content."""
    try:
        r = subprocess.run(
            ["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return r.returncode == 0 and "image/png" in r.stdout
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return False


def _xclip_save(dest: Path) -> bool:
    """Use xclip to extract clipboard image (X11 sessions)."""
    try:
        targets = subprocess.run(
            ["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if "image/png" not in targets.stdout:
            return False
    except FileNotFoundError:
        logger.debug("xclip not installed — X11 clipboard image paste unavailable")
        return False
    except Exception:
        return False

    try:
        with open(dest, "wb") as f:
            subprocess.run(
                ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"],
                stdout=f,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=True,
            )
        if dest.exists() and dest.stat().st_size > 0:
            return True
    except Exception as e:
        logger.debug("xclip image extraction failed: %s", e)
        dest.unlink(missing_ok=True)
    return False
