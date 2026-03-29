"""
Core functionality tests for NeuroMem SDK.
"""

import pytest
from neuromem import NeuroMem
from neuromem.core.types import MemoryType
from neuromem.utils.validation import ValidationError


class TestNeuroMemInitialization:
    """Test NeuroMem initialization"""

    def test_from_config(self, temp_config_file, user_id):
        """Test creating NeuroMem from config"""
        memory = NeuroMem.from_config(temp_config_file, user_id)
        assert memory is not None
        assert memory.user_id == user_id
        memory.close()

    def test_for_langchain(self, user_id):
        """Test langchain convenience method"""
        # This would need a valid config file in the working directory
        # For now, test that the method exists
        assert hasattr(NeuroMem, "for_langchain")

    def test_for_langgraph(self, user_id):
        """Test langgraph convenience method"""
        assert hasattr(NeuroMem, "for_langgraph")


class TestObserve:
    """Test observation functionality"""

    def test_observe_valid_input(self, neuromem_instance):
        """Test observing valid interaction"""
        neuromem_instance.observe(
            user_input="Hello, how are you?", assistant_output="I'm doing well, thank you!"
        )
        # Should not raise any errors

    def test_observe_invalid_user_input(self, neuromem_instance):
        """Test that invalid user input raises ValidationError"""
        with pytest.raises(ValidationError):
            neuromem_instance.observe(user_input="", assistant_output="Response")  # Empty input

    def test_observe_too_long_input(self, neuromem_instance):
        """Test that oversized input raises ValidationError"""
        with pytest.raises(ValidationError):
            neuromem_instance.observe(
                user_input="x" * 60000, assistant_output="Response"  # Exceeds 50KB limit
            )


class TestRetrieve:
    """Test retrieval functionality"""

    def test_retrieve_empty_memory(self, neuromem_instance):
        """Test retrieving from empty memory"""
        results = neuromem_instance.retrieve("test query", k=5)
        assert results == []

    def test_retrieve_with_memories(self, neuromem_instance, mock_openai_client):
        """Test retrieving with some memories"""
        # Add some memories
        neuromem_instance.observe("I like pizza", "Great choice!")
        neuromem_instance.observe("I prefer tea over coffee", "Noted!")

        # Retrieve
        results = neuromem_instance.retrieve("food preferences", k=5)
        assert isinstance(results, list)

    def test_retrieve_respects_k_parameter(self, neuromem_instance):
        """Test that k parameter limits results"""
        # Add many memories
        for i in range(20):
            neuromem_instance.observe(f"Memory {i}", f"Response {i}")

        results = neuromem_instance.retrieve("test", k=5)
        assert len(results) <= 5


class TestMemoryManagement:
    """Test memory CRUD operations"""

    def test_list_memories(self, neuromem_instance):
        """Test listing all memories"""
        neuromem_instance.observe("Test input", "Test output")
        memories = neuromem_instance.list(limit=10)
        assert isinstance(memories, list)
        assert len(memories) >= 1

    def test_list_memories_by_type(self, neuromem_instance):
        """Test filtering memories by type"""
        neuromem_instance.observe("Test input", "Test output")
        episodic = neuromem_instance.list(memory_type="episodic", limit=10)
        assert all(m.memory_type == MemoryType.EPISODIC for m in episodic)


class TestParallelRetrieval:
    """Test parallel retrieval functionality"""

    def test_parallel_retrieval_enabled(self, neuromem_instance):
        """Test that parallel retrieval works"""
        # Add memories
        for i in range(5):
            neuromem_instance.observe(f"Input {i}", f"Output {i}")

        # Retrieve with parallel=True (default)
        results = neuromem_instance.retrieve("test", k=3, parallel=True)
        assert isinstance(results, list)

    def test_sequential_retrieval(self, neuromem_instance):
        """Test that sequential retrieval still works"""
        # Add memories
        for i in range(5):
            neuromem_instance.observe(f"Input {i}", f"Output {i}")

        # Retrieve with parallel=False
        results = neuromem_instance.retrieve("test", k=3, parallel=False)
        assert isinstance(results, list)


class TestHealthChecks:
    """Test health check functionality"""

    def test_health_status(self, neuromem_instance):
        """Test getting health status"""
        from neuromem.health import get_health_status

        health = get_health_status(neuromem_instance)
        assert "status" in health
        assert "checks" in health
        assert health["status"] in ["healthy", "degraded", "unhealthy"]

    def test_readiness_status(self, neuromem_instance):
        """Test getting readiness status"""
        from neuromem.health import get_readiness_status

        readiness = get_readiness_status(neuromem_instance)
        assert "ready" in readiness
        assert isinstance(readiness["ready"], bool)

    def test_liveness_status(self, neuromem_instance):
        """Test getting liveness status"""
        from neuromem.health import get_liveness_status

        liveness = get_liveness_status(neuromem_instance)
        assert "alive" in liveness
        assert liveness["alive"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
