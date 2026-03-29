"""Tests for DSPy adapter."""

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
    nm.retrieve_with_context.return_value = nm.retrieve.return_value
    return nm


dspy = pytest.importorskip("dspy")


class TestNeuroMemRetriever:
    def test_retriever_forward(self, mock_neuromem):
        from neuromem.adapters.dspy import NeuroMemRetriever

        retriever = NeuroMemRetriever(mock_neuromem, k=5)
        result = retriever.forward("python preferences")
        assert hasattr(result, "passages")
        assert len(result.passages) == 1
        assert "User prefers Python type annotations" in result.passages[0]

    def test_retriever_returns_prediction(self, mock_neuromem):
        from neuromem.adapters.dspy import NeuroMemRetriever

        retriever = NeuroMemRetriever(mock_neuromem, k=5)
        result = retriever("python preferences")
        assert isinstance(result, dspy.Prediction)

    def test_retriever_handles_exception(self, mock_neuromem):
        from neuromem.adapters.dspy import NeuroMemRetriever

        mock_neuromem.retrieve.side_effect = RuntimeError("connection lost")
        retriever = NeuroMemRetriever(mock_neuromem, k=5)
        result = retriever.forward("failing query")
        assert result.passages == []

    def test_retriever_custom_k(self, mock_neuromem):
        from neuromem.adapters.dspy import NeuroMemRetriever

        retriever = NeuroMemRetriever(mock_neuromem, k=3)
        retriever.forward("test", k=10)
        mock_neuromem.retrieve.assert_called_once_with(query="test", task_type="chat", k=10)


class TestCreateTools:
    def test_create_tools_returns_three(self, mock_neuromem):
        from neuromem.adapters.dspy import create_neuromem_tools

        tools = create_neuromem_tools(mock_neuromem)
        assert len(tools) == 3

    def test_tool_functions_are_callable(self, mock_neuromem):
        from neuromem.adapters.dspy import create_neuromem_tools

        tools = create_neuromem_tools(mock_neuromem)
        for tool in tools:
            assert callable(tool)

    def test_search_tool_returns_results(self, mock_neuromem):
        from neuromem.adapters.dspy import create_neuromem_tools

        tools = create_neuromem_tools(mock_neuromem)
        search = tools[0]
        result = search(query="python")
        assert "User prefers Python type annotations" in result

    def test_store_tool_stores_memory(self, mock_neuromem):
        from neuromem.adapters.dspy import create_neuromem_tools

        tools = create_neuromem_tools(mock_neuromem)
        store = tools[1]
        result = store(content="I like Go")
        assert "Memory stored" in result
        mock_neuromem.observe.assert_called_once()


class TestMemoryAugmentedQA:
    def test_init(self, mock_neuromem):
        from neuromem.adapters.dspy import MemoryAugmentedQA

        qa = MemoryAugmentedQA(mock_neuromem, k=5)
        assert qa.retrieve is not None
        assert qa.generate is not None
