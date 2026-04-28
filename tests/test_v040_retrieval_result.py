"""
Tests for v0.4.0 D3: RetrievalResult wrapper with backward-compat iteration.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from neuromem.core.types import MemoryItem, MemoryType, RetrievalResult


def _item(content: str) -> MemoryItem:
    return MemoryItem(
        id=f"id-{content}",
        user_id="u1",
        content=content,
        embedding=[0.0],
        memory_type=MemoryType.EPISODIC,
        salience=0.5,
        confidence=0.9,
        created_at=datetime.now(timezone.utc),
        last_accessed=datetime.now(timezone.utc),
        decay_rate=0.05,
        reinforcement=0,
        inferred=False,
        editable=True,
    )


class TestRetrievalResult:
    def test_iteration_yields_items(self):
        result = RetrievalResult(items=[_item("a"), _item("b")])
        out = [m.content for m in result]
        assert out == ["a", "b"]

    def test_list_constructor_compat(self):
        result = RetrievalResult(items=[_item("a"), _item("b")])
        assert [m.content for m in list(result)] == ["a", "b"]

    def test_len(self):
        result = RetrievalResult(items=[_item("a"), _item("b"), _item("c")])
        assert len(result) == 3

    def test_indexing(self):
        result = RetrievalResult(items=[_item("a"), _item("b")])
        assert result[0].content == "a"
        assert result[-1].content == "b"

    def test_truthy_when_nonempty(self):
        full = RetrievalResult(items=[_item("a")])
        empty = RetrievalResult(items=[])
        assert bool(full) is True
        assert bool(empty) is False

    def test_default_confidence_and_abstained(self):
        # Until v0.5.0 H2-D7 wires real values, defaults preserve v0.3.x semantics.
        result = RetrievalResult(items=[_item("a")])
        assert result.confidence == 1.0
        assert result.abstained is False
        assert result.abstention_reason is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
