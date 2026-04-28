"""
Tests for v0.4.0 UI server (FastAPI routes + audit log streaming).

Uses a mock NeuroMem so we don't need Ollama / OpenAI / Qdrant in CI.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from neuromem.core.audit.retrieval_log import (  # noqa: E402
    RetrievalStage,
    default_log as default_retrieval_log,
)
from neuromem.core.audit.observation_log import (  # noqa: E402
    default_log as default_observation_log,
)
from neuromem.core.types import MemoryItem, MemoryType, RetrievalResult  # noqa: E402


def _build_item(memory_id: str, content: str, mt: MemoryType = MemoryType.EPISODIC) -> MemoryItem:
    return MemoryItem(
        id=memory_id,
        user_id="u1",
        content=content,
        embedding=[0.0],
        memory_type=mt,
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
def mock_memory() -> Any:
    """Builds a NeuroMem-shaped mock with the surface the UI server reads."""
    items = [
        _build_item("m1", "User prefers Python", MemoryType.SEMANTIC),
        _build_item("m2", "User likes dark mode", MemoryType.PROCEDURAL),
        _build_item("m3", "User finished onboarding"),
    ]

    backend = MagicMock()
    backend.get_by_id.side_effect = lambda mid: next((i for i in items if i.id == mid), None)

    graph = MagicMock()
    graph.export.return_value = {
        "nodes": ["m1", "m2", "m3"],
        "edges": [
            {
                "source_id": "m1",
                "target_id": "m2",
                "link_type": "related",
                "strength": 0.6,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "metadata": {},
            }
        ],
        "node_count": 3,
        "edge_count": 1,
    }
    graph.node_count = 3
    graph.edge_count = 1
    graph.get_related.return_value = ["m2"]
    graph.get_links.return_value = []

    controller = MagicMock()
    controller.graph = graph
    controller.episodic.backend = backend
    controller.brain = None  # brain off in tests

    memory = MagicMock()
    memory.user_id = "u1"
    memory.controller = controller
    memory.list.return_value = items
    memory.forget.return_value = None
    memory.explain.return_value = {"id": "m1", "score_breakdown": {}}
    memory.retrieve.return_value = RetrievalResult(items=items[:2])
    return memory


@pytest.fixture
def client(mock_memory: Any) -> TestClient:
    from neuromem.ui.server import create_app

    app = create_app(mock_memory)
    return TestClient(app)


class TestHealth:
    def test_health(self, client: TestClient) -> None:
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["version"] == "0.4.0"
        assert body["graph"]["nodes"] == 3
        assert body["audit"]["retrieval_log_enabled"] is True


class TestMemoriesRoutes:
    def test_list_memories(self, client: TestClient) -> None:
        r = client.get("/api/memories?limit=10")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 3
        # Embedding must be stripped (otherwise 3072-dim payloads kill the UI).
        for item in body["items"]:
            assert "embedding" not in item

    def test_get_memory_by_id(self, client: TestClient) -> None:
        r = client.get("/api/memories/m2")
        assert r.status_code == 200
        assert r.json()["id"] == "m2"

    def test_get_memory_404(self, client: TestClient) -> None:
        r = client.get("/api/memories/missing")
        assert r.status_code == 404

    def test_explain(self, client: TestClient) -> None:
        r = client.get("/api/memories/m1/explain")
        assert r.status_code == 200
        assert r.json()["id"] == "m1"

    def test_delete(self, client: TestClient) -> None:
        r = client.delete("/api/memories/m1")
        assert r.status_code == 200
        assert r.json()["status"] == "deleted"

    def test_search(self, client: TestClient) -> None:
        r = client.post("/api/memories/search", json={"query": "preferences", "k": 5})
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 2
        assert "confidence" in body
        assert "abstained" in body


class TestGraphRoutes:
    def test_2d(self, client: TestClient) -> None:
        r = client.get("/api/graph/2d")
        assert r.status_code == 200
        body = r.json()
        assert body["node_count"] == 3
        assert body["edge_count"] == 1
        assert all("memory_type" in n for n in body["nodes"])

    def test_3d_assigns_anatomical_regions(self, client: TestClient) -> None:
        r = client.get("/api/graph/3d")
        assert r.status_code == 200
        body = r.json()
        # Each non-orphan node must have a region from the anatomical set.
        valid_regions = {
            "hippocampus",
            "neocortex",
            "basal_ganglia",
            "amygdala",
            "prefrontal_cortex",
        }
        for n in body["nodes"]:
            assert n["region"] in valid_regions

    def test_3d_episodic_lands_in_hippocampus(self, client: TestClient) -> None:
        body = client.get("/api/graph/3d").json()
        episodic_node = next(n for n in body["nodes"] if n["id"] == "m3")
        assert episodic_node["region"] == "hippocampus"

    def test_3d_semantic_lands_in_neocortex(self, client: TestClient) -> None:
        body = client.get("/api/graph/3d").json()
        semantic_node = next(n for n in body["nodes"] if n["id"] == "m1")
        assert semantic_node["region"] == "neocortex"

    def test_3d_procedural_lands_in_basal_ganglia(self, client: TestClient) -> None:
        body = client.get("/api/graph/3d").json()
        procedural_node = next(n for n in body["nodes"] if n["id"] == "m2")
        assert procedural_node["region"] == "basal_ganglia"

    def test_ego_graph(self, client: TestClient) -> None:
        r = client.get("/api/graph/ego/m1?depth=2")
        assert r.status_code == 200
        body = r.json()
        assert body["center"] == "m1"
        node_ids = {n["id"] for n in body["nodes"]}
        assert "m1" in node_ids
        assert "m2" in node_ids


class TestRetrievalRoutes:
    def setup_method(self) -> None:
        # Reset audit log between tests to keep assertions deterministic.
        default_retrieval_log.disable()
        default_retrieval_log._buf.clear()
        default_retrieval_log._index.clear()
        default_retrieval_log.enable()

    def test_list_empty(self, client: TestClient) -> None:
        r = client.get("/api/retrievals")
        assert r.status_code == 200
        # Audit log starts empty for this test class.
        assert r.json()["count"] == 0

    def test_list_after_recording_a_run(self, client: TestClient) -> None:
        run = default_retrieval_log.begin(user_id="u", query="hi", task_type="chat", k=3)
        default_retrieval_log.add_stage(
            run, RetrievalStage(name="vector_search", elapsed_ms=1.0, candidate_count=10)
        )
        default_retrieval_log.finish(run, [{"id": "m1", "score": 0.9}])

        r = client.get("/api/retrievals")
        assert r.json()["count"] == 1
        run_record = r.json()["runs"][0]
        assert run_record["query"] == "hi"
        assert run_record["status"] == "completed"
        assert len(run_record["stages"]) == 1

    def test_get_run_by_id(self, client: TestClient) -> None:
        run = default_retrieval_log.begin(user_id="u", query="x", task_type="chat", k=1)
        default_retrieval_log.finish(run, [])
        r = client.get(f"/api/retrievals/{run.id}")
        assert r.status_code == 200
        assert r.json()["id"] == run.id

    def test_get_run_404(self, client: TestClient) -> None:
        r = client.get("/api/retrievals/does-not-exist")
        assert r.status_code == 404


class TestObservationRoutes:
    def setup_method(self) -> None:
        default_observation_log.disable()
        default_observation_log._buf.clear()
        default_observation_log.enable()

    def test_list_empty(self, client: TestClient) -> None:
        r = client.get("/api/observations")
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_list_after_record(self, client: TestClient) -> None:
        default_observation_log.record(
            user_id="u", user_text="hi", assistant_text="ok", salience=0.6
        )
        r = client.get("/api/observations")
        assert r.json()["count"] == 1
        assert r.json()["events"][0]["user_text"] == "hi"


class TestBrainRoute:
    def test_brain_off(self, client: TestClient) -> None:
        r = client.get("/api/brain/state")
        assert r.status_code == 200
        assert r.json()["enabled"] is False


class TestMcpConfigRoute:
    def test_default_no_tunnel(self, client: TestClient, tmp_path, monkeypatch) -> None:
        # Force the helper to look in an empty home dir.
        monkeypatch.setenv("HOME", str(tmp_path))
        # Re-import is unnecessary; the route reads HOME on each call.
        r = client.get("/api/mcp-config")
        assert r.status_code == 200
        body = r.json()
        # Whether or not a real ~/.neuromem/mcp-public.json exists on the
        # dev box, the response shape must be stable.
        assert "blobs" in body
        assert "tunnel" in body


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
