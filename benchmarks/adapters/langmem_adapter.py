"""
LangMem adapter for benchmarks.

Uses LangGraph's InMemoryStore with OpenAI embeddings — the standard
storage backend that LangMem builds on.

Install: pip install langmem (installs langgraph + langchain-openai)
"""

import uuid
from typing import Optional

from benchmarks.adapters.base import SearchResult


class LangMemAdapter:
    """Adapter wrapping LangMem / LangGraph InMemoryStore for benchmarking."""

    def __init__(self) -> None:
        self._store = None
        self._user_id: str = ""
        self._embedding_model: str = "text-embedding-3-small"

    @property
    def name(self) -> str:
        return "LangMem"

    def setup(self, config: dict) -> None:
        """
        Initialize LangMem with vector-indexed InMemoryStore.

        Config keys:
            embedding_model: str (default: "text-embedding-3-small")
            embedding_provider: "openai" (only openai supported for now)
            user_id: str (default: auto-generated UUID)
        """
        try:
            from langgraph.store.memory import InMemoryStore
        except ImportError:
            raise ImportError(
                "langmem is required. Install with: pip install langmem"
            )

        self._user_id = config.get("user_id", str(uuid.uuid4()))
        self._embedding_model = config.get("embedding_model", "text-embedding-3-small")

        embedding_provider = config.get("embedding_provider", "openai")

        if embedding_provider == "openai":
            from langchain_openai import OpenAIEmbeddings
            embeddings = OpenAIEmbeddings(model=self._embedding_model)
            dims = 1536 if "small" in self._embedding_model else 3072
        else:
            raise ValueError(
                f"LangMem adapter only supports openai embeddings, got: {embedding_provider}"
            )

        self._store = InMemoryStore(
            index={"embed": embeddings, "dims": dims, "fields": ["text"]}
        )

    def add_memory(
        self,
        user_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> str:
        """Store a memory in the LangGraph InMemoryStore."""
        key = str(uuid.uuid4())
        value = {"text": content}
        if metadata:
            value.update(metadata)
        self._store.put(("memories", user_id), key, value)
        return key

    def search(
        self,
        user_id: str,
        query: str,
        k: int = 10,
    ) -> list[SearchResult]:
        """Search memories using semantic similarity."""
        results = self._store.search(
            ("memories", user_id),
            query=query,
            limit=k,
        )
        return [
            SearchResult(
                content=r.value.get("text", ""),
                score=r.score or 0.0,
                memory_id=r.key,
                metadata={k: v for k, v in r.value.items() if k != "text"},
            )
            for r in results
        ]

    def get_all(self, user_id: str) -> list[SearchResult]:
        """Get all stored memories."""
        results = self._store.search(("memories", user_id), limit=10000)
        return [
            SearchResult(
                content=r.value.get("text", ""),
                score=0.0,
                memory_id=r.key,
            )
            for r in results
        ]

    def clear(self, user_id: str) -> None:
        """Delete all memories for this user."""
        items = self._store.search(("memories", user_id), limit=10000)
        for item in items:
            self._store.delete(("memories", user_id), item.key)

    def teardown(self) -> None:
        """Clean up resources."""
        self._store = None

    def memory_count(self, user_id: str) -> int:
        """Return number of stored memories."""
        return len(self._store.search(("memories", user_id), limit=10000))
