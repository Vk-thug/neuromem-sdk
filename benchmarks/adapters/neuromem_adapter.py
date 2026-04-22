"""
NeuroMem SDK adapter for benchmarks.

Supports both in-memory backend (for quick testing) and Qdrant backend
(for production-grade benchmarks matching real deployment).
"""

from __future__ import annotations

import os
import uuid
import tempfile
from pathlib import Path
from typing import Optional

import yaml

from benchmarks.adapters.base import SearchResult


class NeuroMemAdapter:
    """Adapter wrapping the NeuroMem SDK for benchmarking."""

    def __init__(self) -> None:
        self._neuromem = None
        self._user_id: str = ""
        self._config_path: str = ""
        self._backend: str = "memory"
        self._use_hyde: bool = False
        self._hyde_model: str = "qwen2.5-coder:7b"
        self._verbatim_only: bool = False
        self._bm25_blend: float = 0.5
        self._ce_blend: float = 0.9
        # Optional per-category blend overrides: {category_name: {"bm25": float, "ce": float}}
        # Each slice-based runner can set its current category so the adapter
        # picks the right blend for that category's query profile.
        self._category_blend_overrides: dict[str, dict[str, float]] = {}
        self._active_category: str | None = None

    @property
    def name(self) -> str:
        mode = "verbatim-only" if self._verbatim_only else "cognitive"
        return f"NeuroMem (v0.3.0, {self._backend}, {mode})"

    def set_active_category(self, category: str | None) -> None:
        """
        Mark the current query's category so the next search() picks up any
        per-category blend override configured via `category_blend_overrides`.
        Runners call this before each search; no-op if no overrides configured.
        """
        self._active_category = category

    def setup(self, config: dict) -> None:
        """
        Initialize NeuroMem.

        Config keys:
            backend: "memory" | "qdrant" (default: "memory")
            qdrant_host: str (default: "localhost")
            qdrant_port: int (default: 6333)
            collection_name: str (default: "neuromem_bench")
            embedding_model: str (default: "nomic-embed-text")
            embedding_provider: "ollama" | "openai" (default: "ollama")
            vector_size: int (default: 768)
            user_id: str (default: auto-generated UUID)
        """
        from neuromem import NeuroMem

        self._backend = config.get("backend", "memory")
        self._user_id = config.get("user_id", str(uuid.uuid4()))
        self._use_hyde = config.get("use_hyde", False)
        self._hyde_model = config.get("hyde_model", "qwen2.5-coder:7b")
        self._use_llm_rerank = config.get("use_llm_rerank", False)
        self._verbatim_only = config.get("verbatim_only", False)
        self._bm25_blend = config.get("bm25_blend", 0.5)
        self._ce_blend = config.get("ce_blend", 0.9)
        self._category_blend_overrides = config.get("category_blend_overrides", {}) or {}

        embedding_model = config.get("embedding_model", "nomic-embed-text")
        embedding_provider = config.get("embedding_provider", "ollama")
        vector_size = config.get("vector_size", 768)

        # Build YAML config dynamically
        yaml_config = {
            "neuromem": {
                "model": {
                    "embedding": embedding_model,
                    "consolidation_llm": config.get("consolidation_llm", "gpt-4o-mini"),
                },
                "storage": {},
                "memory": {
                    "decay_enabled": False,  # Disable decay for benchmarking
                    "consolidation_interval": 999999,  # No auto-consolidation
                },
                "async": {"enabled": False},  # Sync mode for deterministic benchmarks
                "retrieval": {
                    # Pure similarity ranking for benchmarks — MemPalace uses
                    # raw cosine distance ordering. Salience/recency add noise
                    # when all memories are the same age and have similar content.
                    "hybrid_enabled": True,
                    "similarity_weight": 1.0,
                    "importance_weight": 0.0,
                    "recency_weight": 0.0,
                    "recency_half_life_days": 1,
                    "bm25_blend": self._bm25_blend,
                    "ce_blend": self._ce_blend,
                    "llm_rerank_enabled": self._use_llm_rerank,
                    "llm_rerank_model": "qwen2.5-coder:7b",
                    "llm_rerank_provider": "ollama",
                },
                "verbatim": {
                    # Enabled: provides redundant storage path that catches
                    # cases where the cognitive memory's content gets filtered
                    # by conflict resolution or confidence thresholds.
                    "enabled": True,
                    "chunk_size": 2000,
                    "chunk_overlap": 150,
                    "weight": 0.5,
                },
                "tagging": {"auto_tag_enabled": False},
                "embeddings": {
                    "provider": embedding_provider,
                    "ollama_base_url": config.get("ollama_base_url", "http://localhost:11434"),
                    # Disable deduplication for benchmarks — each LoCoMo observation is a
                    # distinct fact; dedup would merge semantically similar memories from
                    # different sessions, reducing coverage from ~180 to ~100 memories.
                    "deduplication": {"enabled": False},
                },
            }
        }

        if self._backend == "qdrant":
            yaml_config["neuromem"]["storage"] = {
                "vector_store": {
                    "type": "qdrant",
                    "config": {
                        "host": config.get("qdrant_host", "localhost"),
                        "port": config.get("qdrant_port", 6333),
                        "collection_name": config.get("collection_name", "neuromem_bench"),
                        "vector_size": vector_size,
                    },
                }
            }
        else:
            yaml_config["neuromem"]["storage"] = {
                "database": {"type": "memory"},
            }

        # Write temp config
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, prefix="neuromem_bench_"
        )
        yaml.dump(yaml_config, tmp, default_flow_style=False)
        tmp.close()
        self._config_path = tmp.name

        self._neuromem = NeuroMem.from_config(self._config_path, user_id=self._user_id)

    def add_memory(
        self,
        user_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> str:
        """Store a memory via NeuroMem's observe method."""
        meta = metadata or {}
        speaker = meta.get("speaker", "")
        session = meta.get("session_id", "")

        # Include session and speaker as context prefix so keyword fallback
        # can match queries like "Gina" or "Session 3" against the stored text.
        if speaker and session:
            formatted = f"[Session {session}] {speaker}: {content}"
        elif speaker:
            formatted = f"{speaker}: {content}"
        else:
            formatted = content

        # Pass all benchmark metadata through to the stored MemoryItem
        # so retrieval can resolve corpus_id, timestamp, etc.
        # max_content_length=1_000_000 so LongMemEval's long-haystack docs
        # (up to ~80 KB per session) don't trip the production 50 KB guard.
        self._neuromem.observe(
            user_input=formatted,
            assistant_output="Memory stored.",
            metadata=meta,
            max_content_length=1_000_000,
        )
        return str(uuid.uuid4())  # NeuroMem doesn't return ID from observe

    @staticmethod
    def _clean_content(content: str) -> str:
        """
        Strip the User:/Assistant: wrapper that _observe_sync adds.

        Stored format: "User: [Session X] Speaker: actual content\nAssistant: Memory stored."
        We extract just the actual observation text so the answer LLM
        sees clean context without noise tokens.
        """
        # Remove "Assistant: Memory stored." suffix
        if "\nAssistant: Memory stored." in content:
            content = content.split("\nAssistant: Memory stored.")[0]
        # Remove "User: " prefix
        if content.startswith("User: "):
            content = content[6:]
        return content.strip()

    def search(
        self,
        user_id: str,
        query: str,
        k: int = 5,
    ) -> list[SearchResult]:
        """Search memories using NeuroMem's retrieve method."""
        # HyDE: transform query into a hypothetical answer for better
        # semantic matching against evidence documents. Critical for
        # implicit/preference queries where query and answer share no
        # surface vocabulary. Cached so repeated benchmark runs are fast.
        effective_query = query
        if self._use_hyde:
            try:
                from neuromem.core.hyde import generate_hypothetical_answer

                effective_query = generate_hypothetical_answer(
                    query=query,
                    model=self._hyde_model,
                    provider="ollama",
                )
            except Exception:
                effective_query = query

        # Resolve per-query blend: per-category override wins over global default.
        override = self._category_blend_overrides.get(self._active_category or "", {})
        bm25_blend = override.get("bm25", self._bm25_blend)
        ce_blend = override.get("ce", self._ce_blend)

        if self._verbatim_only:
            items = self._neuromem.retrieve_verbatim_only(
                query=effective_query,
                k=k,
                bm25_blend=bm25_blend,
                ce_blend=ce_blend,
            )
        else:
            items = self._neuromem.retrieve(query=effective_query, task_type="chat", k=k)
        results: list[SearchResult] = []
        for item in items:
            # Merge item metadata (which now includes benchmark metadata like
            # corpus_id, timestamp, session_id) with memory-type info
            result_meta = dict(item.metadata) if item.metadata else {}
            result_meta["memory_type"] = item.memory_type.value
            result_meta["confidence"] = item.confidence

            results.append(SearchResult(
                content=self._clean_content(item.content),
                score=item.salience,
                memory_id=item.id,
                metadata=result_meta,
            ))
        return results

    def get_all(self, user_id: str) -> list[SearchResult]:
        """Get all stored memories."""
        items = self._neuromem.list(limit=1000)
        return [
            SearchResult(
                content=item.content,
                score=item.salience,
                memory_id=item.id,
            )
            for item in items
        ]

    def clear(self, user_id: str) -> None:
        """
        Delete all memories, including verbatim chunks.

        Paginated loop: list(limit) returns at most `limit` items, and a
        MemBench entry can produce thousands of verbatim chunks. Loop until
        list() returns zero so the next entry starts from a clean store and
        search latency doesn't grow unbounded across the run.
        """
        while True:
            items = self._neuromem.list(limit=2000)
            if not items:
                break
            for item in items:
                try:
                    self._neuromem.forget(item.id)
                except Exception:
                    pass

        # Reset the verbatim store's seen-hashes dedup cache so subsequent
        # entries can re-ingest identical content (different targets per entry).
        verbatim = getattr(self._neuromem.controller, "verbatim", None)
        if verbatim is not None:
            try:
                verbatim._seen_hashes.clear()
            except Exception:
                pass

    def teardown(self) -> None:
        """Clean up resources."""
        if self._neuromem:
            self._neuromem.close()
        if self._config_path and os.path.exists(self._config_path):
            os.unlink(self._config_path)

    def memory_count(self, user_id: str) -> int:
        """Return number of stored memories."""
        items = self._neuromem.list(limit=10000)
        return len(items)
