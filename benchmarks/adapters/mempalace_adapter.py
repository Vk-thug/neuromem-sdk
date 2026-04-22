"""
MemPalace adapter for benchmarking.

Wraps ChromaDB with MemPalace's default embedding approach (all-MiniLM-L6-v2
via ChromaDB's built-in SentenceTransformer). This replicates how MemPalace
scores on benchmarks — verbatim storage with no extraction or summarization.
"""

from __future__ import annotations

import uuid

from benchmarks.adapters.base import SearchResult


class MemPalaceAdapter:
    """
    MemPalace-style adapter using ephemeral ChromaDB.

    Stores raw text verbatim with metadata, retrieves by cosine similarity.
    Uses ChromaDB's default embeddings (all-MiniLM-L6-v2).
    """

    def __init__(self) -> None:
        self._client = None
        self._collections: dict[str, object] = {}

    @property
    def name(self) -> str:
        return "MemPalace (ChromaDB)"

    def setup(self, config: dict) -> None:
        """Initialize ephemeral ChromaDB client."""
        try:
            import chromadb
        except ImportError:
            raise ImportError(
                "chromadb is required for the MemPalace adapter.\n"
                "Install with: pip install chromadb"
            )
        self._client = chromadb.EphemeralClient()
        self._collections = {}

    def _get_collection(self, user_id: str) -> object:
        """Get or create a collection for a user."""
        if user_id not in self._collections:
            import chromadb

            # Sanitize collection name (ChromaDB requirements)
            safe_name = f"u_{user_id.replace('-', '_')[:50]}"
            self._collections[user_id] = self._client.get_or_create_collection(
                name=safe_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[user_id]

    def add_memory(
        self,
        user_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> str:
        """Store verbatim text in ChromaDB."""
        collection = self._get_collection(user_id)
        doc_id = str(uuid.uuid4())

        meta = dict(metadata) if metadata else {}
        # ChromaDB metadata values must be str, int, float, or bool
        sanitized_meta: dict = {}
        for k, v in meta.items():
            if isinstance(v, (str, int, float, bool)):
                sanitized_meta[k] = v
            else:
                sanitized_meta[k] = str(v)

        collection.add(
            documents=[content],
            ids=[doc_id],
            metadatas=[sanitized_meta] if sanitized_meta else None,
        )
        return doc_id

    def search(
        self,
        user_id: str,
        query: str,
        k: int = 5,
    ) -> list[SearchResult]:
        """Search by cosine similarity in ChromaDB."""
        collection = self._get_collection(user_id)

        count = collection.count()
        if count == 0:
            return []

        results = collection.query(
            query_texts=[query],
            n_results=min(k, count),
            include=["documents", "distances", "metadatas"],
        )

        search_results: list[SearchResult] = []
        docs = results.get("documents", [[]])[0]
        dists = results.get("distances", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        ids = results.get("ids", [[]])[0]

        for i, doc in enumerate(docs):
            # ChromaDB returns L2 distances for cosine space: dist = 1 - cos_sim
            dist = dists[i] if i < len(dists) else 1.0
            similarity = max(0.0, 1.0 - dist)
            meta = metas[i] if i < len(metas) else {}
            doc_id = ids[i] if i < len(ids) else ""

            search_results.append(SearchResult(
                content=doc or "",
                score=similarity,
                memory_id=doc_id,
                metadata=meta or {},
            ))

        return search_results

    def get_all(self, user_id: str) -> list[SearchResult]:
        """Get all stored memories for a user."""
        collection = self._get_collection(user_id)
        count = collection.count()
        if count == 0:
            return []

        results = collection.get(include=["documents", "metadatas"])
        search_results: list[SearchResult] = []
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])
        ids = results.get("ids", [])

        for i, doc in enumerate(docs):
            search_results.append(SearchResult(
                content=doc or "",
                score=1.0,
                memory_id=ids[i] if i < len(ids) else "",
                metadata=metas[i] if i < len(metas) else {},
            ))

        return search_results

    def clear(self, user_id: str) -> None:
        """Delete all memories for a user."""
        if user_id in self._collections:
            safe_name = f"u_{user_id.replace('-', '_')[:50]}"
            try:
                self._client.delete_collection(safe_name)
            except Exception:
                pass
            del self._collections[user_id]

    def teardown(self) -> None:
        """Clean up ChromaDB client."""
        self._collections.clear()
        self._client = None

    def memory_count(self, user_id: str) -> int:
        """Return number of stored memories."""
        if user_id not in self._collections:
            return 0
        collection = self._get_collection(user_id)
        return collection.count()
