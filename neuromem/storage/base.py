"""
Storage backend abstraction for NeuroMem.

Defines the protocol that all storage backends must implement.
"""

from __future__ import annotations

from typing import Protocol, List, Dict, Any, Tuple
from neuromem.core.types import MemoryItem


class MemoryBackend(Protocol):
    """
    Protocol for memory storage backends.

    All storage implementations (PostgreSQL, SQLite, Chroma, Redis, etc.)
    must implement this interface.
    """

    def upsert(self, item: MemoryItem) -> None:
        """
        Insert or update a memory item.

        Args:
            item: Memory item to store
        """
        ...

    def query(
        self, embedding: List[float], filters: Dict[str, Any], k: int
    ) -> Tuple[List[MemoryItem], List[float]]:
        """
        Query for similar memories.

        Args:
            embedding: Query embedding vector
            filters: Filter criteria (e.g., user_id, memory_type)
            k: Number of results to return

        Returns:
            Tuple of (memory_items, similarity_scores)
        """
        ...

    def get_by_id(self, item_id: str) -> MemoryItem | None:
        """
        Get a memory by ID.

        Args:
            item_id: Memory ID

        Returns:
            Memory item or None if not found
        """
        ...

    def update(self, item: MemoryItem) -> None:
        """
        Update an existing memory item.

        Args:
            item: Memory item with updated fields
        """
        ...

    def delete(self, item_id: str) -> bool:
        """
        Delete a memory item.

        Args:
            item_id: Memory ID

        Returns:
            True if deleted, False if not found
        """
        ...

    def list_all(
        self, user_id: str, memory_type: str | None = None, limit: int = 100
    ) -> List[MemoryItem]:
        """
        List all memories for a user.

        Args:
            user_id: User ID
            memory_type: Optional filter by memory type
            limit: Maximum number to return

        Returns:
            List of memory items
        """
        ...
