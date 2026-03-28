"""Tests for CrewAI adapter."""

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
    nm.consolidate.return_value = None
    nm.retrieve_with_context.return_value = nm.retrieve.return_value
    return nm


crewai = pytest.importorskip("crewai")


class TestNeuroMemSearchTool:
    def test_search_tool_run(self, mock_neuromem):
        from neuromem.adapters.crewai import NeuroMemSearchTool

        tool = NeuroMemSearchTool(neuromem=mock_neuromem, k=5)
        result = tool._run(query="python preferences")
        assert "User prefers Python type annotations" in result
        assert "procedural" in result
        assert "conf:0.90" in result
        mock_neuromem.retrieve.assert_called_once()

    def test_search_tool_handles_empty_results(self, mock_neuromem):
        from neuromem.adapters.crewai import NeuroMemSearchTool

        mock_neuromem.retrieve.return_value = []
        tool = NeuroMemSearchTool(neuromem=mock_neuromem)
        result = tool._run(query="nothing here")
        assert "No relevant memories found" in result

    def test_search_tool_handles_exception(self, mock_neuromem):
        from neuromem.adapters.crewai import NeuroMemSearchTool

        mock_neuromem.retrieve.side_effect = RuntimeError("connection lost")
        tool = NeuroMemSearchTool(neuromem=mock_neuromem)
        result = tool._run(query="failing query")
        assert "temporarily unavailable" in result


class TestNeuroMemStoreTool:
    def test_store_tool_run(self, mock_neuromem):
        from neuromem.adapters.crewai import NeuroMemStoreTool

        tool = NeuroMemStoreTool(neuromem=mock_neuromem)
        result = tool._run(content="User likes dark mode")
        assert "Memory stored" in result
        mock_neuromem.observe.assert_called_once_with(
            "User likes dark mode", "Acknowledged", template=None
        )

    def test_store_tool_handles_exception(self, mock_neuromem):
        from neuromem.adapters.crewai import NeuroMemStoreTool

        mock_neuromem.observe.side_effect = RuntimeError("storage error")
        tool = NeuroMemStoreTool(neuromem=mock_neuromem)
        result = tool._run(content="failing content")
        assert "Failed" in result


class TestNeuroMemConsolidateTool:
    def test_consolidate_tool_run(self, mock_neuromem):
        from neuromem.adapters.crewai import NeuroMemConsolidateTool

        tool = NeuroMemConsolidateTool(neuromem=mock_neuromem)
        result = tool._run()
        assert "complete" in result
        mock_neuromem.consolidate.assert_called_once()


class TestNeuroMemContextTool:
    def test_context_tool_run(self, mock_neuromem):
        from neuromem.adapters.crewai import NeuroMemContextTool

        tool = NeuroMemContextTool(neuromem=mock_neuromem, k=8)
        result = tool._run(query="python preferences")
        assert "User prefers Python type annotations" in result
        mock_neuromem.retrieve_with_context.assert_called_once()


class TestCreateTools:
    def test_create_tools_returns_four(self, mock_neuromem):
        from neuromem.adapters.crewai import create_neuromem_tools

        tools = create_neuromem_tools(mock_neuromem, k=5)
        assert len(tools) == 4

    def test_tools_have_correct_names(self, mock_neuromem):
        from neuromem.adapters.crewai import create_neuromem_tools

        tools = create_neuromem_tools(mock_neuromem)
        names = [t.name for t in tools]
        assert "neuromem_search" in names
        assert "neuromem_store" in names
        assert "neuromem_consolidate" in names
        assert "neuromem_context" in names
