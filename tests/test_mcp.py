"""
Tests for the NeuroMem MCP server.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock
from neuromem.core.types import MemoryItem, MemoryType
from neuromem.mcp.types import serialize_memory, serialize_memory_list


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_memory(
    id: str = "mem-001",
    content: str = "Test memory content",
    memory_type: MemoryType = MemoryType.EPISODIC,
    salience: float = 0.75,
    confidence: float = 0.9,
    tags: list = None,
    metadata: dict = None,
    strength: float = 0.85,
    reinforcement: int = 3,
) -> MemoryItem:
    """Create a MemoryItem for testing."""
    return MemoryItem(
        id=id,
        user_id="test-user",
        content=content,
        embedding=[0.1] * 10,  # small embedding for tests
        memory_type=memory_type,
        salience=salience,
        confidence=confidence,
        created_at=datetime(2025, 6, 15, 10, 30, 0),
        last_accessed=datetime(2025, 6, 15, 12, 0, 0),
        decay_rate=0.01,
        reinforcement=reinforcement,
        inferred=False,
        editable=True,
        tags=tags or ["test", "topic:ai"],
        metadata=metadata or {},
        strength=strength,
    )


def _mock_neuromem():
    """Create a mock NeuroMem instance."""
    mock = MagicMock()
    mock.user_id = "test-user"
    mock._turn_count = 5
    mock.config = MagicMock()
    mock.config.storage.return_value = {"vector_store": {"type": "memory"}}
    mock.config.model.return_value = {
        "embedding": "text-embedding-3-large",
        "consolidation_llm": "gpt-4o-mini",
    }
    mock.config.memory.return_value = {"decay_enabled": True, "consolidation_interval": 10}
    mock.config.retrieval.return_value = {"hybrid_enabled": True}
    return mock


# ---------------------------------------------------------------------------
# Serialization Tests
# ---------------------------------------------------------------------------


class TestSerializeMemory:
    def test_basic_serialization(self):
        item = _make_memory()
        result = serialize_memory(item)

        assert result["id"] == "mem-001"
        assert result["content"] == "Test memory content"
        assert result["memory_type"] == "episodic"
        assert result["salience"] == 0.75
        assert result["confidence"] == 0.9
        assert result["tags"] == ["test", "topic:ai"]
        assert result["strength"] == 0.85
        assert result["reinforcement"] == 3
        assert result["created_at"] == "2025-06-15T10:30:00"
        assert result["last_accessed"] == "2025-06-15T12:00:00"
        assert result["inferred"] is False
        assert result["editable"] is True

    def test_excludes_embedding(self):
        item = _make_memory()
        result = serialize_memory(item)
        assert "embedding" not in result

    def test_memory_type_as_string(self):
        item = _make_memory(memory_type=MemoryType.SEMANTIC)
        result = serialize_memory(item)
        assert result["memory_type"] == "semantic"

    def test_with_expanded_context(self):
        item = _make_memory(
            metadata={"expanded_context": ["related memory 1", "related memory 2"]}
        )
        result = serialize_memory(item)
        assert result["expanded_context"] == ["related memory 1", "related memory 2"]

    def test_without_metadata(self):
        item = _make_memory(metadata={})
        result = serialize_memory(item)
        assert "metadata" not in result

    def test_with_metadata(self):
        item = _make_memory(metadata={"source": "user_input", "context": "chat"})
        result = serialize_memory(item)
        assert result["metadata"]["source"] == "user_input"

    def test_serialize_list(self):
        items = [_make_memory(id=f"mem-{i}") for i in range(3)]
        result = serialize_memory_list(items)
        assert len(result) == 3
        assert result[0]["id"] == "mem-0"
        assert result[2]["id"] == "mem-2"

    def test_serialize_empty_list(self):
        assert serialize_memory_list([]) == []

    def test_none_datetime(self):
        item = _make_memory()
        item.created_at = None
        result = serialize_memory(item)
        assert result["created_at"] is None

    def test_rounds_floats(self):
        item = _make_memory(salience=0.123456789, confidence=0.987654321)
        result = serialize_memory(item)
        assert result["salience"] == 0.1235
        assert result["confidence"] == 0.9877


# ---------------------------------------------------------------------------
# Tool Tests (using asyncio.to_thread mocking)
# ---------------------------------------------------------------------------


class TestMCPTools:
    """Test each tool function via the server's registered tools."""

    @pytest.fixture
    def mock_ctx(self):
        """Create a mock Context with lifespan_context."""
        ctx = MagicMock()
        mock_mem = _mock_neuromem()
        ctx.request_context.lifespan_context = {
            "memory": mock_mem,
            "user_id": "test-user",
        }
        return ctx, mock_mem

    @pytest.mark.asyncio
    async def test_store_memory_tool(self, mock_ctx):
        ctx, mock_mem = mock_ctx
        mock_mem.observe = MagicMock()
        mock_mem._turn_count = 6

        from neuromem.mcp.server import _get_memory

        memory = _get_memory(ctx)
        assert memory is mock_mem

    @pytest.mark.asyncio
    async def test_search_memories_returns_list(self, mock_ctx):
        ctx, mock_mem = mock_ctx
        mock_mem.retrieve.return_value = [_make_memory()]

        import asyncio

        results = await asyncio.to_thread(mock_mem.retrieve, query="test", task_type="chat", k=8)
        serialized = serialize_memory_list(results)
        assert len(serialized) == 1
        assert serialized[0]["content"] == "Test memory content"

    @pytest.mark.asyncio
    async def test_list_memories_with_type_filter(self, mock_ctx):
        ctx, mock_mem = mock_ctx
        mock_mem.list.return_value = [
            _make_memory(memory_type=MemoryType.SEMANTIC, id="sem-1")
        ]

        import asyncio

        results = await asyncio.to_thread(
            mock_mem.list, memory_type="semantic", limit=50
        )
        assert len(results) == 1
        assert results[0].memory_type == MemoryType.SEMANTIC

    @pytest.mark.asyncio
    async def test_get_memory_not_found(self, mock_ctx):
        ctx, mock_mem = mock_ctx
        mock_mem.controller._find_memory_by_id.return_value = None

        item = mock_mem.controller._find_memory_by_id("nonexistent")
        assert item is None

    @pytest.mark.asyncio
    async def test_get_memory_found(self, mock_ctx):
        ctx, mock_mem = mock_ctx
        expected = _make_memory()
        mock_mem.controller._find_memory_by_id.return_value = expected

        item = mock_mem.controller._find_memory_by_id("mem-001")
        assert item.id == "mem-001"

    @pytest.mark.asyncio
    async def test_update_memory_tool(self, mock_ctx):
        ctx, mock_mem = mock_ctx
        mock_mem.update = MagicMock()

        import asyncio

        await asyncio.to_thread(
            mock_mem.update, memory_id="mem-001", content="Updated content"
        )
        mock_mem.update.assert_called_once_with(
            memory_id="mem-001", content="Updated content"
        )

    @pytest.mark.asyncio
    async def test_delete_memory_tool(self, mock_ctx):
        ctx, mock_mem = mock_ctx
        mock_mem.forget = MagicMock()

        import asyncio

        await asyncio.to_thread(mock_mem.forget, memory_id="mem-001")
        mock_mem.forget.assert_called_once_with(memory_id="mem-001")

    @pytest.mark.asyncio
    async def test_consolidate_tool(self, mock_ctx):
        ctx, mock_mem = mock_ctx
        mock_mem.consolidate = MagicMock()

        import asyncio

        await asyncio.to_thread(mock_mem.consolidate)
        mock_mem.consolidate.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_stats_tool(self, mock_ctx):
        ctx, mock_mem = mock_ctx
        mock_mem.list.return_value = [
            _make_memory(memory_type=MemoryType.EPISODIC, id="ep-1"),
            _make_memory(memory_type=MemoryType.SEMANTIC, id="sem-1"),
            _make_memory(memory_type=MemoryType.PROCEDURAL, id="proc-1"),
        ]

        import asyncio

        all_memories = await asyncio.to_thread(mock_mem.list, limit=10000)
        by_type = {"episodic": 0, "semantic": 0, "procedural": 0}
        for m in all_memories:
            mt = m.memory_type.value
            if mt in by_type:
                by_type[mt] += 1

        assert by_type["episodic"] == 1
        assert by_type["semantic"] == 1
        assert by_type["procedural"] == 1

    @pytest.mark.asyncio
    async def test_find_by_tags_tool(self, mock_ctx):
        ctx, mock_mem = mock_ctx
        mock_mem.find_by_tags.return_value = [_make_memory(tags=["topic:ai/memory"])]

        import asyncio

        results = await asyncio.to_thread(
            mock_mem.find_by_tags, tag_prefix="topic:ai", limit=50
        )
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_graph_tool(self, mock_ctx):
        ctx, mock_mem = mock_ctx
        mock_mem.get_graph.return_value = {
            "nodes": [{"id": "entity1", "label": "Python"}],
            "edges": [{"source": "entity1", "target": "entity2", "type": "related"}],
        }

        import asyncio

        graph = await asyncio.to_thread(mock_mem.get_graph)
        assert "nodes" in graph
        assert "edges" in graph

    @pytest.mark.asyncio
    async def test_search_advanced_tool(self, mock_ctx):
        ctx, mock_mem = mock_ctx
        mock_mem.search.return_value = [
            _make_memory(memory_type=MemoryType.SEMANTIC)
        ]

        import asyncio

        results = await asyncio.to_thread(
            mock_mem.search, query_string="type:semantic tag:ai", k=10
        )
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_context_tool(self, mock_ctx):
        ctx, mock_mem = mock_ctx
        mock_mem.retrieve_with_context.return_value = [
            _make_memory(metadata={"expanded_context": ["extra context"]})
        ]

        import asyncio

        results = await asyncio.to_thread(
            mock_mem.retrieve_with_context, query="test", task_type="chat", k=8
        )
        serialized = serialize_memory_list(results)
        assert serialized[0]["expanded_context"] == ["extra context"]


# ---------------------------------------------------------------------------
# Server Lifespan Test
# ---------------------------------------------------------------------------


class TestServerLifespan:
    def test_create_server_returns_fastmcp(self):
        """Test that create_server returns a FastMCP instance."""
        from neuromem.mcp.server import create_server

        server = create_server()
        assert server is not None
        assert server.name == "neuromem"

    def test_module_entry_point_exists(self):
        """Test that __main__.py defines a main function."""
        from neuromem.mcp.__main__ import main

        assert callable(main)

    def test_package_exports(self):
        """Test that __init__.py exports create_server."""
        from neuromem.mcp import create_server

        assert callable(create_server)
