"""Tests for Semantic Kernel adapter."""

import pytest
from unittest.mock import MagicMock
from datetime import datetime
from neuromem.core.types import MemoryItem, MemoryType


@pytest.fixture
def mock_neuromem():
    """Create a mock NeuroMem instance."""
    nm = MagicMock()
    nm.retrieve.return_value = [
        MemoryItem(
            id="mem-001",
            user_id="test",
            content="User prefers Python type annotations",
            embedding=[0.1] * 10,
            memory_type=MemoryType.PROCEDURAL,
            salience=0.8,
            confidence=0.9,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            decay_rate=0.01,
            reinforcement=3,
            inferred=False,
            editable=True,
            tags=["preference", "python"],
            metadata={},
            strength=0.85,
        ),
    ]
    nm.observe.return_value = None
    nm.list.return_value = nm.retrieve.return_value
    nm.consolidate.return_value = None
    nm.retrieve_with_context.return_value = nm.retrieve.return_value
    return nm


sk = pytest.importorskip("semantic_kernel")


class TestNeuroMemPlugin:
    def test_plugin_search_memory(self, mock_neuromem):
        from neuromem.adapters.semantic_kernel import NeuroMemPlugin

        plugin = NeuroMemPlugin(mock_neuromem, k=5)
        result = plugin.search_memory(query="python preferences")
        assert "User prefers Python type annotations" in result
        assert "procedural" in result
        mock_neuromem.retrieve.assert_called_once()

    def test_plugin_search_empty(self, mock_neuromem):
        from neuromem.adapters.semantic_kernel import NeuroMemPlugin

        mock_neuromem.retrieve.return_value = []
        plugin = NeuroMemPlugin(mock_neuromem, k=5)
        result = plugin.search_memory(query="nothing")
        assert "No relevant memories found" in result

    def test_plugin_store_memory(self, mock_neuromem):
        from neuromem.adapters.semantic_kernel import NeuroMemPlugin

        plugin = NeuroMemPlugin(mock_neuromem, k=5)
        result = plugin.store_memory(content="User likes dark mode")
        assert "Memory stored" in result
        mock_neuromem.observe.assert_called_once()

    def test_plugin_list_memories(self, mock_neuromem):
        from neuromem.adapters.semantic_kernel import NeuroMemPlugin

        plugin = NeuroMemPlugin(mock_neuromem, k=5)
        result = plugin.list_memories()
        assert "Found 1 memories" in result
        assert "procedural" in result

    def test_plugin_list_empty(self, mock_neuromem):
        from neuromem.adapters.semantic_kernel import NeuroMemPlugin

        mock_neuromem.list.return_value = []
        plugin = NeuroMemPlugin(mock_neuromem, k=5)
        result = plugin.list_memories()
        assert "No memories found" in result

    def test_plugin_consolidate(self, mock_neuromem):
        from neuromem.adapters.semantic_kernel import NeuroMemPlugin

        plugin = NeuroMemPlugin(mock_neuromem, k=5)
        result = plugin.consolidate_memories()
        assert "complete" in result
        mock_neuromem.consolidate.assert_called_once()

    def test_plugin_get_context(self, mock_neuromem):
        from neuromem.adapters.semantic_kernel import NeuroMemPlugin

        plugin = NeuroMemPlugin(mock_neuromem, k=5)
        result = plugin.get_context(query="python")
        assert "User prefers Python type annotations" in result
        mock_neuromem.retrieve_with_context.assert_called_once()

    def test_plugin_handles_search_exception(self, mock_neuromem):
        from neuromem.adapters.semantic_kernel import NeuroMemPlugin

        mock_neuromem.retrieve.side_effect = RuntimeError("fail")
        plugin = NeuroMemPlugin(mock_neuromem, k=5)
        result = plugin.search_memory(query="test")
        assert "temporarily unavailable" in result


class TestCreatePlugin:
    def test_create_plugin(self, mock_neuromem):
        from neuromem.adapters.semantic_kernel import create_neuromem_plugin

        plugin = create_neuromem_plugin(mock_neuromem, k=5)
        assert plugin is not None
        assert plugin.name == "neuromem"

    def test_create_plugin_custom_name(self, mock_neuromem):
        from neuromem.adapters.semantic_kernel import create_neuromem_plugin

        plugin = create_neuromem_plugin(mock_neuromem, k=5, plugin_name="memory")
        assert plugin.name == "memory"
