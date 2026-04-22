"""
Verbatim memory store for high-recall retrieval.

Stores raw conversation text in overlapping chunks WITHOUT extraction or
summarization. This preserves the exact phrasing needed for retrieval
benchmarks while the cognitive pipeline (episodic/semantic/procedural)
handles learning, decay, and consolidation.

Inspired by MemPalace's core insight: "store everything raw, search well"
beats "extract and summarize" on retrieval benchmarks.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from neuromem import constants
from neuromem.core.types import MemoryItem, MemoryType
from neuromem.utils.embeddings import get_embedding
from neuromem.utils.logging import get_logger

logger = get_logger(__name__)

# Sentinel memory type marker in metadata to distinguish verbatim chunks
VERBATIM_MARKER = "verbatim_chunk"


def _content_hash(text: str) -> str:
    """SHA-256 hash of text for deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def chunk_text(
    text: str,
    chunk_size: int = constants.DEFAULT_VERBATIM_CHUNK_SIZE,
    overlap: int = constants.DEFAULT_VERBATIM_CHUNK_OVERLAP,
) -> List[str]:
    """
    Split text into overlapping character-based chunks.

    Args:
        text: Raw text to chunk.
        chunk_size: Max characters per chunk.
        overlap: Character overlap between consecutive chunks.

    Returns:
        List of text chunks. Single texts shorter than chunk_size
        are returned as-is (one chunk).
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Try to break at a sentence boundary within the last 20% of the chunk
        # to avoid cutting mid-sentence.
        if end < len(text):
            break_zone = chunk[int(chunk_size * 0.8) :]
            for sep in (". ", ".\n", "! ", "? ", "\n\n", "\n"):
                idx = break_zone.rfind(sep)
                if idx >= 0:
                    actual_end = start + int(chunk_size * 0.8) + idx + len(sep)
                    chunk = text[start:actual_end]
                    end = actual_end
                    break

        chunks.append(chunk.strip())
        start = end - overlap

    return chunks


class VerbatimStore:
    """
    Stores and retrieves raw conversation text via a MemoryBackend.

    Each conversation turn is chunked and stored as MemoryItem objects
    with memory_type=EPISODIC and a metadata marker to distinguish them
    from cognitive memories. Content hashing prevents duplicate chunks.

    The store uses the same backend as episodic memory, sharing the vector
    index for efficient cosine similarity search.
    """

    def __init__(
        self,
        backend: Any,  # MemoryBackend protocol
        user_id: str,
        embedding_model: str = "text-embedding-3-large",
        chunk_size: int = constants.DEFAULT_VERBATIM_CHUNK_SIZE,
        chunk_overlap: int = constants.DEFAULT_VERBATIM_CHUNK_OVERLAP,
    ):
        self.backend = backend
        self.user_id = user_id
        self.embedding_model = embedding_model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._seen_hashes: set[str] = set()

    def store(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        Store raw text as verbatim chunks.

        Args:
            content: Raw conversation text to store.
            metadata: Optional metadata (session_id, speaker, timestamp, etc.)

        Returns:
            List of memory IDs for the stored chunks.
        """
        chunks = chunk_text(content, self.chunk_size, self.chunk_overlap)
        if not chunks:
            return []

        stored_ids: List[str] = []
        base_meta = dict(metadata) if metadata else {}

        for idx, chunk in enumerate(chunks):
            # Deduplicate by content hash
            h = _content_hash(chunk)
            if h in self._seen_hashes:
                continue
            self._seen_hashes.add(h)

            chunk_meta = {
                **base_meta,
                "store_type": VERBATIM_MARKER,
                "chunk_index": idx,
                "content_hash": h,
            }

            try:
                embedding = get_embedding(chunk, self.embedding_model)
            except Exception as e:
                logger.warning(
                    "Failed to embed verbatim chunk, skipping",
                    extra={"error": str(e), "chunk_len": len(chunk)},
                )
                continue

            memory_id = str(uuid.uuid4())
            item = MemoryItem(
                id=memory_id,
                user_id=self.user_id,
                content=chunk,
                embedding=embedding,
                memory_type=MemoryType.EPISODIC,
                # High salience so verbatim chunks compete fairly with cognitive
                # memories in hybrid ranking (cognitive memories get 0.65-0.85
                # from _calculate_salience, so verbatim needs to match).
                salience=0.85,
                confidence=1.0,  # Verbatim = ground truth
                created_at=datetime.now(timezone.utc),
                last_accessed=datetime.now(timezone.utc),
                decay_rate=0.0,  # Verbatim chunks don't decay
                reinforcement=1,
                inferred=False,
                editable=False,
                tags=[],
                metadata=chunk_meta,
            )
            self.backend.upsert(item)
            stored_ids.append(memory_id)

        return stored_ids

    def query(
        self,
        embedding: List[float],
        k: int = 10,
    ) -> Tuple[List[MemoryItem], List[float]]:
        """
        Query verbatim chunks by embedding similarity.

        Filters results to only return verbatim chunks (not cognitive memories).

        Args:
            embedding: Query embedding vector.
            k: Number of results to return.

        Returns:
            (items, similarities) tuple.
        """
        # Query with a larger k to account for filtering
        items, sims = self.backend.query(
            embedding=embedding,
            filters={"user_id": self.user_id},
            k=k * 3,
        )

        # Filter to verbatim chunks only
        filtered_items: List[MemoryItem] = []
        filtered_sims: List[float] = []
        for item, sim in zip(items, sims):
            if item.metadata.get("store_type") == VERBATIM_MARKER:
                filtered_items.append(item)
                filtered_sims.append(sim)
                if len(filtered_items) >= k:
                    break

        return filtered_items, filtered_sims

    def count(self) -> int:
        """Count verbatim chunks for this user."""
        all_items = self.backend.list_all(self.user_id, limit=10000)
        return sum(1 for item in all_items if item.metadata.get("store_type") == VERBATIM_MARKER)

    def clear(self) -> None:
        """Remove all verbatim chunks for this user."""
        all_items = self.backend.list_all(self.user_id, limit=10000)
        for item in all_items:
            if item.metadata.get("store_type") == VERBATIM_MARKER:
                self.backend.delete(item.id)
        self._seen_hashes.clear()
