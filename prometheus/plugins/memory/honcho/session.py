"""Honcho-based session management for conversation history."""

from __future__ import annotations

import logging
import queue
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from plugins.memory.honcho.client import get_honcho_client

if TYPE_CHECKING:
    from honcho import Honcho

logger = logging.getLogger(__name__)

_ASYNC_SHUTDOWN = object()


@dataclass
class HonchoSession:
    """
    A conversation session backed by Honcho.

    Provides a local message cache that syncs to Honcho's
    AI-native memory system for user modeling.
    """

    key: str
    user_peer_id: str
    assistant_peer_id: str
    honcho_session_id: str
    messages: list[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the local cache."""
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs,
        }
        self.messages.append(msg)
        self.updated_at = datetime.now()

    def get_history(self, max_messages: int = 50) -> list[Dict[str, Any]]:
        """Get message history for LLM context."""
        recent = (
            self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        )
        return [{"role": m["role"], "content": m["content"]} for m in recent]

    def clear(self) -> None:
        """Clear all messages in the session."""
        self.messages = []
        self.updated_at = datetime.now()


class HonchoSessionManager:
    """
    Manages conversation sessions using Honcho.

    Runs alongside prometheus' existing SQLite state and file-based memory,
    adding persistent cross-session user modeling via Honcho's AI-native memory.
    """

    def __init__(
        self,
        honcho: Honcho | None = None,
        context_tokens: Optional[int] = None,
        config: Any | None = None,
        runtime_user_peer_name: Optional[str] = None,
    ):
        """
        Initialize the session manager.

        Args:
            honcho: Optional Honcho client. If not provided, uses the singleton.
            context_tokens: Max tokens for context() calls (None = Honcho default).
            config: HonchoClientConfig from global config (provides peer_name, ai_peer,
                    write_frequency, observation, etc.).
            runtime_user_peer_name: Gateway user identity for per-user memory scoping.
        """
        self._honcho = honcho
        self._context_tokens = context_tokens
        self._config = config
        self._runtime_user_peer_name = runtime_user_peer_name
        self._cache: Dict[str, HonchoSession] = {}
        self._cache_lock = threading.RLock()
        self._peers_cache: Dict[str, Any] = {}
        self._sessions_cache: Dict[str, Any] = {}

        write_frequency = config.write_frequency if config else "async"
        self._write_frequency = write_frequency
        self._turn_counter: int = 0

        self._context_cache: Dict[str, dict] = {}
        self._prefetch_cache_lock = threading.Lock()
        self._dialectic_reasoning_level: str = config.dialectic_reasoning_level if config else "low"
        self._dialectic_dynamic: bool = config.dialectic_dynamic if config else True
        self._dialectic_max_chars: int = config.dialectic_max_chars if config else 600
        self._observation_mode: str = config.observation_mode if config else "directional"
        self._user_observe_me: bool = config.user_observe_me if config else True
        self._user_observe_others: bool = config.user_observe_others if config else True
        self._ai_observe_me: bool = config.ai_observe_me if config else True
        self._ai_observe_others: bool = config.ai_observe_others if config else True
        self._message_max_chars: int = config.message_max_chars if config else 25000
        self._dialectic_max_input_chars: int = config.dialectic_max_input_chars if config else 10000

        self._async_queue: queue.Queue | None = None
        self._async_thread: threading.Thread | None = None
        if write_frequency == "async":
            self._async_queue = queue.Queue()
            self._async_thread = threading.Thread(
                target=self._async_writer_loop,
                name="honcho-async-writer",
                daemon=True,
            )
            self._async_thread.start()

    @property
    def honcho(self) -> Honcho:
        """Get the Honcho client, initializing if needed."""
        if self._honcho is None:
            self._honcho = get_honcho_client()
        return self._honcho

    def _get_or_create_peer(self, peer_id: str) -> Any:
        """
        Get or create a Honcho peer.

        Peers are lazy -- no API call until first use.
        Observation settings are controlled per-session via SessionPeerConfig.
        """
        if peer_id in self._peers_cache:
            return self._peers_cache[peer_id]

        peer = self.honcho.peer(peer_id)
        self._peers_cache[peer_id] = peer
        return peer

    def _get_or_create_honcho_session(
        self, session_id: str, user_peer: Any, assistant_peer: Any
    ) -> Tuple[Any, list]:
        """
        Get or create a Honcho session with peers configured.

        Returns:
            Tuple of (honcho_session, existing_messages).
        """
        if session_id in self._sessions_cache:
            logger.debug("Honcho session '%s' retrieved from cache", session_id)
            return self._sessions_cache[session_id], []

        session = self.honcho.session(session_id)

        try:
            from honcho.session import SessionPeerConfig

            user_config = SessionPeerConfig(
                observe_me=self._user_observe_me,
                observe_others=self._user_observe_others,
            )
            ai_config = SessionPeerConfig(
                observe_me=self._ai_observe_me,
                observe_others=self._ai_observe_others,
            )

            session.add_peers([(user_peer, user_config), (assistant_peer, ai_config)])

            try:
                server_user = session.get_peer_configuration(user_peer)
                server_ai = session.get_peer_configuration(assistant_peer)
                if server_user.observe_me is not None:
                    self._user_observe_me = server_user.observe_me
                if server_user.observe_others is not None:
                    self._user_observe_others = server_user.observe_others
                if server_ai.observe_me is not None:
                    self._ai_observe_me = server_ai.observe_me
                if server_ai.observe_others is not None:
                    self._ai_observe_others = server_ai.observe_others
                logger.debug(
                    "Honcho observation synced from server: user(me=%s,others=%s) ai(me=%s,others=%s)",
                    self._user_observe_me,
                    self._user_observe_others,
                    self._ai_observe_me,
                    self._ai_observe_others,
                )
            except Exception as e:
                logger.debug("Honcho get_peer_configuration failed (using local config): %s", e)
        except Exception as e:
            logger.warning(
                "Honcho session '%s' add_peers failed (non-fatal): %s",
                session_id,
                e,
            )

        existing_messages = []
        try:
            ctx = session.context(summary=True, tokens=self._context_tokens)
            existing_messages = ctx.messages or []

            if existing_messages and len(existing_messages) > 1:
                timestamps = [m.created_at for m in existing_messages if m.created_at]
                if timestamps and timestamps != sorted(timestamps):
                    logger.warning(
                        "Honcho messages not chronologically ordered for session '%s', sorting",
                        session_id,
                    )
                    existing_messages = sorted(
                        existing_messages,
                        key=lambda m: m.created_at or datetime.min,
                    )

            if existing_messages:
                logger.info(
                    "Honcho session '%s' retrieved (%d existing messages)",
                    session_id,
                    len(existing_messages),
                )
            else:
                logger.info("Honcho session '%s' created (new)", session_id)
        except Exception as e:
            logger.warning(
                "Honcho session '%s' loaded (failed to fetch context: %s)",
                session_id,
                e,
            )

        self._sessions_cache[session_id] = session
        return session, existing_messages

    def _sanitize_id(self, id_str: str) -> str:
        """Sanitize an ID to match Honcho's pattern: ^[a-zA-Z0-9_-]+"""
        return re.sub(r"[^a-zA-Z0-9_-]", "-", id_str)

    def get_or_create(self, key: str) -> HonchoSession:
        """
        Get an existing session or create a new one.

        Args:
            key: Session key (usually channel:chat_id).

        Returns:
            The session.
        """
        with self._cache_lock:
            if key in self._cache:
                logger.debug("Local session cache hit: %s", key)
                return self._cache[key]

        pin_peer_name = (
            self._config is not None
            and bool(getattr(self._config, "peer_name", None))
            and getattr(self._config, "pin_peer_name", False) is True
        )
        if self._runtime_user_peer_name and not pin_peer_name:
            user_peer_id = self._sanitize_id(self._runtime_user_peer_name)
        elif self._config and self._config.peer_name:
            user_peer_id = self._sanitize_id(self._config.peer_name)
        else:
            parts = key.split(":", 1)
            channel = parts[0] if len(parts) > 1 else "default"
            chat_id = parts[1] if len(parts) > 1 else key
            user_peer_id = self._sanitize_id(f"user-{channel}-{chat_id}")

        assistant_peer_id = self._sanitize_id(
            self._config.ai_peer if self._config else "prometheus-assistant"
        )

        honcho_session_id = self._sanitize_id(key)
        user_peer = self._get_or_create_peer(user_peer_id)
        assistant_peer = self._get_or_create_peer(assistant_peer_id)
        honcho_session, existing_messages = self._get_or_create_honcho_session(
            honcho_session_id, user_peer, assistant_peer
        )

        local_messages = []
        for msg in existing_messages:
            role = "assistant" if msg.peer_id == assistant_peer_id else "user"
            local_messages.append(
                {
                    "role": role,
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat() if msg.created_at else "",
                    "_synced": True,
                }
            )

        session = HonchoSession(
            key=key,
            user_peer_id=user_peer_id,
            assistant_peer_id=assistant_peer_id,
            honcho_session_id=honcho_session_id,
            messages=local_messages,
        )

        with self._cache_lock:
            self._cache[key] = session
        return session

    def _flush_session(self, session: HonchoSession) -> bool:
        """Internal: write unsynced messages to Honcho synchronously."""
        if not session.messages:
            return True

        user_peer = self._get_or_create_peer(session.user_peer_id)
        assistant_peer = self._get_or_create_peer(session.assistant_peer_id)
        honcho_session = self._sessions_cache.get(session.honcho_session_id)

        if not honcho_session:
            honcho_session, _ = self._get_or_create_honcho_session(
                session.honcho_session_id, user_peer, assistant_peer
            )

        new_messages = [m for m in session.messages if not m.get("_synced")]
        if not new_messages:
            return True

        honcho_messages = []
        for msg in new_messages:
            peer = user_peer if msg["role"] == "user" else assistant_peer
            honcho_messages.append(peer.message(msg["content"]))

        try:
            honcho_session.add_messages(honcho_messages)
            for msg in new_messages:
                msg["_synced"] = True
            logger.debug("Synced %d messages to Honcho for %s", len(honcho_messages), session.key)
            with self._cache_lock:
                self._cache[session.key] = session
            return True
        except Exception as e:
            for msg in new_messages:
                msg["_synced"] = False
            logger.error("Failed to sync messages to Honcho: %s", e)
            with self._cache_lock:
                self._cache[session.key] = session
            return False

    def _async_writer_loop(self) -> None:
        """Background daemon thread: drains the async write queue."""
        while True:
            try:
                item = self._async_queue.get(timeout=5)
                if item is _ASYNC_SHUTDOWN:
                    break

                first_error: Exception | None = None
                try:
                    success = self._flush_session(item)
                except Exception as e:
                    success = False
                    first_error = e

                if success:
                    continue

                if first_error is not None:
                    logger.warning("Honcho async write failed, retrying once: %s", first_error)
                else:
                    logger.warning("Honcho async write failed, retrying once")

                import time as _time

                _time.sleep(2)

                try:
                    retry_success = self._flush_session(item)
                except Exception as e2:
                    logger.error("Honcho async write retry failed, dropping batch: %s", e2)
                    continue

                if not retry_success:
                    logger.error("Honcho async write retry failed, dropping batch")
            except queue.Empty:
                continue
            except Exception as e:
                logger.error("Honcho async writer error: %s", e)

    def save(self, session: HonchoSession) -> None:
        """Save messages to Honcho, respecting write_frequency."""
        self._turn_counter += 1
        wf = self._write_frequency

        if wf == "async":
            if self._async_queue is not None:
                self._async_queue.put(session)
        elif wf == "turn":
            self._flush_session(session)
        elif wf == "session":
            pass
        elif isinstance(wf, int) and wf > 0 and self._turn_counter % wf == 0:
            self._flush_session(session)

    def flush_all(self) -> None:
        """Flush all pending unsynced messages for all cached sessions."""
        with self._cache_lock:
            sessions = list(self._cache.values())
        for session in sessions:
            try:
                self._flush_session(session)
            except Exception as e:
                logger.error("Honcho flush_all error for %s: %s", session.key, e)

        if self._async_queue is not None:
            while not self._async_queue.empty():
                try:
                    item = self._async_queue.get_nowait()
                    if item is not _ASYNC_SHUTDOWN:
                        self._flush_session(item)
                except queue.Empty:
                    break

    def shutdown(self) -> None:
        """Gracefully shut down the async writer thread."""
        if self._async_queue is not None and self._async_thread is not None:
            self.flush_all()
            self._async_queue.put(_ASYNC_SHUTDOWN)
            self._async_thread.join(timeout=10)

    def delete(self, key: str) -> bool:
        """Delete a session from local cache."""
        with self._cache_lock:
            if key in self._cache:
                del self._cache[key]
                return True
        return False

    def new_session(self, key: str) -> HonchoSession:
        """
        Create a new session, preserving the old one for user modeling.
        """
        import time

        with self._cache_lock:
            old_session = self._cache.pop(key, None)
            if old_session:
                self._sessions_cache.pop(old_session.honcho_session_id, None)

            timestamp = int(time.time())
            new_key = f"{key}:{timestamp}"

            session = self.get_or_create(new_key)

            self._cache[key] = session

        logger.info("Created new session for %s (honcho: %s)", key, session.honcho_session_id)
        return session

    _REASONING_LEVELS = ("minimal", "low", "medium", "high", "max")

    def _default_reasoning_level(self) -> str:
        """Return the configured default reasoning level."""
        return self._dialectic_reasoning_level

    def dialectic_query(
        self,
        session_key: str,
        query: str,
        reasoning_level: Optional[str] = None,
        peer: str = "user",
    ) -> str:
        """
        Query Honcho's dialectic endpoint about a peer.
        """
        session = self._cache.get(session_key)
        if not session:
            return ""

        target_peer_id = self._resolve_peer_id(session, peer)
        if target_peer_id is None:
            return ""

        if len(query) > self._dialectic_max_input_chars:
            query = query[: self._dialectic_max_input_chars].rsplit(" ", 1)[0]

        if self._dialectic_dynamic and reasoning_level:
            level = reasoning_level
        else:
            level = self._default_reasoning_level()

        try:
            if self._ai_observe_others:
                ai_peer_obj = self._get_or_create_peer(session.assistant_peer_id)
                if target_peer_id == session.assistant_peer_id:
                    result = ai_peer_obj.chat(query, reasoning_level=level) or ""
                else:
                    result = (
                        ai_peer_obj.chat(
                            query,
                            target=target_peer_id,
                            reasoning_level=level,
                        )
                        or ""
                    )
            else:
                target_peer = self._get_or_create_peer(target_peer_id)
                result = target_peer.chat(query, reasoning_level=level) or ""

            if result and self._dialectic_max_chars and len(result) > self._dialectic_max_chars:
                result = result[: self._dialectic_max_chars].rsplit(" ", 1)[0] + " …"
            return result
        except Exception as e:
            logger.warning("Honcho dialectic query failed: %s", e)
            return ""

    def prefetch_context(self, session_key: str, user_message: Optional[str] = None) -> None:
        """
        Fire get_prefetch_context in a background thread, caching the result.
        """

        def _run():
            result = self.get_prefetch_context(session_key, user_message)
            if result:
                self.set_context_result(session_key, result)

        t = threading.Thread(target=_run, name="honcho-context-prefetch", daemon=True)
        t.start()

    def set_context_result(self, session_key: str, result: Dict[str, str]) -> None:
        """Store a prefetched context result in a thread-safe way."""
        if not result:
            return
        with self._prefetch_cache_lock:
            self._context_cache[session_key] = result

    def pop_context_result(self, session_key: str) -> Dict[str, str]:
        """
        Return and clear the cached context result for this session.
        """
        with self._prefetch_cache_lock:
            return self._context_cache.pop(session_key, {})

    def get_prefetch_context(
        self, session_key: str, user_message: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Pre-fetch user and AI peer context from Honcho.
        """
        session = self._cache.get(session_key)
        if not session:
            return {}

        result: Dict[str, str] = {}

        try:
            honcho_session = self._sessions_cache.get(session.honcho_session_id)
            if honcho_session:
                ctx = honcho_session.context(summary=True)
                if ctx.summary and getattr(ctx.summary, "content", None):
                    result["summary"] = ctx.summary.content
        except Exception as e:
            logger.debug("Failed to fetch session summary from Honcho: %s", e)

        try:
            user_ctx = self._fetch_peer_context(session.user_peer_id, target=session.user_peer_id)
            result["representation"] = user_ctx["representation"]
            result["card"] = "\n".join(user_ctx["card"])
        except Exception as e:
            logger.warning("Failed to fetch user context from Honcho: %s", e)

        try:
            ai_ctx = self._fetch_peer_context(
                session.assistant_peer_id, target=session.assistant_peer_id
            )
            result["ai_representation"] = ai_ctx["representation"]
            result["ai_card"] = "\n".join(ai_ctx["card"])
        except Exception as e:
            logger.debug("Failed to fetch AI peer context from Honcho: %s", e)

        return result

    def migrate_local_history(self, session_key: str, messages: list[Dict[str, Any]]) -> bool:
        """
        Upload local session history to Honcho as a file.
        """
        session = self._cache.get(session_key)
        if not session:
            logger.warning("No local session cached for '%s', skipping migration", session_key)
            return False

        honcho_session = self._sessions_cache.get(session.honcho_session_id)
        if not honcho_session:
            logger.warning("No Honcho session cached for '%s', skipping migration", session_key)
            return False

        user_peer = self._get_or_create_peer(session.user_peer_id)

        content_bytes = self._format_migration_transcript(session_key, messages)
        first_ts = messages[0].get("timestamp") if messages else None

        try:
            honcho_session.upload_file(
                file=("prior_history.txt", content_bytes, "text/plain"),
                peer=user_peer,
                metadata={"source": "local_jsonl", "count": len(messages)},
                created_at=first_ts,
            )
            logger.info("Migrated %d local messages to Honcho for %s", len(messages), session_key)
            return True
        except Exception as e:
            logger.error("Failed to upload local history to Honcho for %s: %s", session_key, e)
            return False

    @staticmethod
    def _format_migration_transcript(session_key: str, messages: list[Dict[str, Any]]) -> bytes:
        """Format local messages as an XML transcript for Honcho file upload."""
        timestamps = [m.get("timestamp", "") for m in messages]
        time_range = f"{timestamps[0]} to {timestamps[-1]}" if timestamps else "unknown"

        lines = [
            "<prior_conversation_history>",
            "<context>",
            "This conversation history occurred BEFORE the Honcho memory system was activated.",
            "These messages are the preceding elements of this conversation session and should",
            "be treated as foundational context for all subsequent interactions. The user and",
            "assistant have already established rapport through these exchanges.",
            "</context>",
            "",
            f'<transcript session_key="{session_key}" message_count="{len(messages)}"',
            f'           time_range="{time_range}">',
            "",
        ]
        for msg in messages:
            ts = msg.get("timestamp", "?")
            role = msg.get("role", "unknown")
            content = msg.get("content") or ""
            lines.append(f"[{ts}] {role}: {content}")

        lines.append("")
        lines.append("</transcript>")
        lines.append("</prior_conversation_history>")

        return "\n".join(lines).encode("utf-8")

    def migrate_memory_files(self, session_key: str, memory_dir: str) -> bool:
        """
        Upload MEMORY.md and USER.md to Honcho as files.
        """
        from pathlib import Path

        memory_path = Path(memory_dir)

        if not memory_path.exists():
            return False

        session = self._cache.get(session_key)
        if not session:
            logger.warning(
                "No local session cached for '%s', skipping memory migration", session_key
            )
            return False

        honcho_session = self._sessions_cache.get(session.honcho_session_id)
        if not honcho_session:
            logger.warning(
                "No Honcho session cached for '%s', skipping memory migration", session_key
            )
            return False

        user_peer = self._get_or_create_peer(session.user_peer_id)
        assistant_peer = self._get_or_create_peer(session.assistant_peer_id)

        uploaded = False
        files = [
            (
                "MEMORY.md",
                "consolidated_memory.md",
                "Long-term agent notes and preferences",
                user_peer,
                "user",
            ),
            (
                "USER.md",
                "user_profile.md",
                "User profile and preferences",
                user_peer,
                "user",
            ),
            (
                "SOUL.md",
                "agent_soul.md",
                "Agent persona and identity configuration",
                assistant_peer,
                "ai",
            ),
        ]

        for filename, upload_name, description, target_peer, target_kind in files:
            filepath = memory_path / filename
            if not filepath.exists():
                continue
            content = filepath.read_text(encoding="utf-8").strip()
            if not content:
                continue

            wrapped = (
                f"<prior_memory_file>\n"
                f"<context>\n"
                f"This file was consolidated from local conversations BEFORE Honcho was activated.\n"
                f"{description}. Treat as foundational context for this user.\n"
                f"</context>\n"
                f"\n"
                f"{content}\n"
                f"</prior_memory_file>\n"
            )

            try:
                honcho_session.upload_file(
                    file=(upload_name, wrapped.encode("utf-8"), "text/plain"),
                    peer=target_peer,
                    metadata={
                        "source": "local_memory",
                        "original_file": filename,
                        "target_peer": target_kind,
                    },
                )
                logger.info(
                    "Uploaded %s to Honcho for %s (%s peer)",
                    filename,
                    session_key,
                    target_kind,
                )
                uploaded = True
            except Exception as e:
                logger.error("Failed to upload %s to Honcho: %s", filename, e)

        return uploaded

    @staticmethod
    def _normalize_card(card: Any) -> List[str]:
        """Normalize Honcho card payloads into a plain list of strings."""
        if not card:
            return []
        if isinstance(card, list):
            return [str(item) for item in card if item]
        return [str(card)]

    def _fetch_peer_card(self, peer_id: str, *, target: Optional[str] = None) -> List[str]:
        """Fetch a peer card directly from the peer object."""
        peer = self._get_or_create_peer(peer_id)
        getter = getattr(peer, "get_card", None)
        if callable(getter):
            return self._normalize_card(getter(target=target) if target is not None else getter())

        legacy_getter = getattr(peer, "card", None)
        if callable(legacy_getter):
            return self._normalize_card(
                legacy_getter(target=target) if target is not None else legacy_getter()
            )

        return []

    def _fetch_peer_context(
        self,
        peer_id: str,
        search_query: Optional[str] = None,
        *,
        target: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch representation + peer card directly from a peer object."""
        peer = self._get_or_create_peer(peer_id)
        representation = ""
        card: List[str] = []

        try:
            context_kwargs: Dict[str, Any] = {}
            if target is not None:
                context_kwargs["target"] = target
            if search_query is not None:
                context_kwargs["search_query"] = search_query
            ctx = peer.context(**context_kwargs) if context_kwargs else peer.context()
            representation = (
                getattr(ctx, "representation", None)
                or getattr(ctx, "peer_representation", None)
                or ""
            )
            card = self._normalize_card(getattr(ctx, "peer_card", None))
        except Exception as e:
            logger.debug("Direct peer.context() failed for '%s': %s", peer_id, e)

        if not representation:
            try:
                representation = (
                    peer.representation(target=target)
                    if target is not None
                    else peer.representation()
                ) or ""
            except Exception as e:
                logger.debug("Direct peer.representation() failed for '%s': %s", peer_id, e)

        if not card:
            try:
                card = self._fetch_peer_card(peer_id, target=target)
            except Exception as e:
                logger.debug("Direct peer card fetch failed for '%s': %s", peer_id, e)

        return {"representation": representation, "card": card}

    def get_session_context(self, session_key: str, peer: str = "user") -> Dict[str, Any]:
        """Fetch full session context from Honcho including summary."""
        session = self._cache.get(session_key)
        if not session:
            return {}

        honcho_session = self._sessions_cache.get(session.honcho_session_id)
        if not honcho_session:
            peer_id = self._resolve_peer_id(session, peer)
            if peer_id is None:
                peer_id = session.user_peer_id
            return self._fetch_peer_context(peer_id, target=peer_id)

        try:
            peer_id = self._resolve_peer_id(session, peer)
            ctx = honcho_session.context(
                summary=True,
                peer_target=peer_id,
                peer_perspective=session.user_peer_id
                if peer == "user"
                else session.assistant_peer_id,
            )

            result: Dict[str, Any] = {}

            if ctx.summary:
                result["summary"] = ctx.summary.content

            if ctx.peer_representation:
                result["representation"] = ctx.peer_representation
            if ctx.peer_card:
                result["card"] = "\n".join(ctx.peer_card)

            if ctx.messages:
                recent = ctx.messages[-10:]
                result["recent_messages"] = [
                    {"role": getattr(m, "peer_id", "unknown"), "content": (m.content or "")[:500]}
                    for m in recent
                ]

            return result
        except Exception as e:
            logger.debug("Session context fetch failed: %s", e)
            return {}

    def _resolve_peer_id(self, session: HonchoSession, peer: Optional[str]) -> str:
        """Resolve a peer alias or explicit peer ID to a concrete Honcho peer ID."""
        candidate = (peer or "user").strip()
        if not candidate:
            return session.user_peer_id

        normalized = self._sanitize_id(candidate)
        if normalized == self._sanitize_id("user"):
            return session.user_peer_id
        if normalized == self._sanitize_id("ai"):
            return session.assistant_peer_id

        return normalized

    def _resolve_observer_target(
        self,
        session: HonchoSession,
        peer: Optional[str],
    ) -> Tuple[str, str | None]:
        """Resolve observer and target peer IDs for context/search/profile queries."""
        target_peer_id = self._resolve_peer_id(session, peer)

        if target_peer_id == session.assistant_peer_id:
            return session.assistant_peer_id, session.assistant_peer_id

        if self._ai_observe_others:
            return session.assistant_peer_id, target_peer_id

        return target_peer_id, None

    def get_peer_card(self, session_key: str, peer: str = "user") -> List[str]:
        """
        Fetch a peer card — a curated list of key facts.
        """
        session = self._cache.get(session_key)
        if not session:
            return []

        try:
            observer_peer_id, target_peer_id = self._resolve_observer_target(session, peer)
            return self._fetch_peer_card(observer_peer_id, target=target_peer_id)
        except Exception as e:
            logger.debug("Failed to fetch peer card from Honcho: %s", e)
            return []

    def search_context(
        self,
        session_key: str,
        query: str,
        max_tokens: int = 800,
        peer: str = "user",
    ) -> str:
        """
        Semantic search over Honcho session context.
        """
        session = self._cache.get(session_key)
        if not session:
            return ""

        try:
            observer_peer_id, target = self._resolve_observer_target(session, peer)

            ctx = self._fetch_peer_context(
                observer_peer_id,
                search_query=query,
                target=target,
            )
            parts = []
            if ctx["representation"]:
                parts.append(ctx["representation"])
            card = ctx["card"] or []
            if card:
                parts.append("\n".join(f"- {f}" for f in card))
            return "\n\n".join(parts)
        except Exception as e:
            logger.debug("Honcho search_context failed: %s", e)
            return ""

    def create_conclusion(self, session_key: str, content: str, peer: str = "user") -> bool:
        """Write a conclusion about a target peer back to Honcho."""
        if not content or not content.strip():
            return False

        session = self._cache.get(session_key)
        if not session:
            logger.warning("No session cached for '%s', skipping conclusion", session_key)
            return False

        try:
            target_peer_id = self._resolve_peer_id(session, peer)
            if target_peer_id is None:
                logger.warning(
                    "Could not resolve conclusion peer '%s' for session '%s'", peer, session_key
                )
                return False

            if target_peer_id == session.assistant_peer_id:
                assistant_peer = self._get_or_create_peer(session.assistant_peer_id)
                conclusions_scope = assistant_peer.conclusions_of(session.assistant_peer_id)
            elif self._ai_observe_others:
                assistant_peer = self._get_or_create_peer(session.assistant_peer_id)
                conclusions_scope = assistant_peer.conclusions_of(target_peer_id)
            else:
                target_peer = self._get_or_create_peer(target_peer_id)
                conclusions_scope = target_peer.conclusions_of(target_peer_id)

            conclusions_scope.create(
                [
                    {
                        "content": content.strip(),
                        "session_id": session.honcho_session_id,
                    }
                ]
            )
            logger.info(
                "Created conclusion about %s for %s: %s", target_peer_id, session_key, content[:80]
            )
            return True
        except Exception as e:
            logger.error("Failed to create conclusion: %s", e)
            return False

    def delete_conclusion(self, session_key: str, conclusion_id: str, peer: str = "user") -> bool:
        """Delete a conclusion by ID. Use only for PII removal."""
        session = self._cache.get(session_key)
        if not session:
            return False
        try:
            target_peer_id = self._resolve_peer_id(session, peer)
            if target_peer_id == session.assistant_peer_id:
                observer = self._get_or_create_peer(session.assistant_peer_id)
                scope = observer.conclusions_of(session.assistant_peer_id)
            elif self._ai_observe_others:
                observer = self._get_or_create_peer(session.assistant_peer_id)
                scope = observer.conclusions_of(target_peer_id)
            else:
                target_peer = self._get_or_create_peer(target_peer_id)
                scope = target_peer.conclusions_of(target_peer_id)
            scope.delete(conclusion_id)
            logger.info("Deleted conclusion %s for %s", conclusion_id, session_key)
            return True
        except Exception as e:
            logger.error("Failed to delete conclusion %s: %s", conclusion_id, e)
            return False

    def set_peer_card(
        self, session_key: str, card: List[str], peer: str = "user"
    ) -> List[str] | None:
        """Update a peer's card."""
        session = self._cache.get(session_key)
        if not session:
            return None
        try:
            peer_id = self._resolve_peer_id(session, peer)
            if peer_id is None:
                logger.warning(
                    "Could not resolve peer '%s' for set_peer_card in session '%s'",
                    peer,
                    session_key,
                )
                return None
            peer_obj = self._get_or_create_peer(peer_id)
            result = peer_obj.set_card(card)
            logger.info("Updated peer card for %s (%d facts)", peer_id, len(card))
            return result
        except Exception as e:
            logger.error("Failed to set peer card: %s", e)
            return None

    def seed_ai_identity(self, session_key: str, content: str, source: str = "manual") -> bool:
        """
        Seed the AI peer's Honcho representation from text content.
        """
        if not content or not content.strip():
            return False

        session = self._cache.get(session_key)
        if not session:
            logger.warning("No session cached for '%s', skipping AI seed", session_key)
            return False

        assistant_peer = self._get_or_create_peer(session.assistant_peer_id)
        honcho_session = self._sessions_cache.get(session.honcho_session_id)
        if not honcho_session:
            logger.warning("No Honcho session cached for '%s', skipping AI seed", session_key)
            return False

        try:
            wrapped = (
                f"<ai_identity_seed>\n"
                f"<source>{source}</source>\n"
                f"\n"
                f"{content.strip()}\n"
                f"</ai_identity_seed>"
            )
            honcho_session.add_messages([assistant_peer.message(wrapped)])
            logger.info("Seeded AI identity from '%s' into %s", source, session_key)
            return True
        except Exception as e:
            logger.error("Failed to seed AI identity: %s", e)
            return False

    def get_ai_representation(self, session_key: str) -> Dict[str, str]:
        """
        Fetch the AI peer's current Honcho representation.
        """
        session = self._cache.get(session_key)
        if not session:
            return {"representation": "", "card": ""}

        try:
            ctx = self._fetch_peer_context(
                session.assistant_peer_id, target=session.assistant_peer_id
            )
            return {
                "representation": ctx["representation"] or "",
                "card": "\n".join(ctx["card"]),
            }
        except Exception as e:
            logger.debug("Failed to fetch AI representation: %s", e)
            return {"representation": "", "card": ""}

    def list_sessions(self) -> list[Dict[str, Any]]:
        """List all cached sessions."""
        return [
            {
                "key": s.key,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "message_count": len(s.messages),
            }
            for s in self._cache.values()
        ]
