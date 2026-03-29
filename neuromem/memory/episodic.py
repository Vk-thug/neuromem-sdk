"""
Episodic memory for NeuroMem.

Stores recent user-agent interactions (what happened).
"""

from __future__ import annotations

from typing import List, Dict, Any, Tuple
from neuromem.core.types import MemoryItem, MemoryType
from neuromem.storage.base import MemoryBackend


class EpisodicMemory:
    """
    Episodic memory - recent experiences and interactions.

    This is like the hippocampus in the brain - stores recent events
    that may later be consolidated into long-term memory.
    """

    def __init__(self, backend: MemoryBackend, user_id: str):
        """
        Initialize episodic memory.

        Args:
            backend: Primary storage backend (Vector Store)
            user_id: User ID this memory belongs to
        """
        self.backend = backend
        self.user_id = user_id

    def store(self, item: MemoryItem):
        """
        Store an episodic memory.

        Args:
            item: Memory item to store
        """
        if item.memory_type != MemoryType.EPISODIC:
            raise ValueError("Item must be episodic memory type")

        # Write to vector store
        self.backend.upsert(item)

    def retrieve(
        self, embedding: List[float], filters: Dict[str, Any], k: int
    ) -> Tuple[List[MemoryItem], List[float]]:
        """
        Retrieve similar episodic memories.

        Args:
            embedding: Query embedding
            filters: Additional filters
            k: Number of results

        Returns:
            Tuple of (items, similarities)
        """
        filters["user_id"] = self.user_id
        filters["memory_type"] = MemoryType.EPISODIC.value

        # Always use vector store for retrieval
        return self.backend.query(embedding, filters, k)

    def get_all(self, limit: int = 100) -> List[MemoryItem]:
        """
        Get all episodic memories for the user.

        Args:
            limit: Maximum number to return

        Returns:
            List of episodic memories
        """
        return self.backend.list_all(
            self.user_id, memory_type=MemoryType.EPISODIC.value, limit=limit
        )

    def get_by_id(self, memory_id: str) -> MemoryItem | None:
        """
        Get a specific episodic memory.

        Args:
            memory_id: Memory ID

        Returns:
            Memory item or None
        """
        item = self.backend.get_by_id(memory_id)
        if item and item.user_id == self.user_id and item.memory_type == MemoryType.EPISODIC:
            return item
        return None

    def update(self, item: MemoryItem):
        """
        Update an episodic memory.

        Args:
            item: Updated memory item
        """
        if item.user_id != self.user_id:
            raise ValueError("Cannot update memory for different user")

        # Update vector store
        self.backend.update(item)

    def delete(self, memory_id: str) -> bool:
        """
        Delete an episodic memory.

        Args:
            memory_id: Memory ID

        Returns:
            True if deleted
        """
        item = self.get_by_id(memory_id)
        if item:
            # Delete from vector store
            return self.backend.delete(memory_id)
        return False
