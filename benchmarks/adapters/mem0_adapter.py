"""
Mem0 adapter for benchmarks.

Wraps the mem0ai package to implement the same interface as NeuroMem.
Install: pip install mem0ai
"""

from __future__ import annotations

import uuid
from typing import Optional

from benchmarks.adapters.base import SearchResult


class Mem0Adapter:
    """Adapter wrapping Mem0 for benchmarking."""

    def __init__(self) -> None:
        self._client = None
        self._user_id: str = ""

    @property
    def name(self) -> str:
        return "Mem0"

    def setup(self, config: dict) -> None:
        """
        Initialize Mem0.

        Config keys:
            embedding_model: str (default: "text-embedding-3-small")
            llm_model: str (default: "gpt-4.1-nano")
            vector_store: dict with provider, config (default: Qdrant)
            user_id: str (default: auto-generated UUID)
            ollama_base_url: str (for ollama embeddings)
            embedding_provider: "openai" | "ollama" (default: "openai")
        """
        try:
            from mem0 import Memory
        except ImportError:
            raise ImportError(
                "mem0ai is required for Mem0 benchmarks. "
                "Install with: pip install mem0ai"
            )

        self._user_id = config.get("user_id", str(uuid.uuid4()))

        # Build Mem0 config
        mem0_config: dict = {}

        # Embedding config
        embedding_provider = config.get("embedding_provider", "openai")
        if embedding_provider == "ollama":
            mem0_config["embedder"] = {
                "provider": "ollama",
                "config": {
                    "model": config.get("embedding_model", "nomic-embed-text"),
                    "ollama_base_url": config.get(
                        "ollama_base_url", "http://localhost:11434"
                    ),
                },
            }
        else:
            mem0_config["embedder"] = {
                "provider": "openai",
                "config": {
                    "model": config.get("embedding_model", "text-embedding-3-small"),
                },
            }

        # LLM config
        llm_provider = config.get("llm_provider", "openai")
        if llm_provider == "ollama":
            mem0_config["llm"] = {
                "provider": "ollama",
                "config": {
                    "model": config.get("llm_model", "qwen2.5-coder:7b"),
                    "ollama_base_url": config.get(
                        "ollama_base_url", "http://localhost:11434"
                    ),
                },
            }
        else:
            mem0_config["llm"] = {
                "provider": "openai",
                "config": {
                    "model": config.get("llm_model", "gpt-4.1-nano"),
                },
            }

        # Vector store config
        vector_store = config.get("vector_store")
        if vector_store:
            mem0_config["vector_store"] = vector_store
        else:
            # Default: use Qdrant if available, otherwise in-memory
            backend = config.get("backend", "memory")
            if backend == "qdrant":
                mem0_config["vector_store"] = {
                    "provider": "qdrant",
                    "config": {
                        "host": config.get("qdrant_host", "localhost"),
                        "port": config.get("qdrant_port", 6333),
                        "collection_name": config.get(
                            "collection_name", "mem0_bench"
                        ),
                    },
                }

        self._client = Memory.from_config(mem0_config) if mem0_config else Memory()

    def add_memory(
        self,
        user_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> str:
        """Store a memory via Mem0's add method."""
        meta = metadata or {}
        messages = [{"role": "user", "content": content}]

        result = self._client.add(
            messages=messages,
            user_id=user_id,
            metadata=meta,
        )

        # Mem0 returns a dict with "results" key containing list of memories
        if isinstance(result, dict) and "results" in result:
            results = result["results"]
            if results and len(results) > 0:
                return results[0].get("id", str(uuid.uuid4()))
        return str(uuid.uuid4())

    def search(
        self,
        user_id: str,
        query: str,
        k: int = 5,
    ) -> list[SearchResult]:
        """Search memories using Mem0's search method."""
        results = self._client.search(
            query=query,
            user_id=user_id,
            limit=k,
        )

        search_results: list[SearchResult] = []
        if isinstance(results, dict) and "results" in results:
            items = results["results"]
        elif isinstance(results, list):
            items = results
        else:
            items = []

        for item in items:
            if isinstance(item, dict):
                search_results.append(SearchResult(
                    content=item.get("memory", item.get("text", "")),
                    score=item.get("score", 0.0),
                    memory_id=item.get("id", ""),
                    metadata=item.get("metadata", {}),
                ))

        return search_results

    def get_all(self, user_id: str) -> list[SearchResult]:
        """Get all stored memories."""
        results = self._client.get_all(user_id=user_id)
        items = []
        if isinstance(results, dict) and "results" in results:
            raw = results["results"]
        elif isinstance(results, list):
            raw = results
        else:
            raw = []

        for item in raw:
            if isinstance(item, dict):
                items.append(SearchResult(
                    content=item.get("memory", item.get("text", "")),
                    score=0.0,
                    memory_id=item.get("id", ""),
                ))
        return items

    def clear(self, user_id: str) -> None:
        """Delete all memories for a user."""
        try:
            self._client.delete_all(user_id=user_id)
        except Exception:
            # Fallback: delete one by one
            all_mems = self.get_all(user_id)
            for mem in all_mems:
                try:
                    self._client.delete(memory_id=mem.memory_id)
                except Exception:
                    pass

    def teardown(self) -> None:
        """Clean up resources."""
        self._client = None

    def memory_count(self, user_id: str) -> int:
        """Return number of stored memories."""
        return len(self.get_all(user_id))
