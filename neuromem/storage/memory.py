"""
In-memory storage backend for NeuroMem.

Simple implementation for testing and development.
"""

from typing import List, Dict, Any, Tuple
import numpy as np
from neuromem.core.types import MemoryItem


class InMemoryBackend:
    """
    In-memory storage backend.

    Stores all memories in RAM. Data is lost when the process ends.
    Useful for testing and development.
    """

    def __init__(self):
        self._storage: Dict[str, MemoryItem] = {}

    def upsert(self, item: MemoryItem) -> None:
        """Insert or update a memory item."""
        if item.id in self._storage:
            # Update: increment reinforcement
            existing = self._storage[item.id]
            item.reinforcement = existing.reinforcement + 1

        self._storage[item.id] = item

    def query(
        self, embedding: List[float], filters: Dict[str, Any], k: int
    ) -> Tuple[List[MemoryItem], List[float]]:
        """Query for similar memories using cosine similarity."""
        # Filter items
        items = list(self._storage.values())

        if "user_id" in filters:
            items = [item for item in items if item.user_id == filters["user_id"]]

        if "memory_type" in filters:
            allowed_types = filters["memory_type"]
            if isinstance(allowed_types, str):
                allowed_types = [allowed_types]
            items = [
                item
                for item in items
                if item.memory_type.value in allowed_types or item.memory_type in allowed_types
            ]

        if not items:
            return [], []

        # Vectorized cosine similarity — single matrix multiply instead of per-item loop.
        # For N items with D dimensions, this is O(N*D) via NumPy BLAS vs O(N*D) in Python loops.
        # In practice ~5-10x faster due to C-level vectorization.
        query_vec = np.array(embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return items[:k], [0.0] * min(k, len(items))

        embeddings_matrix = np.array([item.embedding for item in items], dtype=np.float32)
        norms = np.linalg.norm(embeddings_matrix, axis=1)
        # Avoid division by zero
        norms = np.where(norms == 0, 1.0, norms)
        similarities = (embeddings_matrix @ query_vec) / (norms * query_norm)

        # Filter out garbage results below minimum similarity threshold.
        # Without this, we return k results even if best match is 0.01.
        MIN_SIMILARITY = 0.05
        valid_mask = similarities >= MIN_SIMILARITY
        valid_indices = np.where(valid_mask)[0]

        if len(valid_indices) == 0:
            return [], []

        # Partial sort for top-k among valid results
        valid_sims = similarities[valid_indices]
        effective_k = min(k, len(valid_indices))
        if effective_k < len(valid_indices):
            top_local = np.argpartition(valid_sims, -effective_k)[-effective_k:]
            top_local = top_local[np.argsort(valid_sims[top_local])[::-1]]
        else:
            top_local = np.argsort(valid_sims)[::-1]

        top_indices = valid_indices[top_local]
        result_items = [items[i] for i in top_indices]
        result_sims = [float(similarities[i]) for i in top_indices]
        return result_items, result_sims

    def get_by_id(self, item_id: str) -> MemoryItem | None:
        """Get a memory by ID."""
        return self._storage.get(item_id)

    def update(self, item: MemoryItem) -> None:
        """Update an existing memory item."""
        if item.id in self._storage:
            self._storage[item.id] = item

    def delete(self, item_id: str) -> bool:
        """Delete a memory item."""
        if item_id in self._storage:
            del self._storage[item_id]
            return True
        return False

    def list_all(
        self, user_id: str, memory_type: str | None = None, limit: int = 100
    ) -> List[MemoryItem]:
        """List all memories for a user."""
        items = [item for item in self._storage.values() if item.user_id == user_id]

        if memory_type:
            items = [
                item
                for item in items
                if item.memory_type.value == memory_type or item.memory_type == memory_type
            ]

        # Sort by last accessed (most recent first)
        items.sort(key=lambda x: x.last_accessed, reverse=True)

        return items[:limit]

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))
