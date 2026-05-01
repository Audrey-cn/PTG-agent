"""Memory management utilities for Prometheus."""

import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


class MemoryDeduplicator:
    """Deduplicate memory entries to prevent redundant information."""

    def __init__(self, similarity_threshold: float = 0.85):
        """Initialize the deduplicator.

        Args:
            similarity_threshold: Threshold for considering entries as duplicates (0.0-1.0)
        """
        self._threshold = similarity_threshold
        self._seen_hashes: set[str] = set()
        self._seen_texts: list[str] = []

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        return text.lower().strip()

    def _compute_hash(self, text: str) -> str:
        """Compute a hash for text."""
        normalized = self._normalize_text(text)
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _compute_similarity(self, text1: str, text2: str) -> float:
        """Compute similarity between two texts using Jaccard similarity.

        Returns:
            Similarity score between 0.0 and 1.0
        """
        words1 = set(self._normalize_text(text1).split())
        words2 = set(self._normalize_text(text2).split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def is_duplicate(self, text: str) -> bool:
        """Check if text is a duplicate.

        Args:
            text: Text to check

        Returns:
            True if text is a duplicate
        """
        normalized = self._normalize_text(text)

        text_hash = self._compute_hash(normalized)
        if text_hash in self._seen_hashes:
            return True

        for seen_text in self._seen_texts:
            similarity = self._compute_similarity(normalized, seen_text)
            if similarity >= self._threshold:
                return True

        return False

    def add(self, text: str) -> bool:
        """Add text to the deduplicator.

        Args:
            text: Text to add

        Returns:
            True if text was added (not a duplicate), False if skipped
        """
        if self.is_duplicate(text):
            return False

        normalized = self._normalize_text(text)
        self._seen_hashes.add(self._compute_hash(normalized))
        self._seen_texts.append(normalized)

        if len(self._seen_texts) > 1000:
            self._seen_texts = self._seen_texts[-500:]

        return True

    def deduplicate_entries(
        self,
        entries: list[dict[str, Any]],
        text_key: str = "content",
    ) -> tuple[list[dict[str, Any]], int]:
        """Deduplicate a list of memory entries.

        Args:
            entries: List of memory entry dictionaries
            text_key: Key containing text to compare

        Returns:
            Tuple of (deduplicated_entries, duplicate_count)
        """
        deduplicated = []
        duplicate_count = 0

        for entry in entries:
            text = entry.get(text_key, "")

            if isinstance(text, list):
                text = " ".join(str(t) for t in text)

            if self.add(text):
                deduplicated.append(entry)
            else:
                duplicate_count += 1

        return deduplicated, duplicate_count

    def clear(self):
        """Clear all seen entries."""
        self._seen_hashes.clear()
        self._seen_texts.clear()


class MemoryCompressor:
    """Compress memory entries to fit within token budgets."""

    def __init__(
        self,
        max_memory_tokens: int = 10000,
        compression_ratio: float = 0.5,
    ):
        """Initialize the compressor.

        Args:
            max_memory_tokens: Maximum tokens allowed
            compression_ratio: Target compression ratio
        """
        self._max_memory_tokens = max_memory_tokens
        self._compression_ratio = compression_ratio

    def compress_entries(
        self,
        entries: list[dict[str, Any]],
        text_key: str = "content",
    ) -> list[dict[str, Any]]:
        """Compress memory entries to fit within token budget.

        Args:
            entries: List of memory entry dictionaries
            text_key: Key containing text to compress

        Returns:
            Compressed entries
        """
        current_tokens = self._estimate_tokens(entries, text_key)

        if current_tokens <= self._max_memory_tokens:
            return entries

        compressed = entries.copy()
        target_tokens = int(self._max_memory_tokens * self._compression_ratio)

        while current_tokens > target_tokens and len(compressed) > 1:
            compressed = self._compress_one_level(compressed, text_key)
            current_tokens = self._estimate_tokens(compressed, text_key)

        return compressed

    def _estimate_tokens(self, entries: list[dict[str, Any]], text_key: str) -> int:
        """Estimate total tokens in entries."""
        total = 0
        for entry in entries:
            text = entry.get(text_key, "")
            if isinstance(text, list):
                text = " ".join(str(t) for t in text)
            total += len(text) // 4
        return total

    def _compress_one_level(
        self,
        entries: list[dict[str, Any]],
        text_key: str,
    ) -> list[dict[str, Any]]:
        """Compress entries by one level (merge adjacent entries)."""
        if len(entries) <= 2:
            return entries

        compressed = []

        for i in range(0, len(entries) - 1, 2):
            merged = self._merge_entries(entries[i], entries[i + 1], text_key)
            compressed.append(merged)

        if len(entries) % 2 == 1:
            compressed.append(entries[-1])

        return compressed

    def _merge_entries(
        self,
        entry1: dict[str, Any],
        entry2: dict[str, Any],
        text_key: str,
    ) -> dict[str, Any]:
        """Merge two entries into one."""
        text1 = entry1.get(text_key, "")
        text2 = entry2.get(text_key, "")

        if isinstance(text1, list):
            text1 = " ".join(str(t) for t in text1)
        if isinstance(text2, list):
            text2 = " ".join(str(t) for t in text2)

        merged_text = f"{text1}\n{text2}"

        merged = entry1.copy()
        merged[text_key] = merged_text

        return merged


class MemoryFlusher:
    """Flush memory to long-term storage."""

    def __init__(self, storage_path: str | None = None):
        """Initialize the flusher.

        Args:
            storage_path: Path to storage directory
        """
        from pathlib import Path

        self._storage_path = Path(storage_path) if storage_path else None

        if self._storage_path:
            self._storage_path.mkdir(parents=True, exist_ok=True)

    def flush_to_file(
        self,
        entries: list[dict[str, Any]],
        filename: str,
        format: str = "json",
    ) -> bool:
        """Flush entries to a file.

        Args:
            entries: List of memory entries
            filename: Filename to write
            format: File format (json/jsonl)

        Returns:
            True if successful
        """
        if not self._storage_path:
            return False

        import json

        file_path = self._storage_path / filename

        try:
            if format == "json":
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(entries, f, indent=2, ensure_ascii=False)
            elif format == "jsonl":
                with open(file_path, "w", encoding="utf-8") as f:
                    for entry in entries:
                        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            else:
                return False

            logger.info(f"Flushed {len(entries)} entries to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to flush memory: {e}")
            return False

    def load_from_file(
        self,
        filename: str,
        format: str = "json",
    ) -> list[dict[str, Any]]:
        """Load entries from a file.

        Args:
            filename: Filename to read
            format: File format (json/jsonl)

        Returns:
            List of memory entries
        """
        if not self._storage_path:
            return []

        import json

        file_path = self._storage_path / filename

        if not file_path.exists():
            return []

        try:
            if format == "json":
                with open(file_path, encoding="utf-8") as f:
                    return json.load(f)
            elif format == "jsonl":
                entries = []
                with open(file_path, encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            entries.append(json.loads(line))
                return entries

        except Exception as e:
            logger.error(f"Failed to load memory: {e}")

        return []


class MemoryManager:
    """Central memory management with flush, dedup, and compression."""

    def __init__(
        self,
        max_memory_tokens: int = 10000,
        deduplication_threshold: float = 0.85,
    ):
        """Initialize the memory manager.

        Args:
            max_memory_tokens: Maximum memory tokens
            deduplication_threshold: Deduplication similarity threshold
        """
        self._deduplicator = MemoryDeduplicator(deduplication_threshold)
        self._compressor = MemoryCompressor(max_memory_tokens)
        self._flusher = MemoryFlusher()

    def process_entries(
        self,
        entries: list[dict[str, Any]],
        text_key: str = "content",
        flush: bool = False,
        flush_filename: str | None = None,
    ) -> dict[str, Any]:
        """Process memory entries through dedup and compression.

        Args:
            entries: List of memory entries
            text_key: Key containing text
            flush: Whether to flush to storage
            flush_filename: Filename for flushing

        Returns:
            Processing result with stats
        """
        original_count = len(entries)

        deduplicated, duplicates_removed = self._deduplicator.deduplicate_entries(entries, text_key)

        compressed = self._compressor.compress_entries(deduplicated, text_key)

        if flush and flush_filename:
            self._flusher.flush_to_file(compressed, flush_filename)

        return {
            "original_count": original_count,
            "duplicates_removed": duplicates_removed,
            "final_count": len(compressed),
            "compressed": compressed,
        }

    def add_entry(self, entry: dict[str, Any], text_key: str = "content") -> bool:
        """Add a single entry with deduplication.

        Args:
            entry: Memory entry
            text_key: Key containing text

        Returns:
            True if entry was added
        """
        text = entry.get(text_key, "")

        if isinstance(text, list):
            text = " ".join(str(t) for t in text)

        return self._deduplicator.add(text)


_global_memory_manager: MemoryManager | None = None


def get_memory_manager() -> MemoryManager:
    """Get the global memory manager instance."""
    global _global_memory_manager
    if _global_memory_manager is None:
        _global_memory_manager = MemoryManager()
    return _global_memory_manager


def deduplicate_memory(entries: list[dict[str, Any]], **kwargs) -> tuple[list[dict[str, Any]], int]:
    """Deduplicate memory entries.

    Args:
        entries: List of memory entries
        **kwargs: Additional arguments for deduplicator

    Returns:
        Tuple of (deduplicated_entries, duplicate_count)
    """
    deduplicator = MemoryDeduplicator(**kwargs)
    return deduplicator.deduplicate_entries(entries)


def compress_memory(
    entries: list[dict[str, Any]], max_tokens: int = 10000, **kwargs
) -> list[dict[str, Any]]:
    """Compress memory entries.

    Args:
        entries: List of memory entries
        max_tokens: Maximum tokens
        **kwargs: Additional arguments for compressor

    Returns:
        Compressed entries
    """
    compressor = MemoryCompressor(max_memory_tokens=max_tokens, **kwargs)
    return compressor.compress_entries(entries)
