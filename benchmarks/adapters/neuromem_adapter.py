"""
NeuroMem SDK adapter for benchmarks.

Supports both in-memory backend (for quick testing) and Qdrant backend
(for production-grade benchmarks matching real deployment).
"""

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

    @property
    def name(self) -> str:
        return f"NeuroMem (v0.2.0, {self._backend})"

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
                    "hybrid_enabled": True,  # Enable multi-signal ranking
                    # In benchmark mode all memories have the same base salience,
                    # so pure similarity should dominate ranking
                    "similarity_weight": 0.70,
                    "importance_weight": 0.15,
                    "recency_weight": 0.15,
                    "recency_half_life_days": 1,  # All memories same age in bench
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

        self._neuromem.observe(
            user_input=formatted,
            assistant_output="Memory stored.",
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
        items = self._neuromem.retrieve(query=query, task_type="chat", k=k)
        results: list[SearchResult] = []
        for item in items:
            results.append(SearchResult(
                content=self._clean_content(item.content),
                score=item.salience,
                memory_id=item.id,
                metadata={
                    "memory_type": item.memory_type.value,
                    "confidence": item.confidence,
                    "tags": item.tags,
                },
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
        """Delete all memories."""
        items = self._neuromem.list(limit=1000)
        for item in items:
            try:
                self._neuromem.forget(item.id)
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
