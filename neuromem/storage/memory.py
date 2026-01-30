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
        self,
        embedding: List[float],
        filters: Dict[str, Any],
        k: int
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
                item for item in items
                if item.memory_type.value in allowed_types or item.memory_type in allowed_types
            ]
        
        if not items:
            return [], []
        
        # Calculate cosine similarities
        query_vec = np.array(embedding)
        similarities = []
        
        for item in items:
            item_vec = np.array(item.embedding)
            similarity = self._cosine_similarity(query_vec, item_vec)
            similarities.append(similarity)
        
        # Sort by similarity
        sorted_pairs = sorted(
            zip(items, similarities),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Take top k
        top_k = sorted_pairs[:k]
        
        if not top_k:
            return [], []
        
        items, sims = zip(*top_k)
        return list(items), list(sims)
    
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
        self,
        user_id: str,
        memory_type: str | None = None,
        limit: int = 100
    ) -> List[MemoryItem]:
        """List all memories for a user."""
        items = [
            item for item in self._storage.values()
            if item.user_id == user_id
        ]
        
        if memory_type:
            items = [
                item for item in items
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
