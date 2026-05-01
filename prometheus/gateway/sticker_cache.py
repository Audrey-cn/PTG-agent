"""Sticker description cache for messaging platforms."""

import json
import time
from pathlib import Path


def _get_sticker_cache_path() -> Path:
    from prometheus.config import get_prometheus_home

    return get_prometheus_home() / "sticker_cache.json"


# Vision prompt for describing stickers -- concise to save tokens
STICKER_VISION_PROMPT = (
    "Describe this sticker in 1-2 sentences. Focus on what it depicts -- "
    "character, action, emotion. Be concise and objective."
)


def _load_cache() -> dict:
    """Load sticker cache from disk."""
    cache_path = _get_sticker_cache_path()
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    """Save sticker cache to disk."""
    cache_path = _get_sticker_cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def get_cached_description(file_unique_id: str) -> dict | None:
    """Look up a cached sticker description.

    Returns: dict with keys {description, emoji, set_name, cached_at} or None.
    """
    cache = _load_cache()
    return cache.get(file_unique_id)


def cache_sticker_description(
    file_unique_id: str,
    description: str,
    emoji: str = "",
    set_name: str = "",
) -> None:
    """Store a sticker description in cache.

    Args:
        file_unique_id: Stable sticker identifier.
        description: Vision-generated description text.
        emoji: Associated emoji (e.g. "😀").
        set_name: Sticker set name if available.
    """
    cache = _load_cache()
    cache[file_unique_id] = {
        "description": description,
        "emoji": emoji,
        "set_name": set_name,
        "cached_at": time.time(),
    }
    _save_cache(cache)


def build_sticker_injection(
    description: str,
    emoji: str = "",
    set_name: str = "",
) -> str:
    """Build warm-style injection text for sticker description.

    Returns string like:
      [The user sent a sticker 😀 from "MyPack"~ It shows: "A cat waving" (=^.w.^=)]
    """
    context = ""
    if set_name and emoji:
        context = f' {emoji} from "{set_name}"'
    elif emoji:
        context = f" {emoji}"

    return f'[The user sent a sticker{context}~ It shows: "{description}" (=^.w.^=)]'


def build_animated_sticker_injection(emoji: str = "") -> str:
    """Build injection text for animated/video stickers we can't analyze."""
    if emoji:
        return (
            f"[The user sent an animated sticker {emoji}~ "
            f"I can't see animated ones yet, but the emoji suggests: {emoji}]"
        )
    return "[The user sent an animated sticker~ I can't see animated ones yet]"
