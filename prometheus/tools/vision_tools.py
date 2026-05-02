#!/usr/bin/env python3
"""Vision Tools Module."""

from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from collections.abc import Awaitable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from prometheus.agent.auxiliary_client import async_call_llm, extract_content_or_reasoning
from prometheus.constants_core import get_prometheus_dir
from prometheus.tools.debug_helpers import DebugSession
from prometheus.tools.website_policy import check_website_access

logger = logging.getLogger(__name__)

_debug = DebugSession("vision_tools", env_var="VISION_TOOLS_DEBUG")


def _resolve_download_timeout() -> float:
    env_val = os.getenv("PROMETHEUS_VISION_DOWNLOAD_TIMEOUT", "").strip()
    if env_val:
        try:
            return float(env_val)
        except ValueError:
            pass
    try:
        from prometheus.config import PrometheusConfig

        cfg = PrometheusConfig.load()
        val = cfg.get("auxiliary.vision.download_timeout")
        if val is not None:
            return float(val)
    except Exception:
        pass
    return 30.0


_VISION_DOWNLOAD_TIMEOUT = _resolve_download_timeout()

_VISION_MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024


def _validate_image_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False

    if not url.startswith(("http://", "https://")):
        return False

    parsed = urlparse(url)
    if not parsed.netloc:
        return False

    from prometheus.tools.security.url_safety import is_safe_url

    return is_safe_url(url)


def _detect_image_mime_type(image_path: Path) -> str | None:
    """Return a MIME type when the file looks like a supported image."""
    with image_path.open("rb") as f:
        header = f.read(64)

    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if header.startswith(b"BM"):
        return "image/bmp"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    if image_path.suffix.lower() == ".svg":
        head = image_path.read_text(encoding="utf-8", errors="ignore")[:4096].lower()
        if "<svg" in head:
            return "image/svg+xml"
    return None


async def _download_image(image_url: str, destination: Path, max_retries: int = 3) -> Path:
    """Download an image from a URL to a local destination (async) with retry logic."""
    import asyncio

    destination.parent.mkdir(parents=True, exist_ok=True)

    async def _ssrf_redirect_guard(response):
        if response.is_redirect and response.next_request:
            redirect_url = str(response.next_request.url)
            from prometheus.tools.security.url_safety import is_safe_url

            if not is_safe_url(redirect_url):
                raise ValueError(f"Blocked redirect to private/internal address: {redirect_url}")

    last_error = None
    for attempt in range(max_retries):
        try:
            blocked = check_website_access(image_url)
            if blocked:
                raise PermissionError(blocked["message"])

            async with httpx.AsyncClient(
                timeout=_VISION_DOWNLOAD_TIMEOUT,
                follow_redirects=True,
                event_hooks={"response": [_ssrf_redirect_guard]},
            ) as client:
                response = await client.get(
                    image_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Accept": "image/*,*/*;q=0.8",
                    },
                )
                response.raise_for_status()

                cl = response.headers.get("content-length")
                if cl and int(cl) > _VISION_MAX_DOWNLOAD_BYTES:
                    raise ValueError(
                        f"Image too large ({int(cl)} bytes, max {_VISION_MAX_DOWNLOAD_BYTES})"
                    )

                final_url = str(response.url)
                blocked = check_website_access(final_url)
                if blocked:
                    raise PermissionError(blocked["message"])

                body = response.content
                if len(body) > _VISION_MAX_DOWNLOAD_BYTES:
                    raise ValueError(
                        f"Image too large ({len(body)} bytes, max {_VISION_MAX_DOWNLOAD_BYTES})"
                    )
                destination.write_bytes(body)

            return destination
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = 2 ** (attempt + 1)
                logger.warning(
                    "Image download failed (attempt %s/%s): %s",
                    attempt + 1,
                    max_retries,
                    str(e)[:50],
                )
                logger.warning("Retrying in %ss...", wait_time)
                await asyncio.sleep(wait_time)
            else:
                logger.error(
                    "Image download failed after %s attempts: %s",
                    max_retries,
                    str(e)[:100],
                    exc_info=True,
                )

    if last_error is None:
        raise RuntimeError(
            f"_download_image exited retry loop without attempting (max_retries={max_retries})"
        )
    raise last_error


def _determine_mime_type(image_path: Path) -> str:
    extension = image_path.suffix.lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }
    return mime_types.get(extension, "image/jpeg")


def _image_to_base64_data_url(image_path: Path, mime_type: str | None = None) -> str:
    data = image_path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    mime = mime_type or _determine_mime_type(image_path)
    data_url = f"data:{mime};base64,{encoded}"
    return data_url


_MAX_BASE64_BYTES = 20 * 1024 * 1024
_RESIZE_TARGET_BYTES = 5 * 1024 * 1024


def _is_image_size_error(error: Exception) -> bool:
    """Detect if an API error is related to image or payload size."""
    err_str = str(error).lower()
    return any(
        hint in err_str
        for hint in (
            "too large",
            "payload",
            "413",
            "content_too_large",
            "request_too_large",
            "image_url",
            "invalid_request",
            "exceeds",
            "size limit",
        )
    )


def _resize_image_for_vision(
    image_path: Path, mime_type: str | None = None, max_base64_bytes: int = _RESIZE_TARGET_BYTES
) -> str:
    """Convert an image to a base64 data URL, auto-resizing if too large."""
    file_size = image_path.stat().st_size
    estimated_b64 = (file_size * 4) // 3 + 100
    if estimated_b64 <= max_base64_bytes:
        data_url = _image_to_base64_data_url(image_path, mime_type=mime_type)
        if len(data_url) <= max_base64_bytes:
            return data_url
    else:
        data_url = None

    try:
        import io as _io

        from PIL import Image
    except ImportError:
        logger.info("Pillow not installed — cannot auto-resize oversized image")
        if data_url is None:
            data_url = _image_to_base64_data_url(image_path, mime_type=mime_type)
        return data_url

    logger.info(
        "Image file is %.1f MB (estimated base64 %.1f MB, limit %.1f MB), auto-resizing...",
        file_size / (1024 * 1024),
        estimated_b64 / (1024 * 1024),
        max_base64_bytes / (1024 * 1024),
    )

    mime = mime_type or _determine_mime_type(image_path)
    pil_format = "PNG" if mime == "image/png" else "JPEG"
    out_mime = "image/png" if pil_format == "PNG" else "image/jpeg"

    try:
        img = Image.open(image_path)
    except Exception as exc:
        logger.info("Pillow cannot open image for resizing: %s", exc)
        if data_url is None:
            data_url = _image_to_base64_data_url(image_path, mime_type=mime_type)
        return data_url

    if pil_format == "JPEG" and img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    quality_steps = (85, 70, 50) if pil_format == "JPEG" else (None,)
    prev_dims = (img.width, img.height)
    candidate = None

    for attempt in range(5):
        if attempt > 0:
            scale = 0.5
            new_w = max(int(img.width * scale), 64)
            new_h = max(int(img.height * scale), 64)
            if new_w == 64 and img.width > 0:
                effective_scale = 64 / img.width
                new_h = max(int(img.height * effective_scale), 64)
            elif new_h == 64 and img.height > 0:
                effective_scale = 64 / img.height
                new_w = max(int(img.width * effective_scale), 64)
            if (new_w, new_h) == prev_dims:
                break
            img = img.resize((new_w, new_h), Image.LANCZOS)
            prev_dims = (new_w, new_h)
            logger.info("Resized to %dx%d (attempt %d)", new_w, new_h, attempt)

        for q in quality_steps:
            buf = _io.BytesIO()
            save_kwargs = {"format": pil_format}
            if q is not None:
                save_kwargs["quality"] = q
            img.save(buf, **save_kwargs)
            encoded = base64.b64encode(buf.getvalue()).decode("ascii")
            candidate = f"data:{out_mime};base64,{encoded}"
            if len(candidate) <= max_base64_bytes:
                logger.info(
                    "Auto-resized image fits: %.1f MB (quality=%s, %dx%d)",
                    len(candidate) / (1024 * 1024),
                    q,
                    img.width,
                    img.height,
                )
                return candidate

    if candidate is not None:
        logger.warning(
            "Auto-resize could not fit image under %.1f MB (best: %.1f MB)",
            max_base64_bytes / (1024 * 1024),
            len(candidate) / (1024 * 1024),
        )
        return candidate

    return data_url or _image_to_base64_data_url(image_path, mime_type=mime_type)


async def vision_analyze_tool(
    image_url: str,
    user_prompt: str,
    model: str = None,
) -> str:
    """Analyze an image from a URL or local file path using vision AI."""
    debug_call_data = {
        "parameters": {
            "image_url": image_url,
            "user_prompt": user_prompt[:200] + "..." if len(user_prompt) > 200 else user_prompt,
            "model": model,
        },
        "error": None,
        "success": False,
        "analysis_length": 0,
        "model_used": model,
        "image_size_bytes": 0,
    }

    temp_image_path = None
    should_cleanup = True
    detected_mime_type = None

    try:
        from prometheus.tools.security.interrupt import is_interrupted

        if is_interrupted():
            return tool_error("Interrupted", success=False)

        logger.info("Analyzing image: %s", image_url[:60])
        logger.info("User prompt: %s", user_prompt[:100])

        resolved_url = image_url
        if resolved_url.startswith("file://"):
            resolved_url = resolved_url[len("file://") :]
        local_path = Path(os.path.expanduser(resolved_url))
        if local_path.is_file():
            logger.info("Using local image file: %s", image_url)
            temp_image_path = local_path
            should_cleanup = False
        elif _validate_image_url(image_url):
            blocked = check_website_access(image_url)
            if blocked:
                raise PermissionError(blocked["message"])
            logger.info("Downloading image from URL...")
            temp_dir = get_prometheus_dir("cache/vision", "temp_vision_images")
            temp_image_path = temp_dir / f"temp_image_{uuid.uuid4()}.jpg"
            await _download_image(image_url, temp_image_path)
            should_cleanup = True
        else:
            raise ValueError(
                "Invalid image source. Provide an HTTP/HTTPS URL or a valid local file path."
            )

        image_size_bytes = temp_image_path.stat().st_size
        image_size_kb = image_size_bytes / 1024
        logger.info("Image ready (%.1f KB)", image_size_kb)

        detected_mime_type = _detect_image_mime_type(temp_image_path)
        if not detected_mime_type:
            raise ValueError("Only real image files are supported for vision analysis.")

        logger.info("Converting image to base64...")
        image_data_url = _image_to_base64_data_url(temp_image_path, mime_type=detected_mime_type)
        data_size_kb = len(image_data_url) / 1024
        logger.info("Image converted to base64 (%.1f KB)", data_size_kb)

        if len(image_data_url) > _MAX_BASE64_BYTES:
            image_data_url = _resize_image_for_vision(temp_image_path, mime_type=detected_mime_type)
            if len(image_data_url) > _MAX_BASE64_BYTES:
                raise ValueError(
                    f"Image too large for vision API: base64 payload is "
                    f"{len(image_data_url) / (1024 * 1024):.1f} MB "
                    f"(limit {_MAX_BASE64_BYTES / (1024 * 1024):.0f} MB) "
                    f"even after resizing. "
                    f"Install Pillow (`pip install Pillow`) for better auto-resize, "
                    f"or compress the image manually."
                )

        debug_call_data["image_size_bytes"] = image_size_bytes

        comprehensive_prompt = user_prompt

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": comprehensive_prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        ]

        logger.info("Processing image with vision model...")

        vision_timeout = 120.0
        vision_temperature = 0.1
        try:
            from prometheus.config import PrometheusConfig

            _cfg = PrometheusConfig.load()
            _vision_cfg = _cfg.get("auxiliary.vision", default={})
            _vt = _vision_cfg.get("timeout")
            if _vt is not None:
                vision_timeout = float(_vt)
            _vtemp = _vision_cfg.get("temperature")
            if _vtemp is not None:
                vision_temperature = float(_vtemp)
        except Exception:
            pass
        call_kwargs = {
            "task": "vision",
            "messages": messages,
            "temperature": vision_temperature,
            "max_tokens": 2000,
            "timeout": vision_timeout,
        }
        if model:
            call_kwargs["model"] = model
        try:
            response = await async_call_llm(**call_kwargs)
        except Exception as _api_err:
            if _is_image_size_error(_api_err) and len(image_data_url) > _RESIZE_TARGET_BYTES:
                logger.info(
                    "API rejected image (%.1f MB, likely too large); "
                    "auto-resizing to ~%.0f MB and retrying...",
                    len(image_data_url) / (1024 * 1024),
                    _RESIZE_TARGET_BYTES / (1024 * 1024),
                )
                image_data_url = _resize_image_for_vision(
                    temp_image_path, mime_type=detected_mime_type
                )
                messages[0]["content"][1]["image_url"]["url"] = image_data_url
                response = await async_call_llm(**call_kwargs)
            else:
                raise

        analysis = extract_content_or_reasoning(response)

        if not analysis:
            logger.warning("Vision LLM returned empty content, retrying once")
            response = await async_call_llm(**call_kwargs)
            analysis = extract_content_or_reasoning(response)

        analysis_length = len(analysis)

        logger.info("Image analysis completed (%s characters)", analysis_length)

        result = {
            "success": True,
            "analysis": analysis
            or "There was a problem with the request and the image could not be analyzed.",
        }

        debug_call_data["success"] = True
        debug_call_data["analysis_length"] = analysis_length

        _debug.log_call("vision_analyze_tool", debug_call_data)
        _debug.save()

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        error_msg = f"Error analyzing image: {str(e)}"
        logger.error("%s", error_msg, exc_info=True)

        err_str = str(e).lower()
        if any(
            hint in err_str
            for hint in (
                "402",
                "insufficient",
                "payment required",
                "credits",
                "billing",
            )
        ):
            analysis = (
                "Insufficient credits or payment required. Please top up your "
                f"API provider account and try again. Error: {e}"
            )
        elif any(
            hint in err_str
            for hint in (
                "does not support",
                "not support image",
                "content_policy",
                "multimodal",
                "unrecognized request argument",
                "image input",
            )
        ):
            analysis = (
                f"{model} does not support vision or our request was not "
                f"accepted by the server. Error: {e}"
            )
        elif "invalid_request" in err_str or "image_url" in err_str:
            analysis = (
                "The vision API rejected the image. This can happen when the "
                "image is in an unsupported format, corrupted, or still too "
                "large after auto-resize. Try a smaller JPEG/PNG and retry. "
                f"Error: {e}"
            )
        else:
            analysis = (
                "There was a problem with the request and the image could not "
                f"be analyzed. Error: {e}"
            )

        result = {
            "success": False,
            "error": error_msg,
            "analysis": analysis,
        }

        debug_call_data["error"] = error_msg
        _debug.log_call("vision_analyze_tool", debug_call_data)
        _debug.save()

        return json.dumps(result, indent=2, ensure_ascii=False)

    finally:
        if should_cleanup and temp_image_path and temp_image_path.exists():
            try:
                temp_image_path.unlink()
                logger.debug("Cleaned up temporary image file")
            except Exception as cleanup_error:
                logger.warning("Could not delete temporary file: %s", cleanup_error, exc_info=True)


def check_vision_requirements() -> bool:
    """Check if the configured runtime vision path can resolve a client."""
    try:
        from prometheus.agent.auxiliary_client import resolve_vision_provider_client

        _provider, client, _model = resolve_vision_provider_client()
        return client is not None
    except Exception:
        return False


if __name__ == "__main__":
    print("👁️ Vision Tools Module")
    print("=" * 40)

    api_available = check_vision_requirements()

    if not api_available:
        print("❌ No auxiliary vision model available")
        print(
            "Configure a supported multimodal backend (OpenRouter, Nous, Codex, Anthropic, or a custom OpenAI-compatible endpoint)."
        )
        exit(1)
    else:
        print("✅ Vision model available")

    print("🛠️ Vision tools ready for use!")

    if _debug.active:
        print(f"🐛 Debug mode ENABLED - Session ID: {_debug.session_id}")
        print(f"   Debug logs will be saved to: ./logs/vision_tools_debug_{_debug.session_id}.json")
    else:
        print("🐛 Debug mode disabled (set VISION_TOOLS_DEBUG=true to enable)")

    print("\nBasic usage:")
    print("  from vision_tools import vision_analyze_tool")
    print("  import asyncio")
    print("")
    print("  async def main():")
    print("      result = await vision_analyze_tool(")
    print("          image_url='https://example.com/image.jpg',")
    print("          user_prompt='What do you see in this image?'")
    print("      )")
    print("      print(result)")
    print("  asyncio.run(main())")

    print("\nExample prompts:")
    print("  - 'What architectural style is this building?'")
    print("  - 'Describe the emotions and mood in this image'")
    print("  - 'What text can you read in this image?'")
    print("  - 'Identify any safety hazards visible'")
    print("  - 'What products or brands are shown?'")

    print("\nDebug mode:")
    print("  # Enable debug logging")
    print("  export VISION_TOOLS_DEBUG=true")
    print("  # Debug logs capture all vision analysis calls and results")
    print("  # Logs saved to: ./logs/vision_tools_debug_UUID.json")


from prometheus.tools.security.registry import registry, tool_error

VISION_ANALYZE_SCHEMA = {
    "name": "vision_analyze",
    "description": (
        "Inspect an image from a URL, file path, or tool output when you need "
        "closer detail than what's visible in the conversation. If the user's "
        "image is already attached to the conversation and you can see it, "
        "just answer directly — only call this tool for images referenced by "
        "URL/path, images returned inside other tool results (browser "
        "screenshots, search thumbnails), or when you need a deeper look at "
        "a specific region the main model's vision may have missed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "image_url": {
                "type": "string",
                "description": "Image URL (http/https) or local file path to analyze.",
            },
            "question": {
                "type": "string",
                "description": "Your specific question or request about the image to resolve. The AI will automatically provide a complete image description AND answer your specific question.",
            },
        },
        "required": ["image_url", "question"],
    },
}


def _handle_vision_analyze(args: dict[str, Any], **kw: Any) -> Awaitable[str]:
    image_url = args.get("image_url", "")
    question = args.get("question", "")
    full_prompt = (
        "Fully describe and explain everything about this image, then answer the "
        f"following question:\n\n{question}"
    )
    model = os.getenv("AUXILIARY_VISION_MODEL", "").strip() or None
    return vision_analyze_tool(image_url, full_prompt, model)


registry.register(
    name="vision_analyze",
    toolset="vision",
    schema=VISION_ANALYZE_SCHEMA,
    handler=_handle_vision_analyze,
    check_fn=check_vision_requirements,
    is_async=True,
    emoji="👁️",
)
