"""
Zep Cloud adapter for benchmarks.

Uses Zep's graph-based memory with temporal and semantic search.
Requires ZEP_API_KEY environment variable.

Install: pip install zep-cloud
Docs: https://help.getzep.com/
"""

import os
import uuid
from typing import Optional

from benchmarks.adapters.base import SearchResult


class ZepAdapter:
    """Adapter wrapping Zep Cloud for benchmarking."""

    def __init__(self) -> None:
        self._client = None
        self._user_id_map: dict[str, str] = {}  # bench user_id -> zep user_id

    @property
    def name(self) -> str:
        return "Zep"

    def setup(self, config: dict) -> None:
        """
        Initialize Zep Cloud client.

        Config keys:
            zep_api_key: str (default: ZEP_API_KEY env var)
        """
        try:
            from zep_cloud import Zep
        except ImportError:
            raise ImportError(
                "zep-cloud is required. Install with: pip install zep-cloud"
            )

        api_key = config.get("zep_api_key") or os.environ.get("ZEP_API_KEY")
        if not api_key:
            raise ValueError(
                "Zep requires ZEP_API_KEY environment variable or zep_api_key in config. "
                "Get your key at https://app.getzep.com/"
            )

        self._client = Zep(api_key=api_key)

    def _ensure_user(self, user_id: str) -> str:
        """Ensure a Zep user exists for the given benchmark user_id."""
        if user_id not in self._user_id_map:
            zep_user_id = f"bench_{user_id[:8]}"
            try:
                self._client.user.add(user_id=zep_user_id)
            except Exception:
                # User may already exist — that's fine
                pass
            self._user_id_map[user_id] = zep_user_id
        return self._user_id_map[user_id]

    def add_memory(
        self,
        user_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> str:
        """Store a memory via Zep's graph API."""
        zep_uid = self._ensure_user(user_id)
        self._client.graph.add(
            user_id=zep_uid,
            type="text",
            data=content,
        )
        return str(uuid.uuid4())

    def search(
        self,
        user_id: str,
        query: str,
        k: int = 10,
    ) -> list[SearchResult]:
        """Search memories using Zep's graph search."""
        zep_uid = self._user_id_map.get(user_id)
        if not zep_uid:
            return []

        try:
            results = self._client.graph.search(
                user_id=zep_uid,
                query=query,
                limit=k,
                scope="edges",
            )
        except Exception:
            return []

        search_results: list[SearchResult] = []
        items = getattr(results, "edges", None) or getattr(results, "results", None) or []
        for item in items:
            content = getattr(item, "fact", None) or getattr(item, "name", "") or str(item)
            score = getattr(item, "score", 0.0) or 0.0
            mem_id = getattr(item, "uuid", None) or str(uuid.uuid4())
            search_results.append(SearchResult(
                content=content,
                score=score,
                memory_id=mem_id,
            ))
        return search_results

    def get_all(self, user_id: str) -> list[SearchResult]:
        """Get all stored memories — approximated via broad search."""
        return self.search(user_id, "memory", k=1000)

    def clear(self, user_id: str) -> None:
        """Delete Zep user and all their data."""
        zep_uid = self._user_id_map.pop(user_id, None)
        if zep_uid:
            try:
                self._client.user.delete(user_id=zep_uid)
            except Exception:
                pass

    def teardown(self) -> None:
        """Clean up all created users."""
        for user_id in list(self._user_id_map.keys()):
            self.clear(user_id)
        self._client = None

    def memory_count(self, user_id: str) -> int:
        """Return approximate number of stored memories."""
        return len(self.get_all(user_id))
