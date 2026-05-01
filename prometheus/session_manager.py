"""Session management and search for Prometheus."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("prometheus.sessions")


class SessionEntry:
    """A session entry with metadata."""

    def __init__(
        self,
        session_id: str,
        created_at: str,
        last_accessed: str,
        title: str = "",
        message_count: int = 0,
        metadata: dict[str, Any] | None = None,
        parent_session_id: str | None = None,
        end_reason: str | None = None,
    ):
        self.session_id = session_id
        self.created_at = created_at
        self.last_accessed = last_accessed
        self.title = title
        self.message_count = message_count
        self.metadata = metadata or {}
        self.parent_session_id = parent_session_id
        self.end_reason = end_reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "title": self.title,
            "message_count": self.message_count,
            "metadata": self.metadata,
            "parent_session_id": self.parent_session_id,
            "end_reason": self.end_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionEntry":
        return cls(
            session_id=data["session_id"],
            created_at=data["created_at"],
            last_accessed=data["last_accessed"],
            title=data.get("title", ""),
            message_count=data.get("message_count", 0),
            metadata=data.get("metadata", {}),
            parent_session_id=data.get("parent_session_id"),
            end_reason=data.get("end_reason"),
        )


class SessionIndex:
    """Index of all sessions."""

    def __init__(self):
        self._sessions: dict[str, SessionEntry] = {}
        self._load()

    def _load(self):
        """Load session index from disk."""
        if not SESSION_INDEX_FILE.exists():
            return

        try:
            with open(SESSION_INDEX_FILE, encoding="utf-8") as f:
                data = json.load(f)
                for session_data in data.get("sessions", []):
                    entry = SessionEntry.from_dict(session_data)
                    self._sessions[entry.session_id] = entry
        except Exception as e:
            logger.error(f"Failed to load session index: {e}")

    def _save(self):
        """Save session index to disk."""
        SESSION_INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(SESSION_INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {"sessions": [entry.to_dict() for entry in self._sessions.values()]},
                    f,
                    indent=2,
                )
        except Exception as e:
            logger.error(f"Failed to save session index: {e}")

    def add_session(self, entry: SessionEntry):
        """Add or update a session entry."""
        self._sessions[entry.session_id] = entry
        self._save()

    def get_session(self, session_id: str) -> SessionEntry | None:
        """Get a session entry."""
        return self._sessions.get(session_id)

    def remove_session(self, session_id: str):
        """Remove a session entry."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._save()

    def create_session(
        self,
        session_id: str,
        title: str = "",
        parent_session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionEntry:
        """Create a new session entry.

        Args:
            session_id: Unique session identifier
            title: Optional session title
            parent_session_id: Parent session if this is a branch
            metadata: Optional metadata dict

        Returns:
            The created SessionEntry
        """
        now = datetime.now().isoformat()
        entry = SessionEntry(
            session_id=session_id,
            created_at=now,
            last_accessed=now,
            title=title,
            message_count=0,
            metadata=metadata or {},
            parent_session_id=parent_session_id,
        )
        self._sessions[session_id] = entry
        self._save()
        return entry

    def end_session(self, session_id: str, reason: str = "ended") -> bool:
        """Mark a session as ended.

        Args:
            session_id: Session to end
            reason: Why the session ended (e.g., 'branched', 'completed', 'interrupted')

        Returns:
            True if session was found and updated
        """
        entry = self._sessions.get(session_id)
        if entry:
            entry.end_reason = reason
            self._save()
            return True
        return False

    def get_child_sessions(self, parent_session_id: str) -> list[SessionEntry]:
        """Get all child sessions (branches) of a parent session."""
        return [s for s in self._sessions.values() if s.parent_session_id == parent_session_id]

    def get_next_title_in_lineage(self, base_title: str) -> str:
        """Generate next title in a lineage (e.g., 'branch 2', 'branch 3').

        Args:
            base_title: Base title to increment (e.g., 'branch' or 'my-project')

        Returns:
            Next title in sequence (e.g., 'branch 2' if 'branch' exists)
        """
        existing_titles = {s.title.lower() for s in self._sessions.values() if s.title}

        if base_title.lower() not in existing_titles:
            return base_title

        counter = 2
        while True:
            candidate = f"{base_title} {counter}"
            if candidate.lower() not in existing_titles:
                return candidate
            counter += 1
            if counter > 1000:
                return f"{base_title} {datetime.now().strftime('%H%M%S')}"

    def list_sessions(
        self,
        sort_by: str = "last_accessed",
        limit: int = 50,
        search_query: str | None = None,
    ) -> list[SessionEntry]:
        """List sessions with optional filtering."""
        sessions = list(self._sessions.values())

        if search_query:
            query_lower = search_query.lower()
            sessions = [
                s
                for s in sessions
                if query_lower in s.title.lower() or query_lower in s.session_id.lower()
            ]

        if sort_by == "last_accessed":
            sessions.sort(key=lambda s: s.last_accessed, reverse=True)
        elif sort_by == "created_at":
            sessions.sort(key=lambda s: s.created_at, reverse=True)
        elif sort_by == "message_count":
            sessions.sort(key=lambda s: s.message_count, reverse=True)

        return sessions[:limit]

    def get_recent(self, hours: int = 24, limit: int = 10) -> list[SessionEntry]:
        """Get recently accessed sessions."""
        cutoff = datetime.now() - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()

        recent = [s for s in self._sessions.values() if s.last_accessed > cutoff_str]

        recent.sort(key=lambda s: s.last_accessed, reverse=True)
        return recent[:limit]


class SessionSearch:
    """Search within session content."""

    def __init__(self, session_dir: Path | None = None):
        self._session_dir = session_dir or SESSION_DIR

    def search(
        self,
        query: str,
        session_ids: list[str] | None = None,
        limit: int = 20,
    ) -> list[tuple[str, int, str]]:
        """Search for query in sessions.

        Returns:
            List of (session_id, line_number, matching_line) tuples
        """
        results = []
        query_lower = query.lower()

        session_files = list(self._session_dir.glob("*.json"))

        for session_file in session_files:
            session_id = session_file.stem

            if session_ids and session_id not in session_ids:
                continue

            try:
                with open(session_file, encoding="utf-8") as f:
                    data = json.load(f)

                messages = data.get("messages", [])

                for line_num, msg in enumerate(messages, 1):
                    content = msg.get("content", "")

                    if isinstance(content, str) and query_lower in content.lower():
                        preview = content[:200].replace("\n", " ")
                        results.append((session_id, line_num, preview))

                        if len(results) >= limit:
                            return results

            except Exception as e:
                logger.error(f"Failed to search session {session_id}: {e}")

        return results

    def get_session_messages(
        self,
        session_id: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get messages from a specific session."""
        session_file = self._session_dir / f"{session_id}.json"

        if not session_file.exists():
            return []

        try:
            with open(session_file, encoding="utf-8") as f:
                data = json.load(f)

            messages = data.get("messages", [])

            if limit:
                return messages[-limit:]

            return messages

        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return []

    def load_transcript(self, session_id: str) -> list[dict[str, Any]]:
        """Load full transcript for a session (for branching/resume).

        Returns:
            List of message dicts with role, content, tool_calls, etc.
        """
        return self.get_session_messages(session_id)

    def save_transcript(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Save transcript for a session.

        Args:
            session_id: Session identifier
            messages: List of message dicts
            metadata: Optional metadata to merge with existing

        Returns:
            True if saved successfully
        """
        session_file = self._session_dir / f"{session_id}.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            existing_data = {}
            if session_file.exists():
                with open(session_file, encoding="utf-8") as f:
                    existing_data = json.load(f)

            existing_data["session_id"] = session_id
            existing_data["last_accessed"] = datetime.now().isoformat()
            existing_data["message_count"] = len(messages)

            if metadata:
                existing_data["metadata"] = {**existing_data.get("metadata", {}), **metadata}

            existing_data["messages"] = messages

            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            logger.error(f"Failed to save transcript for {session_id}: {e}")
            return False

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        **kwargs,
    ) -> bool:
        """Append a message to an existing session transcript.

        Args:
            session_id: Session to append to
            role: Message role (user, assistant, system, tool)
            content: Message content
            **kwargs: Additional message fields (tool_name, tool_calls, etc.)

        Returns:
            True if appended successfully
        """
        session_file = self._session_dir / f"{session_id}.json"

        try:
            existing_data = {}
            if session_file.exists():
                with open(session_file, encoding="utf-8") as f:
                    existing_data = json.load(f)

            messages = existing_data.get("messages", [])
            message = {"role": role, "content": content}
            for key, value in kwargs.items():
                if value is not None:
                    message[key] = value

            messages.append(message)
            existing_data["messages"] = messages
            existing_data["message_count"] = len(messages)
            existing_data["last_accessed"] = datetime.now().isoformat()

            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            logger.error(f"Failed to append message to {session_id}: {e}")
            return False


class SessionBrowser:
    """Interactive session browser."""

    def __init__(self):
        self._index = SessionIndex()
        self._search = SessionSearch()

    def browse(
        self,
        search_query: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Browse sessions with optional search.

        Returns:
            List of session summaries
        """
        sessions = self._index.list_sessions(
            search_query=search_query,
            limit=limit,
        )

        return [
            {
                "session_id": s.session_id,
                "title": s.title or "(no title)",
                "created": self._format_date(s.created_at),
                "last_accessed": self._format_date(s.last_accessed),
                "message_count": s.message_count,
            }
            for s in sessions
        ]

    def search_sessions(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search within session content.

        Returns:
            List of search results
        """
        results = self._search.search(query, limit=limit)

        return [
            {
                "session_id": session_id,
                "line": line_num,
                "preview": preview,
            }
            for session_id, line_num, preview in results
        ]

    def get_session_detail(self, session_id: str) -> dict[str, Any] | None:
        """Get detailed information about a session."""
        entry = self._index.get_session(session_id)
        if not entry:
            return None

        messages = self._search.get_session_messages(session_id)

        return {
            "session_id": session_id,
            "title": entry.title,
            "created": entry.created_at,
            "last_accessed": entry.last_accessed,
            "message_count": entry.message_count,
            "messages": messages,
        }

    def delete_session(self, session_id: str):
        """Delete a session."""
        session_file = self._session_dir / f"{session_id}.json"

        if session_file.exists():
            session_file.unlink()

        self._index.remove_session(session_id)

    def branch_session(
        self,
        source_session_id: str,
        new_title: str | None = None,
    ) -> str | None:
        """Create a new branch (fork) of an existing session.

        The new session copies all conversation history from the source.
        The source session is marked as ended with reason 'branched'.
        A 'parent_session_id' link is established for lineage tracking.

        Args:
            source_session_id: Session to branch from
            new_title: Optional title for the new session. If not provided,
                      uses the source title + 'branch N' suffix

        Returns:
            New session ID if successful, None otherwise
        """

        source = self._index.get_session(source_session_id)
        if not source:
            logger.warning(f"Source session not found: {source_session_id}")
            return None

        messages = self._search.load_transcript(source_session_id)
        if not messages:
            logger.warning(f"No messages in source session: {source_session_id}")
            return None

        base_title = new_title or source.title or "branch"
        title = self._index.get_next_title_in_lineage(base_title)

        new_session_id = (
            f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        )

        self._index.create_session(
            session_id=new_session_id,
            title=title,
            parent_session_id=source_session_id,
        )

        self._search.save_transcript(
            new_session_id,
            messages,
            metadata={
                "title": title,
                "parent_session_id": source_session_id,
            },
        )

        self._index.end_session(source_session_id, reason="branched")

        logger.info(f"Branched session {source_session_id} -> {new_session_id}")
        return new_session_id

    def get_lineage(self, session_id: str) -> list[SessionEntry]:
        """Get the full lineage (ancestors) of a session.

        Args:
            session_id: Session to get lineage for

        Returns:
            List of SessionEntries from root to current session
        """
        lineage = []
        current_id = session_id

        while current_id:
            entry = self._index.get_session(current_id)
            if not entry:
                break
            lineage.append(entry)
            current_id = entry.parent_session_id

        lineage.reverse()
        return lineage

    def get_session_tree(
        self,
        session_id: str,
        max_depth: int = 10,
    ) -> dict[str, Any]:
        """Get a session tree (ancestors + descendants) for display.

        Args:
            session_id: Root session to build tree from
            max_depth: Maximum depth for descendants

        Returns:
            Dict with session info and children
        """
        root = self._index.get_session(session_id)
        if not root:
            return {}

        def build_node(entry: SessionEntry, depth: int) -> dict[str, Any]:
            node = {
                "session_id": entry.session_id,
                "title": entry.title,
                "created_at": entry.created_at,
                "end_reason": entry.end_reason,
                "depth": depth,
            }
            if depth < max_depth:
                children = self._index.get_child_sessions(entry.session_id)
                node["children"] = [build_node(child, depth + 1) for child in children]
            return node

        return build_node(root, 0)

    @staticmethod
    def _format_date(iso_date: str) -> str:
        """Format ISO date string for display."""
        try:
            dt = datetime.fromisoformat(iso_date)
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return iso_date


def get_session_browser() -> SessionBrowser:
    """Get a SessionBrowser instance."""
    return SessionBrowser()


def save_session(
    session_id: str,
    messages: list[dict[str, Any]],
    title: str = "",
    metadata: dict[str, Any] | None = None,
):
    """Save a session to disk."""
    session_file = SESSION_DIR / f"{session_id}.json"
    session_file.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "session_id": session_id,
        "created_at": datetime.now().isoformat(),
        "last_accessed": datetime.now().isoformat(),
        "title": title,
        "message_count": len(messages),
        "messages": messages,
        "metadata": metadata or {},
    }

    try:
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        index = SessionIndex()
        entry = SessionEntry(
            session_id=session_id,
            created_at=data["created_at"],
            last_accessed=data["last_accessed"],
            title=title,
            message_count=len(messages),
            metadata=metadata or {},
        )
        index.add_session(entry)

    except Exception as e:
        logger.error(f"Failed to save session: {e}")
