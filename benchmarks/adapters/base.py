"""
Base protocol for memory system adapters.

Every memory system (NeuroMem, Mem0, Zep, LangMem) implements this
same interface so the benchmark runner is system-agnostic.
"""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class SearchResult:
    """A single search result from a memory system."""

    content: str
    score: float
    memory_id: str = ""
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class MemorySystemAdapter(Protocol):
    """Protocol that all memory system adapters must implement."""

    @property
    def name(self) -> str:
        """Human-readable name of the memory system."""
        ...

    def setup(self, config: dict) -> None:
        """Initialize the memory system with given configuration."""
        ...

    def add_memory(
        self,
        user_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> str:
        """
        Store a memory.

        Args:
            user_id: User identifier
            content: Memory content text
            metadata: Optional metadata (session_id, timestamp, speaker, etc.)

        Returns:
            Memory ID
        """
        ...

    def search(
        self,
        user_id: str,
        query: str,
        k: int = 5,
    ) -> list[SearchResult]:
        """
        Search for relevant memories.

        Args:
            user_id: User identifier
            query: Search query
            k: Number of results

        Returns:
            List of SearchResult objects
        """
        ...

    def get_all(self, user_id: str) -> list[SearchResult]:
        """Get all stored memories for a user."""
        ...

    def clear(self, user_id: str) -> None:
        """Delete all memories for a user."""
        ...

    def teardown(self) -> None:
        """Clean up resources."""
        ...

    def memory_count(self, user_id: str) -> int:
        """Return number of stored memories for user."""
        ...
