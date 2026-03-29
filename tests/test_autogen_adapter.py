"""Tests for AutoGen (AG2) adapter."""

import pytest
from unittest.mock import MagicMock, patch
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
    return nm


autogen = pytest.importorskip("autogen")


class TestRegisterTools:
    def test_register_tools(self, mock_neuromem):
        from neuromem.adapters.autogen import register_neuromem_tools

        caller = MagicMock()
        executor = MagicMock()

        with patch("neuromem.adapters.autogen.register_function") as mock_reg:
            register_neuromem_tools(mock_neuromem, caller, executor, k=5)
            assert mock_reg.call_count == 4

            # Verify tool names
            registered_names = [c.kwargs["name"] for c in mock_reg.call_args_list]
            assert "search_memory" in registered_names
            assert "store_memory" in registered_names
            assert "list_memories" in registered_names
            assert "consolidate_memories" in registered_names


class TestNeuroMemCapability:
    def test_capability_enriches_message(self, mock_neuromem):
        from neuromem.adapters.autogen import NeuroMemCapability

        capability = NeuroMemCapability(mock_neuromem, k=5)
        result = capability._enrich_with_memory("What languages do I prefer?")
        assert "Relevant context from memory" in result
        assert "User prefers Python type annotations" in result
        assert "What languages do I prefer?" in result

    def test_capability_handles_retrieval_failure(self, mock_neuromem):
        from neuromem.adapters.autogen import NeuroMemCapability

        mock_neuromem.retrieve.side_effect = RuntimeError("connection lost")
        capability = NeuroMemCapability(mock_neuromem, k=5)
        result = capability._enrich_with_memory("test message")
        assert result == "test message"

    def test_capability_no_results(self, mock_neuromem):
        from neuromem.adapters.autogen import NeuroMemCapability

        mock_neuromem.retrieve.return_value = []
        capability = NeuroMemCapability(mock_neuromem, k=5)
        result = capability._enrich_with_memory("test message")
        assert result == "test message"

    def test_add_to_agent(self, mock_neuromem):
        from neuromem.adapters.autogen import NeuroMemCapability

        capability = NeuroMemCapability(mock_neuromem, k=5)
        agent = MagicMock()
        capability.add_to_agent(agent)
        agent.register_hook.assert_called_once_with(
            hookable_method="process_last_received_message",
            hook=capability._enrich_with_memory,
        )
