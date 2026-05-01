"""Image Generation Provider Registry."""

from __future__ import annotations

import logging
import threading

from prometheus.agent.image_gen_provider import ImageGenProvider

logger = logging.getLogger(__name__)


_providers: dict[str, ImageGenProvider] = {}
_lock = threading.Lock()


def register_provider(provider: ImageGenProvider) -> None:
    """Register an image generation provider.

    Re-registration (same ``name``) overwrites the previous entry and logs
    a debug message — this makes hot-reload scenarios (tests, dev loops)
    behave predictably.
    """
    if not isinstance(provider, ImageGenProvider):
        raise TypeError(
            f"register_provider() expects an ImageGenProvider instance, "
            f"got {type(provider).__name__}"
        )
    name = provider.name
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Image gen provider .name must be a non-empty string")
    with _lock:
        existing = _providers.get(name)
        _providers[name] = provider
    if existing is not None:
        logger.debug(
            "Image gen provider '%s' re-registered (was %r)", name, type(existing).__name__
        )
    else:
        logger.debug("Registered image gen provider '%s' (%s)", name, type(provider).__name__)


def list_providers() -> list[ImageGenProvider]:
    """Return all registered providers, sorted by name."""
    with _lock:
        items = list(_providers.values())
    return sorted(items, key=lambda p: p.name)


def get_provider(name: str) -> ImageGenProvider | None:
    """Return the provider registered under *name*, or None."""
    if not isinstance(name, str):
        return None
    with _lock:
        return _providers.get(name.strip())


def get_active_provider() -> ImageGenProvider | None:
    """Resolve the currently-active provider.

    Reads ``image_gen.provider`` from config.yaml; falls back per the
    module docstring.
    """
    configured: str | None = None
    try:
        from prometheus.config import PrometheusConfig

        cfg = PrometheusConfig.load()
        section = cfg.get("image_gen") if isinstance(cfg, dict) else None
        if isinstance(section, dict):
            raw = section.get("provider")
            if isinstance(raw, str) and raw.strip():
                configured = raw.strip()
    except Exception as exc:
        logger.debug("Could not read image_gen.provider from config: %s", exc)

    with _lock:
        snapshot = dict(_providers)

    if configured:
        provider = snapshot.get(configured)
        if provider is not None:
            return provider
        logger.debug(
            "image_gen.provider='%s' configured but not registered; falling back",
            configured,
        )

    if len(snapshot) == 1:
        return next(iter(snapshot.values()))

    if "fal" in snapshot:
        return snapshot["fal"]

    return None


def _reset_for_tests() -> None:
    """Clear the registry. **Test-only.**"""
    with _lock:
        _providers.clear()
