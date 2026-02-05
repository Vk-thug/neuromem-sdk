"""
Pytest configuration and fixtures for NeuroMem tests.
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, MagicMock
from neuromem import NeuroMem
from neuromem.config import NeuroMemConfig
from neuromem.user import UserManager
from neuromem.storage.memory import InMemoryBackend
from neuromem.core.types import MemoryItem, MemoryType
from datetime import datetime
import uuid


@pytest.fixture
def temp_config_file():
    """Create a temporary config file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
neuromem:
  model:
    embedding: text-embedding-3-large
    consolidation_llm: gpt-4o-mini
  storage:
    database:
      type: memory
  memory:
    decay_enabled: true
    consolidation_interval: 10
    max_active_memories: 50
  async:
    enabled: false  # Disable async for testing
  retrieval:
    hybrid_enabled: false  # Simplify for testing
""")
        config_path = f.name

    yield config_path

    # Cleanup
    if os.path.exists(config_path):
        os.unlink(config_path)


@pytest.fixture
def user_id():
    """Generate a test user ID"""
    return str(uuid.uuid4())


@pytest.fixture
def neuromem_instance(temp_config_file, user_id):
    """Create a NeuroMem instance for testing"""
    memory = NeuroMem.from_config(temp_config_file, user_id=user_id)
    yield memory
    memory.close()


@pytest.fixture
def mock_embedding():
    """Generate a mock embedding vector"""
    import numpy as np
    np.random.seed(42)
    return np.random.randn(1536).tolist()


@pytest.fixture
def sample_memory_item(user_id, mock_embedding):
    """Create a sample memory item"""
    return MemoryItem(
        id=str(uuid.uuid4()),
        user_id=user_id,
        content="Sample memory content",
        embedding=mock_embedding,
        memory_type=MemoryType.EPISODIC,
        salience=0.7,
        confidence=0.9,
        created_at=datetime.utcnow(),
        last_accessed=datetime.utcnow(),
        decay_rate=0.05,
        reinforcement=1,
        inferred=False,
        editable=True,
        tags=['test'],
        metadata={}
    )


@pytest.fixture
def in_memory_backend():
    """Create an in-memory backend for testing"""
    return InMemoryBackend()


@pytest.fixture
def mock_openai_client(monkeypatch):
    """Mock OpenAI API client"""
    mock_client = MagicMock()
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1] * 1536)]
    mock_client.embeddings.create.return_value = mock_response

    def mock_openai_init(*args, **kwargs):
        return mock_client

    # Patch OpenAI client
    monkeypatch.setattr("neuromem.utils.embeddings.OpenAI", mock_openai_init)

    return mock_client
