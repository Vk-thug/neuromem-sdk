"""Tests for Haystack adapter."""

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


haystack = pytest.importorskip("haystack")


class TestNeuroMemRetriever:
    def test_retriever_run(self, mock_neuromem):
        from neuromem.adapters.haystack import NeuroMemRetriever

        retriever = NeuroMemRetriever(mock_neuromem, top_k=5)
        result = retriever.run(query="python preferences")
        assert "documents" in result
        assert len(result["documents"]) == 1
        mock_neuromem.retrieve.assert_called_once()

    def test_retriever_returns_documents(self, mock_neuromem):
        from neuromem.adapters.haystack import NeuroMemRetriever
        from haystack import Document

        retriever = NeuroMemRetriever(mock_neuromem, top_k=5)
        result = retriever.run(query="test")
        doc = result["documents"][0]
        assert isinstance(doc, Document)
        assert doc.content == "User prefers Python type annotations"
        assert doc.meta["memory_type"] == "procedural"
        assert doc.meta["confidence"] == 0.9

    def test_retriever_handles_exception(self, mock_neuromem):
        from neuromem.adapters.haystack import NeuroMemRetriever

        mock_neuromem.retrieve.side_effect = RuntimeError("connection lost")
        retriever = NeuroMemRetriever(mock_neuromem, top_k=5)
        result = retriever.run(query="failing")
        assert result["documents"] == []

    def test_retriever_custom_top_k(self, mock_neuromem):
        from neuromem.adapters.haystack import NeuroMemRetriever

        retriever = NeuroMemRetriever(mock_neuromem, top_k=3)
        retriever.run(query="test", top_k=10)
        mock_neuromem.retrieve.assert_called_once_with(
            query="test", task_type="chat", k=10
        )


class TestNeuroMemWriter:
    def test_writer_run(self, mock_neuromem):
        from neuromem.adapters.haystack import NeuroMemWriter
        from haystack import Document

        writer = NeuroMemWriter(mock_neuromem)
        docs = [Document(content="Important fact", meta={"response": "Noted"})]
        result = writer.run(documents=docs)
        assert result["memories_written"] == 1
        mock_neuromem.observe.assert_called_once()

    def test_writer_counts_written(self, mock_neuromem):
        from neuromem.adapters.haystack import NeuroMemWriter
        from haystack import Document

        writer = NeuroMemWriter(mock_neuromem)
        docs = [
            Document(content="Fact 1", meta={}),
            Document(content="Fact 2", meta={}),
            Document(content="Fact 3", meta={}),
        ]
        result = writer.run(documents=docs)
        assert result["memories_written"] == 3

    def test_writer_handles_partial_failure(self, mock_neuromem):
        from neuromem.adapters.haystack import NeuroMemWriter
        from haystack import Document

        mock_neuromem.observe.side_effect = [None, RuntimeError("fail"), None]
        writer = NeuroMemWriter(mock_neuromem)
        docs = [
            Document(content="Good 1", meta={}),
            Document(content="Bad", meta={}),
            Document(content="Good 2", meta={}),
        ]
        result = writer.run(documents=docs)
        assert result["memories_written"] == 2


class TestNeuroMemContextRetriever:
    def test_context_retriever_run(self, mock_neuromem):
        from neuromem.adapters.haystack import NeuroMemContextRetriever

        retriever = NeuroMemContextRetriever(mock_neuromem, top_k=5)
        result = retriever.run(query="python preferences")
        assert "documents" in result
        assert len(result["documents"]) == 1
        mock_neuromem.retrieve_with_context.assert_called_once()

    def test_context_retriever_includes_metadata(self, mock_neuromem):
        from neuromem.adapters.haystack import NeuroMemContextRetriever

        retriever = NeuroMemContextRetriever(mock_neuromem, top_k=5)
        result = retriever.run(query="test")
        doc = result["documents"][0]
        assert "expanded_context" in doc.meta
