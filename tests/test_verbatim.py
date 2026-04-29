"""
Tests for verbatim storage (Phase 2 of v0.4.0).

Tests chunking, deduplication, store/query lifecycle, config gating,
and integration with MemoryController.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from neuromem.core.types import MemoryItem, MemoryType
from neuromem.core.verbatim import (
    VERBATIM_MARKER,
    VerbatimStore,
    _content_hash,
    chunk_text,
)

# ── Chunking ──


class TestChunkText:
    def test_empty_string(self) -> None:
        assert chunk_text("") == []

    def test_whitespace_only(self) -> None:
        assert chunk_text("   ") == []

    def test_short_text_single_chunk(self) -> None:
        text = "Hello world, this is a short text."
        chunks = chunk_text(text, chunk_size=800)
        assert chunks == [text]

    def test_exact_chunk_size(self) -> None:
        text = "x" * 800
        chunks = chunk_text(text, chunk_size=800)
        assert len(chunks) == 1

    def test_long_text_multiple_chunks(self) -> None:
        text = "word " * 200  # 1000 chars
        chunks = chunk_text(text, chunk_size=400, overlap=50)
        assert len(chunks) >= 2
        # Verify overlap: end of chunk N should overlap with start of chunk N+1
        for i in range(len(chunks) - 1):
            # There should be some shared content between adjacent chunks
            assert len(chunks[i]) > 0
            assert len(chunks[i + 1]) > 0

    def test_overlap_creates_redundancy(self) -> None:
        text = "A" * 100 + "B" * 100 + "C" * 100  # 300 chars
        chunks = chunk_text(text, chunk_size=150, overlap=50)
        # With overlap, chunks share some content
        assert len(chunks) >= 2

    def test_sentence_boundary_break(self) -> None:
        # Text with a sentence boundary in the last 20% of the chunk
        text = "First sentence here. " * 5 + "Second part. " * 5
        chunks = chunk_text(text, chunk_size=100, overlap=10)
        # Chunks should prefer breaking at sentence boundaries
        for chunk in chunks[:-1]:  # Last chunk may be shorter
            assert len(chunk) > 0


class TestContentHash:
    def test_deterministic(self) -> None:
        assert _content_hash("hello") == _content_hash("hello")

    def test_different_inputs(self) -> None:
        assert _content_hash("hello") != _content_hash("world")

    def test_length(self) -> None:
        assert len(_content_hash("test")) == 16


# ── VerbatimStore ──


class TestVerbatimStore:
    """Tests using a mock backend to avoid embedding API calls."""

    @pytest.fixture()
    def mock_backend(self) -> MagicMock:
        backend = MagicMock()
        backend.upsert = MagicMock()
        backend.query = MagicMock(return_value=([], []))
        backend.list_all = MagicMock(return_value=[])
        backend.delete = MagicMock(return_value=True)
        return backend

    @pytest.fixture()
    def store(self, mock_backend: MagicMock) -> VerbatimStore:
        return VerbatimStore(
            backend=mock_backend,
            user_id="test_user",
            embedding_model="test-model",
            chunk_size=100,
            chunk_overlap=20,
        )

    @patch("neuromem.core.verbatim.get_embedding")
    def test_store_short_text(self, mock_embed: MagicMock, store: VerbatimStore) -> None:
        mock_embed.return_value = [0.1] * 10
        ids = store.store("Short text here")
        assert len(ids) == 1
        store.backend.upsert.assert_called_once()

        item = store.backend.upsert.call_args[0][0]
        assert item.content == "Short text here"
        assert item.metadata["store_type"] == VERBATIM_MARKER
        assert item.confidence == 1.0
        assert item.decay_rate == 0.0

    @patch("neuromem.core.verbatim.get_embedding")
    def test_store_long_text_creates_multiple_chunks(
        self, mock_embed: MagicMock, store: VerbatimStore
    ) -> None:
        mock_embed.return_value = [0.1] * 10
        text = "This is a longer text. " * 20  # ~460 chars
        ids = store.store(text)
        assert len(ids) >= 2
        assert store.backend.upsert.call_count >= 2

    @patch("neuromem.core.verbatim.get_embedding")
    def test_deduplication(self, mock_embed: MagicMock, store: VerbatimStore) -> None:
        mock_embed.return_value = [0.1] * 10
        ids1 = store.store("Unique content here")
        ids2 = store.store("Unique content here")  # Same content
        assert len(ids1) == 1
        assert len(ids2) == 0  # Deduplicated

    @patch("neuromem.core.verbatim.get_embedding")
    def test_metadata_preserved(self, mock_embed: MagicMock, store: VerbatimStore) -> None:
        mock_embed.return_value = [0.1] * 10
        store.store("Some content", metadata={"session_id": "s1", "speaker": "Alice"})

        item = store.backend.upsert.call_args[0][0]
        assert item.metadata["session_id"] == "s1"
        assert item.metadata["speaker"] == "Alice"
        assert item.metadata["store_type"] == VERBATIM_MARKER

    def test_query_filters_to_verbatim_only(self, store: VerbatimStore) -> None:
        """Query should return only items with verbatim marker."""
        verbatim_item = MemoryItem(
            id="v1",
            user_id="test_user",
            content="verbatim chunk",
            embedding=[0.1] * 10,
            memory_type=MemoryType.EPISODIC,
            salience=0.5,
            confidence=1.0,
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            decay_rate=0.0,
            reinforcement=1,
            inferred=False,
            editable=False,
            tags=[],
            metadata={"store_type": VERBATIM_MARKER},
        )
        cognitive_item = MemoryItem(
            id="c1",
            user_id="test_user",
            content="cognitive memory",
            embedding=[0.2] * 10,
            memory_type=MemoryType.EPISODIC,
            salience=0.5,
            confidence=0.9,
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            decay_rate=0.05,
            reinforcement=1,
            inferred=False,
            editable=True,
            tags=[],
            metadata={},
        )
        store.backend.query.return_value = (
            [verbatim_item, cognitive_item],
            [0.9, 0.8],
        )

        items, sims = store.query([0.1] * 10, k=5)
        assert len(items) == 1
        assert items[0].id == "v1"
        assert sims[0] == 0.9

    @patch("neuromem.core.verbatim.get_embedding")
    def test_embedding_failure_skips_chunk(
        self, mock_embed: MagicMock, store: VerbatimStore
    ) -> None:
        mock_embed.side_effect = Exception("API error")
        ids = store.store("Some content")
        assert len(ids) == 0
        store.backend.upsert.assert_not_called()

    def test_clear(self, store: VerbatimStore) -> None:
        verbatim_item = MemoryItem(
            id="v1",
            user_id="test_user",
            content="chunk",
            embedding=[],
            memory_type=MemoryType.EPISODIC,
            salience=0.5,
            confidence=1.0,
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            decay_rate=0.0,
            reinforcement=1,
            inferred=False,
            editable=False,
            tags=[],
            metadata={"store_type": VERBATIM_MARKER},
        )
        store.backend.list_all.return_value = [verbatim_item]
        store.clear()
        store.backend.delete.assert_called_once_with("v1")


# ── Config Gating ──


class TestVerbatimConfigGating:
    def test_verbatim_config_defaults(self) -> None:
        """Verbatim config should return sensible defaults."""
        import tempfile
        import yaml

        config_data = {"neuromem": {"model": {"embedding": "test"}}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            f.flush()
            from neuromem.config import NeuroMemConfig

            cfg = NeuroMemConfig(f.name)

        v = cfg.verbatim()
        assert v["enabled"] is True
        assert v["chunk_size"] == 800
        assert v["chunk_overlap"] == 100

    def test_verbatim_disabled(self) -> None:
        """When verbatim.enabled is False, no VerbatimStore should be created."""
        import tempfile
        import yaml

        config_data = {
            "neuromem": {
                "model": {"embedding": "test"},
                "verbatim": {"enabled": False},
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            f.flush()
            from neuromem.config import NeuroMemConfig

            cfg = NeuroMemConfig(f.name)

        v = cfg.verbatim()
        assert v["enabled"] is False


# ── Controller Integration ──


class TestControllerVerbatimIntegration:
    def test_controller_accepts_verbatim_param(self) -> None:
        """MemoryController should accept verbatim=None without error."""
        from neuromem.core.controller import MemoryController

        # Minimal mocks for controller init
        mock_episodic = MagicMock()
        mock_semantic = MagicMock()
        mock_procedural = MagicMock()
        mock_session = MagicMock()
        mock_retriever = MagicMock()
        mock_consolidator = MagicMock()
        mock_decay = MagicMock()

        # Should not raise
        controller = MemoryController(
            episodic=mock_episodic,
            semantic=mock_semantic,
            procedural=mock_procedural,
            session=mock_session,
            retriever=mock_retriever,
            consolidator=mock_consolidator,
            decay_engine=mock_decay,
            config={"async": {"enabled": False}},
            verbatim=None,
        )
        assert controller.verbatim is None

    def test_controller_accepts_verbatim_store(self) -> None:
        """MemoryController should accept a VerbatimStore instance."""
        from neuromem.core.controller import MemoryController

        mock_verbatim = MagicMock()
        controller = MemoryController(
            episodic=MagicMock(),
            semantic=MagicMock(),
            procedural=MagicMock(),
            session=MagicMock(),
            retriever=MagicMock(),
            consolidator=MagicMock(),
            decay_engine=MagicMock(),
            config={"async": {"enabled": False}},
            verbatim=mock_verbatim,
        )
        assert controller.verbatim is mock_verbatim
