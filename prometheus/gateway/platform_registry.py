"""Platform Adapter Registry."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PlatformEntry:
    """Metadata and factory for a single platform adapter."""

    name: str
    label: str
    adapter_factory: Callable[[Any], Any]
    check_fn: Callable[[], bool]
    validate_config: Callable[[Any], bool] | None = None
    is_connected: Callable[[Any], bool] | None = None
    required_env: list = field(default_factory=list)
    install_hint: str = ""
    setup_fn: Callable[[], None] | None = None
    source: str = "plugin"
    plugin_name: str = ""
    allowed_users_env: str = ""
    allow_all_env: str = ""
    max_message_length: int = 0
    pii_safe: bool = False
    emoji: str = "🔌"
    allow_update_command: bool = True
    platform_hint: str = ""


class PlatformRegistry:
    """Central registry of platform adapters.

    Thread-safe for reads (dict lookups are atomic under GIL).
    Writes happen at startup during sequential discovery.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, PlatformEntry] = {}

    def register(self, entry: PlatformEntry) -> None:
        """Register a platform adapter entry.

        If an entry with the same name exists, it is replaced (last writer
        wins -- this lets plugins override built-in adapters if desired).
        """
        if entry.name in self._entries:
            prev = self._entries[entry.name]
            logger.info(
                "Platform '%s' re-registered (was %s, now %s)",
                entry.name,
                prev.source,
                entry.source,
            )
        self._entries[entry.name] = entry
        logger.debug("Registered platform adapter: %s (%s)", entry.name, entry.source)

    def unregister(self, name: str) -> bool:
        """Remove a platform entry.  Returns True if it existed."""
        return self._entries.pop(name, None) is not None

    def get(self, name: str) -> PlatformEntry | None:
        """Look up a platform entry by name."""
        return self._entries.get(name)

    def all_entries(self) -> list[PlatformEntry]:
        """Return all registered platform entries."""
        return list(self._entries.values())

    def plugin_entries(self) -> list[PlatformEntry]:
        """Return only plugin-registered platform entries."""
        return [e for e in self._entries.values() if e.source == "plugin"]

    def is_registered(self, name: str) -> bool:
        return name in self._entries

    def create_adapter(self, name: str, config: Any) -> Any | None:
        """Create an adapter instance for the given platform name.

        Returns None if:
        - No entry registered for *name*
        - check_fn() returns False (missing deps)
        - validate_config() returns False (misconfigured)
        - The factory raises an exception
        """
        entry = self._entries.get(name)
        if entry is None:
            return None

        if not entry.check_fn():
            hint = f" ({entry.install_hint})" if entry.install_hint else ""
            logger.warning(
                "Platform '%s' requirements not met%s",
                entry.label,
                hint,
            )
            return None

        if entry.validate_config is not None:
            try:
                if not entry.validate_config(config):
                    logger.warning(
                        "Platform '%s' config validation failed",
                        entry.label,
                    )
                    return None
            except Exception as e:
                logger.warning(
                    "Platform '%s' config validation error: %s",
                    entry.label,
                    e,
                )
                return None

        try:
            adapter = entry.adapter_factory(config)
            return adapter
        except Exception as e:
            logger.error(
                "Failed to create adapter for platform '%s': %s",
                entry.label,
                e,
                exc_info=True,
            )
            return None


platform_registry = PlatformRegistry()
