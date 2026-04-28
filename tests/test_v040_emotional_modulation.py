"""
Tests for v0.4.0 H1-R10: emotional modulation in apply_hybrid_boosts.

Verifies the multiplicative emotional weight + flashbulb boost are applied
post-CE-blend (Phelps 2004 — amygdala modulation, not gating).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from neuromem.core.hybrid_boosts import apply_hybrid_boosts


@dataclass
class _FakeItem:
    """Stand-in for MemoryItem with just the fields hybrid_boosts inspects."""

    content: str
    metadata: dict = field(default_factory=dict)


class TestEmotionalModulationDisabled:
    def test_factor_zero_preserves_v03x_behaviour(self):
        items = [
            (_FakeItem("a", {"emotional_weight": 0.9, "flashbulb": True}), 0.5),
            (_FakeItem("b", {"emotional_weight": 0.0}), 0.5),
        ]
        out = apply_hybrid_boosts(
            items, query_text="", emotional_weight_factor=0.0, flashbulb_boost=0.0
        )
        # No query_text means no other boosts either; pass-through preserved.
        scores = {item.content: score for item, score in out}
        assert scores["a"] == pytest.approx(0.5)
        assert scores["b"] == pytest.approx(0.5)


class TestEmotionalModulationActive:
    def test_emotional_weight_lifts_score_multiplicatively(self):
        items = [
            (_FakeItem("hot", {"emotional_weight": 1.0}), 0.5),
            (_FakeItem("cold", {"emotional_weight": 0.0}), 0.5),
        ]
        out = apply_hybrid_boosts(
            items,
            query_text="anything",  # need non-empty so the loop runs
            emotional_weight_factor=0.2,
            flashbulb_boost=0.0,
            keyword_weight=0.0,
            quoted_phrase_boost=0.0,
            person_name_boost=0.0,
            temporal_boost_max=0.0,
        )
        scores = {item.content: score for item, score in out}
        # hot: 0.5 * (1 + 0.2 * 1.0) = 0.6
        # cold: 0.5 * 1.0 = 0.5
        assert scores["hot"] == pytest.approx(0.6, abs=1e-6)
        assert scores["cold"] == pytest.approx(0.5, abs=1e-6)
        # Re-sort: hot must rank above cold.
        assert out[0][0].content == "hot"

    def test_flashbulb_metadata_adds_extra_bump(self):
        items = [
            (_FakeItem("flash", {"emotional_weight": 0.5, "flashbulb": True}), 0.5),
            (_FakeItem("plain", {"emotional_weight": 0.5}), 0.5),
        ]
        out = apply_hybrid_boosts(
            items,
            query_text="anything",
            emotional_weight_factor=0.1,
            flashbulb_boost=0.2,
            keyword_weight=0.0,
            quoted_phrase_boost=0.0,
            person_name_boost=0.0,
            temporal_boost_max=0.0,
        )
        scores = {item.content: score for item, score in out}
        # flash: 0.5 * (1 + 0.1*0.5) * (1 + 0.2) = 0.5 * 1.05 * 1.2 = 0.63
        # plain: 0.5 * (1 + 0.1*0.5) = 0.525
        assert scores["flash"] == pytest.approx(0.63, abs=1e-6)
        assert scores["plain"] == pytest.approx(0.525, abs=1e-6)

    def test_score_capped_at_one(self):
        items = [(_FakeItem("hot", {"emotional_weight": 5.0, "flashbulb": True}), 0.95)]
        out = apply_hybrid_boosts(
            items,
            query_text="anything",
            emotional_weight_factor=1.0,
            flashbulb_boost=1.0,
            keyword_weight=0.0,
            quoted_phrase_boost=0.0,
            person_name_boost=0.0,
            temporal_boost_max=0.0,
        )
        # Even at high multipliers, score must be <= 1.0.
        assert out[0][1] <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
