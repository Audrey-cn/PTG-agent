"""Routing helpers for inbound user-attached images."""

from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


_VALID_MODES = frozenset({"auto", "native", "text"})


def _coerce_mode(raw: Any) -> str:
    """Normalize a config value into one of the valid modes."""
    if not isinstance(raw, str):
        return "auto"
    val = raw.strip().lower()
    if val in _VALID_MODES:
        return val
    return "auto"


def _explicit_aux_vision_override(cfg: dict[str, Any] | None) -> bool:
    """True when the user configured a specific auxiliary vision backend.

    An explicit override means the user *wants* the text pipeline (they're
    paying for a dedicated vision model), so we don't silently bypass it.
    """
    if not isinstance(cfg, dict):
        return False
    aux = cfg.get("auxiliary") or {}
    if not isinstance(aux, dict):
        return False
    vision = aux.get("vision") or {}
    if not isinstance(vision, dict):
        return False

    provider = str(vision.get("provider") or "").strip().lower()
    model = str(vision.get("model") or "").strip()
    base_url = str(vision.get("base_url") or "").strip()

    return not (provider in ("", "auto") and not model and not base_url)


def _lookup_supports_vision(provider: str, model: str) -> bool | None:
    """Return True/False if we can resolve caps, None if unknown."""
    if not provider or not model:
        return None
    try:
        from prometheus.agent.models_dev import get_model_capabilities

        caps = get_model_capabilities(provider, model)
    except Exception as exc:
        logger.debug("image_routing: caps lookup failed for %s:%s — %s", provider, model, exc)
        return None
    if caps is None:
        return None
    return bool(caps.supports_vision)


def decide_image_input_mode(
    provider: str,
    model: str,
    cfg: dict[str, Any] | None,
) -> str:
    """Return ``"native"`` or ``"text"`` for the given turn.

    Args:
      provider: active inference provider ID (e.g. ``"anthropic"``, ``"openrouter"``).
      model:    active model slug as it would be sent to the provider.
      cfg:      loaded config.yaml dict, or None. When None, behaves as auto.
    """
    mode_cfg = "auto"
    if isinstance(cfg, dict):
        agent_cfg = cfg.get("agent") or {}
        if isinstance(agent_cfg, dict):
            mode_cfg = _coerce_mode(agent_cfg.get("image_input_mode"))

    if mode_cfg == "native":
        return "native"
    if mode_cfg == "text":
        return "text"

    if _explicit_aux_vision_override(cfg):
        return "text"

    supports = _lookup_supports_vision(provider, model)
    if supports is True:
        return "native"
    return "text"


# Image size handling is REACTIVE rather than proactive: we attempt native
# attachment at full size regardless of provider, and rely on
# ``run_agent._try_shrink_image_parts_in_messages`` to shrink + retry if
# the provider rejects the request (e.g. Anthropic's hard 5 MB per-image
# ceiling returned as HTTP 400 "image exceeds 5 MB maximum").
#
# Why reactive: our knowledge of provider ceilings is partial and evolving
# (OpenAI accepts 49 MB+, Anthropic 5 MB, Gemini 100 MB, others unknown).
# A proactive per-provider table would be stale the moment a provider raises
# or lowers its limit, and silently degrading quality for users on providers
# that would have accepted the full image is the worse failure mode.
# The shrink-on-reject path loses 1 API call + maybe 1s of Pillow work when
# it fires, which is cheaper than permanent quality loss.


def _guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    if mime and mime.startswith("image/"):
        return mime
    suffix = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }.get(suffix, "image/jpeg")


def _file_to_data_url(path: Path) -> str | None:
    """Encode a local image as a base64 data URL at its native size.

    Size limits are NOT enforced here — the agent retry loop
    (``run_agent._try_shrink_image_parts_in_messages``) shrinks on the
    provider's first rejection. Keeping this simple means providers that
    accept large images (OpenAI 49 MB+, Gemini 100 MB) don't pay a silent
    quality tax just because one other provider is stricter.

    Returns None only if the file can't be read (missing, permission
    denied, etc.); the caller reports those paths in ``skipped``.
    """
    try:
        raw = path.read_bytes()
    except Exception as exc:
        logger.warning("image_routing: failed to read %s — %s", path, exc)
        return None
    mime = _guess_mime(path)
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def build_native_content_parts(
    user_text: str,
    image_paths: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Build an OpenAI-style ``content`` list for a user turn.

    Shape:
      [{"type": "text", "text": "..."},
       {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
       ...]

    Images are attached at their native size. If a provider rejects the
    request because an image is too large (e.g. Anthropic's 5 MB per-image
    ceiling), the agent's retry loop transparently shrinks and retries
    once — see ``run_agent._try_shrink_image_parts_in_messages``.

    Returns (content_parts, skipped_paths). Skipped paths are files that
    couldn't be read from disk.
    """
    parts: list[dict[str, Any]] = []
    skipped: list[str] = []

    text = (user_text or "").strip()
    if text:
        parts.append({"type": "text", "text": text})

    for raw_path in image_paths:
        p = Path(raw_path)
        if not p.exists() or not p.is_file():
            skipped.append(str(raw_path))
            continue
        data_url = _file_to_data_url(p)
        if not data_url:
            skipped.append(str(raw_path))
            continue
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": data_url},
            }
        )

    if not text and any(p.get("type") == "image_url" for p in parts):
        parts.insert(0, {"type": "text", "text": "What do you see in this image?"})

    return parts, skipped


__all__ = [
    "decide_image_input_mode",
    "build_native_content_parts",
]
