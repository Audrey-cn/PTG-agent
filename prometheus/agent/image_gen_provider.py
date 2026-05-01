"""Image Generation Provider ABC."""

from __future__ import annotations

import abc
import base64
import datetime
import logging
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


VALID_ASPECT_RATIOS: tuple[str, ...] = ("landscape", "square", "portrait")
DEFAULT_ASPECT_RATIO = "landscape"


# ---------------------------------------------------------------------------
# ABC
# ---------------------------------------------------------------------------


class ImageGenProvider(abc.ABC):
    """Abstract base class for an image generation backend.

    Subclasses must implement :meth:`generate`. Everything else has sane
    defaults — override only what your provider needs.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Stable short identifier used in ``image_gen.provider`` config.

        Lowercase, no spaces. Examples: ``fal``, ``openai``, ``replicate``.
        """

    @property
    def display_name(self) -> str:
        """Human-readable label shown in ``prometheus tools``. Defaults to ``name.title()``."""
        return self.name.title()

    def is_available(self) -> bool:
        """Return True when this provider can service calls.

        Typically checks for a required API key. Default: True
        (providers with no external dependencies are always available).
        """
        return True

    def list_models(self) -> list[dict[str, Any]]:
        """Return catalog entries for ``prometheus tools`` model picker.

        Each entry::

            {
                "id": "gpt-image-1.5",               # required
                "display": "GPT Image 1.5",          # optional; defaults to id
                "speed": "~10s",                     # optional
                "strengths": "...",                  # optional
                "price": "$...",                     # optional
            }

        Default: empty list (provider has no user-selectable models).
        """
        return []

    def get_setup_schema(self) -> dict[str, Any]:
        """Return provider metadata for the ``prometheus tools`` picker.

        Used by ``tools_config.py`` to inject this provider as a row in
        the Image Generation provider list. Shape::

            {
                "name": "OpenAI",                     # picker label
                "badge": "paid",                      # optional short tag
                "tag": "One-line description...",     # optional subtitle
                "env_vars": [                         # keys to prompt for
                    {"key": "OPENAI_API_KEY",
                     "prompt": "OpenAI API key",
                     "url": "https://platform.openai.com/api-keys"},
                ],
            }

        Default: minimal entry derived from ``display_name``. Override to
        expose API key prompts and custom badges.
        """
        return {
            "name": self.display_name,
            "badge": "",
            "tag": "",
            "env_vars": [],
        }

    def default_model(self) -> str | None:
        """Return the default model id, or None if not applicable."""
        models = self.list_models()
        if models:
            return models[0].get("id")
        return None

    @abc.abstractmethod
    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate an image.

        Implementations should return the dict from :func:`success_response`
        or :func:`error_response`. ``kwargs`` may contain forward-compat
        parameters future versions of the schema will expose — implementations
        should ignore unknown keys.
        """


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def resolve_aspect_ratio(value: str | None) -> str:
    """Clamp an aspect_ratio value to the valid set, defaulting to landscape.

    Invalid values are coerced rather than rejected so the tool surface is
    forgiving of agent mistakes.
    """
    if not isinstance(value, str):
        return DEFAULT_ASPECT_RATIO
    v = value.strip().lower()
    if v in VALID_ASPECT_RATIOS:
        return v
    return DEFAULT_ASPECT_RATIO


def _images_cache_dir() -> Path:
    """Return ``$PROMETHEUS_HOME/cache/images/``, creating parents as needed."""
    from prometheus.constants_core import get_prometheus_home

    path = get_prometheus_home() / "cache" / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_b64_image(
    b64_data: str,
    *,
    prefix: str = "image",
    extension: str = "png",
) -> Path:
    """Decode base64 image data and write it under ``$PROMETHEUS_HOME/cache/images/``.

    Returns the absolute :class:`Path` to the saved file.

    Filename format: ``<prefix>_<YYYYMMDD_HHMMSS>_<short-uuid>.<ext>``.
    """
    raw = base64.b64decode(b64_data)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:8]
    path = _images_cache_dir() / f"{prefix}_{ts}_{short}.{extension}"
    path.write_bytes(raw)
    return path


def success_response(
    *,
    image: str,
    model: str,
    prompt: str,
    aspect_ratio: str,
    provider: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a uniform success response dict.

    ``image`` may be an HTTP URL or an absolute filesystem path (for b64
    providers like OpenAI). Callers that need to pass through additional
    backend-specific fields can supply ``extra``.
    """
    payload: dict[str, Any] = {
        "success": True,
        "image": image,
        "model": model,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "provider": provider,
    }
    if extra:
        for k, v in extra.items():
            payload.setdefault(k, v)
    return payload


def error_response(
    *,
    error: str,
    error_type: str = "provider_error",
    provider: str = "",
    model: str = "",
    prompt: str = "",
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
) -> dict[str, Any]:
    """Build a uniform error response dict."""
    return {
        "success": False,
        "image": None,
        "error": error,
        "error_type": error_type,
        "model": model,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "provider": provider,
    }
