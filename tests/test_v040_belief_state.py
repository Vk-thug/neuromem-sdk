"""
Tests for v0.4.0 H1-R12: BeliefState IntEnum + backward-compat ``inferred``.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from neuromem.core.types import BeliefState, MemoryItem, MemoryType


def _make_item(
    *,
    inferred: bool = False,
    belief_state: BeliefState | None = None,
) -> MemoryItem:
    """Build a minimal MemoryItem for migration tests."""
    kwargs = dict(
        id="m1",
        user_id="u1",
        content="x",
        embedding=[0.0],
        memory_type=MemoryType.EPISODIC,
        salience=0.5,
        confidence=0.9,
        created_at=datetime.now(timezone.utc),
        last_accessed=datetime.now(timezone.utc),
        decay_rate=0.05,
        reinforcement=0,
        inferred=inferred,
        editable=True,
    )
    if belief_state is not None:
        kwargs["belief_state"] = belief_state
    return MemoryItem(**kwargs)


class TestBeliefStateOrdering:
    def test_int_ordering_known_above_believed(self):
        assert BeliefState.KNOWN > BeliefState.BELIEVED
        assert BeliefState.BELIEVED > BeliefState.INFERRED
        assert BeliefState.INFERRED > BeliefState.SPECULATED

    def test_from_legacy_inferred_true_maps_to_inferred(self):
        assert BeliefState.from_legacy_inferred(True) is BeliefState.INFERRED

    def test_from_legacy_inferred_false_maps_to_believed_not_known(self):
        # KNOWN requires cross-session corroboration v0.3.x never tracked.
        assert BeliefState.from_legacy_inferred(False) is BeliefState.BELIEVED


class TestMemoryItemMigration:
    def test_default_belief_state_is_believed(self):
        item = _make_item()
        assert item.belief_state is BeliefState.BELIEVED
        assert item.inferred is False

    def test_legacy_inferred_true_promotes_to_inferred_belief_state(self):
        item = _make_item(inferred=True)
        assert item.belief_state is BeliefState.INFERRED
        assert item.inferred is True  # legacy mirror still True

    def test_belief_state_is_source_of_truth(self):
        item = _make_item(inferred=False, belief_state=BeliefState.SPECULATED)
        # Even though legacy inferred=False, belief_state wins; inferred mirror reflects.
        assert item.belief_state is BeliefState.SPECULATED
        assert item.inferred is False  # SPECULATED is not INFERRED

    def test_explicit_inferred_state(self):
        item = _make_item(belief_state=BeliefState.INFERRED)
        assert item.belief_state is BeliefState.INFERRED
        assert item.inferred is True

    def test_explicit_known_state(self):
        item = _make_item(belief_state=BeliefState.KNOWN)
        assert item.belief_state is BeliefState.KNOWN
        # KNOWN is not INFERRED — legacy mirror stays False.
        assert item.inferred is False


class TestRoundtrip:
    def test_to_dict_includes_belief_state(self):
        item = _make_item(belief_state=BeliefState.KNOWN)
        d = item.to_dict()
        assert d["belief_state"] == int(BeliefState.KNOWN)
        assert d["inferred"] is False

    def test_from_dict_uses_belief_state_when_present(self):
        item = _make_item(belief_state=BeliefState.SPECULATED)
        round_tripped = MemoryItem.from_dict(item.to_dict())
        assert round_tripped.belief_state is BeliefState.SPECULATED

    def test_from_dict_legacy_v03x_row_no_belief_state_field(self):
        """Rows persisted by v0.3.x lack ``belief_state`` — derive from inferred."""
        item = _make_item(inferred=True)
        legacy = item.to_dict()
        legacy.pop("belief_state")  # simulate v0.3.x persisted shape
        round_tripped = MemoryItem.from_dict(legacy)
        assert round_tripped.belief_state is BeliefState.INFERRED
        assert round_tripped.inferred is True

    def test_from_dict_legacy_v03x_inferred_false(self):
        item = _make_item(inferred=False)
        legacy = item.to_dict()
        legacy.pop("belief_state")
        round_tripped = MemoryItem.from_dict(legacy)
        assert round_tripped.belief_state is BeliefState.BELIEVED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
