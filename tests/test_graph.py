"""
Tests for MemoryGraph and Memory Links.
"""

import pytest
import uuid
from datetime import datetime, timezone
from neuromem.core.types import MemoryLink
from neuromem.core.graph import MemoryGraph


@pytest.fixture
def graph():
    return MemoryGraph()


@pytest.fixture
def sample_ids():
    return [str(uuid.uuid4()) for _ in range(5)]


def _make_link(source_id, target_id, link_type="related", strength=0.8):
    return MemoryLink(
        source_id=source_id,
        target_id=target_id,
        link_type=link_type,
        strength=strength,
        created_at=datetime.now(timezone.utc),
    )


class TestMemoryLink:
    def test_memory_link_creation(self):
        link = _make_link("a", "b")
        assert link.source_id == "a"
        assert link.target_id == "b"
        assert link.link_type == "related"
        assert link.strength == 0.8

    def test_memory_link_to_dict(self):
        link = _make_link("a", "b", "derived_from", 0.9)
        d = link.to_dict()
        assert d["source_id"] == "a"
        assert d["target_id"] == "b"
        assert d["link_type"] == "derived_from"
        assert d["strength"] == 0.9
        assert "created_at" in d


class TestMemoryGraphBasic:
    def test_add_link(self, graph, sample_ids):
        link = _make_link(sample_ids[0], sample_ids[1])
        graph.add_link(link)
        assert graph.edge_count == 1
        assert graph.node_count == 2

    def test_duplicate_link_updates_strength(self, graph, sample_ids):
        link1 = _make_link(sample_ids[0], sample_ids[1], strength=0.5)
        link2 = _make_link(sample_ids[0], sample_ids[1], strength=0.9)
        graph.add_link(link1)
        graph.add_link(link2)
        assert graph.edge_count == 1  # Not duplicated
        links = graph.get_links(sample_ids[0])
        assert links[0].strength == 0.9  # Updated to max

    def test_remove_link(self, graph, sample_ids):
        graph.add_link(_make_link(sample_ids[0], sample_ids[1]))
        assert graph.remove_link(sample_ids[0], sample_ids[1])
        assert graph.edge_count == 0

    def test_remove_nonexistent_link(self, graph):
        assert not graph.remove_link("x", "y")

    def test_remove_all_links(self, graph, sample_ids):
        graph.add_link(_make_link(sample_ids[0], sample_ids[1]))
        graph.add_link(_make_link(sample_ids[0], sample_ids[2]))
        graph.add_link(_make_link(sample_ids[3], sample_ids[0]))
        count = graph.remove_all_links(sample_ids[0])
        assert count == 3

    def test_get_links(self, graph, sample_ids):
        graph.add_link(_make_link(sample_ids[0], sample_ids[1], "related"))
        graph.add_link(_make_link(sample_ids[0], sample_ids[2], "derived_from"))
        all_links = graph.get_links(sample_ids[0])
        assert len(all_links) == 2
        related = graph.get_links(sample_ids[0], link_type="related")
        assert len(related) == 1

    def test_get_backlinks(self, graph, sample_ids):
        graph.add_link(_make_link(sample_ids[0], sample_ids[2]))
        graph.add_link(_make_link(sample_ids[1], sample_ids[2]))
        backlinks = graph.get_backlinks(sample_ids[2])
        assert len(backlinks) == 2


class TestMemoryGraphTraversal:
    def test_get_related_depth_1(self, graph, sample_ids):
        # A -> B -> C
        graph.add_link(_make_link(sample_ids[0], sample_ids[1]))
        graph.add_link(_make_link(sample_ids[1], sample_ids[2]))
        related = graph.get_related(sample_ids[0], depth=1)
        assert sample_ids[1] in related
        assert sample_ids[2] not in related  # Only depth=1

    def test_get_related_depth_2(self, graph, sample_ids):
        # A -> B -> C
        graph.add_link(_make_link(sample_ids[0], sample_ids[1]))
        graph.add_link(_make_link(sample_ids[1], sample_ids[2]))
        related = graph.get_related(sample_ids[0], depth=2)
        assert sample_ids[1] in related
        assert sample_ids[2] in related

    def test_get_related_bidirectional(self, graph, sample_ids):
        # A -> B (A links to B)
        graph.add_link(_make_link(sample_ids[0], sample_ids[1]))
        # Starting from B, should find A via backlink
        related = graph.get_related(sample_ids[1], depth=1)
        assert sample_ids[0] in related

    def test_get_related_no_duplicates(self, graph, sample_ids):
        # A -> B, A -> C, B -> C (diamond)
        graph.add_link(_make_link(sample_ids[0], sample_ids[1]))
        graph.add_link(_make_link(sample_ids[0], sample_ids[2]))
        graph.add_link(_make_link(sample_ids[1], sample_ids[2]))
        related = graph.get_related(sample_ids[0], depth=2)
        assert len(related) == len(set(related))  # No duplicates


class TestMemoryGraphClusters:
    def test_single_cluster(self, graph, sample_ids):
        graph.add_link(_make_link(sample_ids[0], sample_ids[1]))
        graph.add_link(_make_link(sample_ids[1], sample_ids[2]))
        clusters = graph.get_clusters()
        assert len(clusters) == 1
        assert len(clusters[0]) == 3

    def test_two_clusters(self, graph, sample_ids):
        # Cluster 1: 0 -> 1
        graph.add_link(_make_link(sample_ids[0], sample_ids[1]))
        # Cluster 2: 2 -> 3
        graph.add_link(_make_link(sample_ids[2], sample_ids[3]))
        clusters = graph.get_clusters()
        assert len(clusters) == 2

    def test_empty_graph_clusters(self, graph):
        assert graph.get_clusters() == []

    def test_bridge_memories_empty_when_fully_connected(self, graph, sample_ids):
        # When a bridge link connects clusters, union-find merges them
        # so no bridges exist in the final graph
        graph.add_link(_make_link(sample_ids[0], sample_ids[1]))
        graph.add_link(_make_link(sample_ids[2], sample_ids[3]))
        graph.add_link(_make_link(sample_ids[1], sample_ids[2]))
        # All 4 nodes are now in one cluster
        clusters = graph.get_clusters()
        assert len(clusters) == 1
        bridges = graph.get_bridge_memories()
        assert bridges == []  # No bridges when fully connected

    def test_bridge_memories_no_bridges_single_cluster(self, graph, sample_ids):
        graph.add_link(_make_link(sample_ids[0], sample_ids[1]))
        bridges = graph.get_bridge_memories()
        assert bridges == []


class TestMemoryGraphExport:
    def test_export(self, graph, sample_ids):
        graph.add_link(_make_link(sample_ids[0], sample_ids[1]))
        graph.add_link(_make_link(sample_ids[1], sample_ids[2]))
        export = graph.export()
        assert "nodes" in export
        assert "edges" in export
        assert export["node_count"] == 3
        assert export["edge_count"] == 2

    def test_export_empty(self, graph):
        export = graph.export()
        assert export["node_count"] == 0
        assert export["edge_count"] == 0


class TestControllerIntegration:
    """Test graph, conflict resolution, and reconsolidation in controller."""

    @pytest.fixture
    def neuromem_instance(self, tmp_path):
        config_content = """
neuromem:
  model:
    embedding: text-embedding-3-large
  storage:
    database:
      type: memory
  memory:
    decay_enabled: true
    consolidation_interval: 10
  async:
    enabled: false
  retrieval:
    hybrid_enabled: false
"""
        config_path = tmp_path / "test.yaml"
        config_path.write_text(config_content)
        from neuromem import NeuroMem

        user_id = str(uuid.uuid4())
        memory = NeuroMem.from_config(str(config_path), user_id=user_id)
        yield memory
        memory.close()

    def test_controller_has_graph(self, neuromem_instance):
        assert hasattr(neuromem_instance.controller, "graph")
        assert isinstance(neuromem_instance.controller.graph, MemoryGraph)

    def test_controller_has_conflict_resolver(self, neuromem_instance):
        from neuromem.core.policies.conflict_resolution import ConflictResolver

        assert isinstance(neuromem_instance.controller.conflict_resolver, ConflictResolver)

    def test_controller_has_reconsolidation_policy(self, neuromem_instance):
        from neuromem.core.policies.reconsolidation import ReconsolidationPolicy

        assert isinstance(
            neuromem_instance.controller.reconsolidation_policy, ReconsolidationPolicy
        )

    def test_retrieve_with_context_expansion(self, neuromem_instance):
        # Store some memories
        neuromem_instance.observe("I like Python", "Great!")
        neuromem_instance.observe("I use PyTorch", "Nice!")

        # Retrieve with context expansion (graph is empty so no expansion, but no crash)
        results = neuromem_instance.retrieve_with_context("Python frameworks")
        assert isinstance(results, list)

    def test_find_by_tags_empty(self, neuromem_instance):
        results = neuromem_instance.find_by_tags("topic:")
        assert results == []

    def test_get_tag_tree_empty(self, neuromem_instance):
        tree = neuromem_instance.get_tag_tree()
        assert isinstance(tree, dict)

    def test_get_graph_export(self, neuromem_instance):
        export = neuromem_instance.get_graph()
        assert "nodes" in export
        assert "edges" in export

    def test_get_memories_by_date(self, neuromem_instance):
        neuromem_instance.observe("Test memory", "Test response")
        from datetime import datetime

        memories = neuromem_instance.get_memories_by_date(datetime.now())
        assert isinstance(memories, list)

    def test_explain_includes_graph_info(self, neuromem_instance):
        neuromem_instance.observe("Test input", "Test output")
        memories = neuromem_instance.list(limit=1)
        if memories:
            explanation = neuromem_instance.explain(memories[0].id)
            assert "graph" in explanation
            assert "link_count" in explanation["graph"]
            assert "retrieval_stats" in explanation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
