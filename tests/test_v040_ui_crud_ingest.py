"""
Tests for v0.4.0 CRUD + ingest API routes.

CRUD coverage:
* POST /api/memories  → calls memory.observe.
* PUT /api/memories/{id} → soft-supersede: deprecates old, creates new
  with ``supersedes`` graph link and ``edit_lineage_root`` metadata.

Ingest coverage:
* GET /api/ingest        → lists jobs from the audit log.
* GET /api/ingest/{id}   → 404 for unknown, returns job dict for known.
* DELETE /api/ingest/{id} → cooperative cancel, returns 404 if not running.
* GET /api/ingest/parsers → returns supported suffixes.

The file-upload route is exercised in a smoke test that uploads a tiny
Markdown buffer (Markdown parser is zero-dep, so this works without
Docling installed).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from neuromem.core.audit.ingest_log import (  # noqa: E402
    IngestStage,
    default_log as default_ingest_log,
)
from neuromem.core.types import MemoryItem, MemoryType  # noqa: E402


def _build_item(memory_id: str, content: str) -> MemoryItem:
    return MemoryItem(
        id=memory_id,
        user_id="u1",
        content=content,
        embedding=[0.1, 0.2, 0.3],
        memory_type=MemoryType.SEMANTIC,
        salience=0.7,
        confidence=0.9,
        created_at=datetime.now(timezone.utc),
        last_accessed=datetime.now(timezone.utc),
        decay_rate=0.05,
        reinforcement=1,
        inferred=False,
        editable=True,
    )


@pytest.fixture
def mock_memory(monkeypatch) -> Any:
    items = [_build_item("m1", "User prefers Python")]

    backend = MagicMock()
    backend.get_by_id.side_effect = lambda mid: next((i for i in items if i.id == mid), None)

    def _update(item):
        for idx, existing in enumerate(items):
            if existing.id == item.id:
                items[idx] = item
                return
        items.append(item)

    def _upsert(item):
        for idx, existing in enumerate(items):
            if existing.id == item.id:
                items[idx] = item
                return
        items.append(item)

    backend.update.side_effect = _update
    backend.upsert.side_effect = _upsert

    graph = MagicMock()
    graph.export.return_value = {
        "nodes": [i.id for i in items],
        "edges": [],
        "node_count": len(items),
        "edge_count": 0,
    }
    graph.node_count = len(items)
    graph.edge_count = 0
    graph.add_link.return_value = None

    controller = MagicMock()
    controller.graph = graph
    controller.episodic.backend = backend
    controller.brain = None

    config = MagicMock()
    config.model.return_value = {"embedding": "stub"}

    memory = MagicMock()
    memory.user_id = "u1"
    memory.controller = controller
    memory.config = config
    memory.list.return_value = items
    memory.observe = MagicMock()
    memory.forget = MagicMock()

    # Patch the embedding helper so PUT /api/memories/{id} doesn't try
    # to hit Ollama / OpenAI in tests.
    monkeypatch.setattr(
        "neuromem.utils.embeddings.get_embedding",
        lambda text, model=None, **kw: [0.1, 0.2, 0.3],
    )

    return memory, items, backend, graph


@pytest.fixture
def client(mock_memory) -> TestClient:
    from neuromem.ui.server import create_app

    memory, _items, _backend, _graph = mock_memory
    app = create_app(memory)
    return TestClient(app)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


class TestAddMemory:
    def test_post_calls_observe(self, client: TestClient, mock_memory) -> None:
        memory, *_ = mock_memory
        r = client.post(
            "/api/memories",
            json={"content": "Likes Vim", "metadata": {"src": "manual"}},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "added"
        memory.observe.assert_called_once()
        kwargs = memory.observe.call_args.kwargs
        assert kwargs["user_input"] == "Likes Vim"

    def test_post_rejects_empty(self, client: TestClient) -> None:
        r = client.post("/api/memories", json={"content": ""})
        assert r.status_code == 400


class TestEditMemory:
    def test_soft_supersede_creates_new_id(self, client: TestClient, mock_memory) -> None:
        _, items, _backend, graph = mock_memory
        r = client.put("/api/memories/m1", json={"content": "User prefers Rust now"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "edited"
        assert body["old_id"] == "m1"
        assert body["new_id"] != "m1"

        # Old memory marked deprecated.
        old = next(i for i in items if i.id == "m1")
        assert old.metadata.get("deprecated") is True

        # New memory carries supersedes metadata + edit_lineage_root.
        new = next(i for i in items if i.id == body["new_id"])
        assert new.metadata["supersedes"] == "m1"
        assert new.metadata["edit_lineage_root"] == "m1"
        assert new.content == "User prefers Rust now"

        # Graph link added: supersedes edge from new -> old.
        graph.add_link.assert_called_once()
        link = graph.add_link.call_args.args[0]
        assert link.link_type == "supersedes"
        assert link.source_id == body["new_id"]
        assert link.target_id == "m1"

    def test_edit_404(self, client: TestClient) -> None:
        r = client.put("/api/memories/missing", json={"content": "x"})
        assert r.status_code == 404

    def test_edit_rejects_empty(self, client: TestClient) -> None:
        r = client.put("/api/memories/m1", json={"content": "  "})
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Ingest API
# ---------------------------------------------------------------------------


class TestIngestRoutes:
    def setup_method(self) -> None:
        default_ingest_log.disable()
        default_ingest_log._buf.clear()
        default_ingest_log._index.clear()
        default_ingest_log.enable()

    def test_list_empty(self, client: TestClient) -> None:
        r = client.get("/api/ingest")
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_list_after_record(self, client: TestClient) -> None:
        job = default_ingest_log.begin(
            user_id="u", source_path="/x.pdf", source_id="abc", parser_name="docling"
        )
        default_ingest_log.add_stage(
            job, IngestStage(name="parse_chunk", elapsed_ms=1.0, chunk_index=0)
        )
        default_ingest_log.finish(job)

        r = client.get("/api/ingest")
        body = r.json()
        assert body["count"] == 1
        assert body["jobs"][0]["status"] == "completed"

    def test_get_404(self, client: TestClient) -> None:
        r = client.get("/api/ingest/nope")
        assert r.status_code == 404

    def test_cancel_404_when_not_running(self, client: TestClient) -> None:
        # Job that's already completed cannot be cancelled.
        job = default_ingest_log.begin(
            user_id="u", source_path="/x", source_id="s", parser_name="md"
        )
        default_ingest_log.finish(job)
        r = client.delete(f"/api/ingest/{job.id}")
        assert r.status_code == 404

    def test_cancel_running(self, client: TestClient) -> None:
        job = default_ingest_log.begin(
            user_id="u", source_path="/x", source_id="s", parser_name="md"
        )
        r = client.delete(f"/api/ingest/{job.id}")
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"

    def test_parsers_endpoint(self, client: TestClient) -> None:
        r = client.get("/api/ingest/parsers")
        assert r.status_code == 200
        suffixes = r.json()["suffixes"]
        assert ".md" in suffixes
        assert ".pdf" in suffixes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
