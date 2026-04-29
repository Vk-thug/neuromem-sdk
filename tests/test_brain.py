"""
Tests for the brain-faithful memory system (v0.3.0).

Tests all 6 brain regions + BrainSystem facade + state persistence.
"""

import pytest
import numpy as np
from datetime import datetime, timezone, timedelta

from neuromem.brain.types import SparseCode, BrainState
from neuromem.brain.hippocampus.pattern_separation import PatternSeparator
from neuromem.brain.hippocampus.pattern_completion import PatternCompleter
from neuromem.brain.hippocampus.ca1_gate import CA1Gate
from neuromem.brain.amygdala.emotional_tagger import EmotionalTagger
from neuromem.brain.prefrontal.working_memory import WorkingMemoryBuffer
from neuromem.brain.basal_ganglia.td_learner import TDLearner
from neuromem.brain.neocortex.schema_integrator import SchemaIntegrator
from neuromem.brain.state_store import BrainStateStore
from neuromem.brain.system import BrainSystem
from neuromem.core.types import MemoryItem, MemoryType
from neuromem.core.decay import DecayEngine
from neuromem.storage.memory import InMemoryBackend


def _make_item(
    content: str = "test",
    embedding: list = None,
    salience: float = 0.5,
    memory_id: str = "m1",
    metadata: dict = None,
    created_at: datetime = None,
) -> MemoryItem:
    if embedding is None:
        embedding = np.random.randn(32).tolist()
    return MemoryItem(
        id=memory_id,
        user_id="test-user",
        content=content,
        embedding=embedding,
        memory_type=MemoryType.EPISODIC,
        salience=salience,
        confidence=0.9,
        created_at=created_at or datetime.now(timezone.utc),
        last_accessed=datetime.now(timezone.utc),
        decay_rate=0.05,
        reinforcement=0,
        inferred=False,
        editable=True,
        metadata=metadata or {},
    )


# ── SparseCode Type ──


class TestSparseCode:
    def test_roundtrip_serialization(self):
        sc = SparseCode(
            dense_vector=[0.1, 0.2],
            sparse_indices=[0, 5, 10],
            sparse_values=[0.9, 0.7, 0.3],
            sparsity=0.95,
            expansion_dim=200,
        )
        d = sc.to_dict()
        assert "sparse_indices" in d
        assert d["expansion_dim"] == 200

        sc2 = SparseCode.from_dict(d, dense_vector=[0.1, 0.2])
        assert sc2.sparse_indices == sc.sparse_indices
        assert sc2.sparsity == sc.sparsity

    def test_frozen(self):
        sc = SparseCode([0.1], [0], [1.0], 0.9, 10)
        with pytest.raises(AttributeError):
            sc.sparsity = 0.5


# ── BrainState Type ──


class TestBrainState:
    def test_roundtrip(self):
        bs = BrainState(
            user_id="u1",
            working_memory_slots=["m1", "m2"],
            last_ripple=datetime.now(timezone.utc),
        )
        d = bs.to_dict()
        bs2 = BrainState.from_dict(d)
        assert bs2.user_id == "u1"
        assert bs2.working_memory_slots == ["m1", "m2"]
        assert bs2.last_ripple is not None

    def test_default_values(self):
        bs = BrainState(user_id="u2")
        assert bs.working_memory_slots == []
        assert bs.td_values == {}
        assert bs.last_ripple is None


# ── Pattern Separation (Dentate Gyrus) ──


class TestPatternSeparator:
    def test_output_dimensions(self):
        ps = PatternSeparator(input_dim=32, expansion_ratio=4, sparsity=0.05)
        emb = np.random.randn(32).tolist()
        sc = ps.separate(emb)
        assert sc.expansion_dim == 128
        assert len(sc.sparse_indices) <= int(128 * 0.05) + 1

    def test_sparsity(self):
        ps = PatternSeparator(input_dim=64, expansion_ratio=4, sparsity=0.05)
        sc = ps.separate(np.random.randn(64).tolist())
        assert sc.sparsity > 0.9

    def test_similar_inputs_decorrelated(self):
        ps = PatternSeparator(input_dim=64, expansion_ratio=4, sparsity=0.1, user_id="test")
        base = np.random.randn(64)
        sc1 = ps.separate(base.tolist())
        sc2 = ps.separate((base + np.random.randn(64) * 0.01).tolist())
        # Pattern separation should reduce overlap vs identical
        overlap = len(set(sc1.sparse_indices) & set(sc2.sparse_indices))
        total = max(len(sc1.sparse_indices), 1)
        # Overlap should be less than 100% (decorrelation)
        assert overlap / total <= 1.0

    def test_user_isolation(self):
        ps1 = PatternSeparator(input_dim=32, user_id="user_a")
        ps2 = PatternSeparator(input_dim=32, user_id="user_b")
        emb = np.random.randn(32).tolist()
        sc1 = ps1.separate(emb)
        sc2 = ps2.separate(emb)
        # Different users should get different sparse codes
        assert sc1.sparse_indices != sc2.sparse_indices

    def test_auto_adapt_dimension(self):
        ps = PatternSeparator(input_dim=32)
        emb_16 = np.random.randn(16).tolist()
        sc = ps.separate(emb_16)
        assert sc.expansion_dim == 16 * ps.expansion_ratio


# ── Pattern Completion (CA3) ──


class TestPatternCompleter:
    def test_finds_most_similar(self):
        pc = PatternCompleter(iterations=3, temperature=0.1)
        query = np.random.randn(32).tolist()
        candidates = [np.random.randn(32).tolist() for _ in range(5)]
        candidates[2] = [x + np.random.randn() * 0.01 for x in query]
        result = pc.complete(query, candidates, ["a", "b", "c", "d", "e"])
        assert result is not None
        assert result[0] == "c"
        assert result[1] > 0.9

    def test_empty_candidates(self):
        pc = PatternCompleter()
        assert pc.complete([0.1, 0.2], [], []) is None

    def test_zero_query(self):
        pc = PatternCompleter()
        assert pc.complete([0.0, 0.0], [[1.0, 0.0]], ["a"]) is None


# ── CA1 Gate ──


class TestCA1Gate:
    def test_maturation_penalty(self):
        gate = CA1Gate(maturation_minutes=30, maturation_penalty=0.3)
        item = _make_item(metadata={"maturation_ready": False})
        ranked = [(item, 0.8)]
        result = gate.gate(ranked, {}, [])
        # Score should be reduced by maturation penalty
        assert result[0][1] < 0.8

    def test_flashbulb_boost(self):
        gate = CA1Gate()
        item = _make_item(metadata={"flashbulb": True})
        ranked = [(item, 0.5)]
        result = gate.gate(ranked, {}, [])
        assert result[0][1] >= 0.9

    def test_working_memory_boost(self):
        gate = CA1Gate()
        item = _make_item()
        ranked = [(item, 0.5)]
        result = gate.gate(ranked, {}, ["m1"])
        assert result[0][1] > 0.5


# ── Emotional Tagger (Amygdala) ──


class TestEmotionalTagger:
    def test_high_arousal_detected(self):
        et = EmotionalTagger(flashbulb_threshold=0.8)
        result = et.tag("EMERGENCY! Server CRASHED! This is a disaster and danger!")
        assert result["arousal"] > 0.1  # Multiple arousal signals
        assert "arousal" in result

    def test_positive_valence(self):
        et = EmotionalTagger()
        result = et.tag("I love this amazing beautiful day")
        assert result["valence"] > 0

    def test_neutral_content(self):
        et = EmotionalTagger()
        result = et.tag("The weather is moderate today")
        assert result["arousal"] < 0.3
        assert result["flashbulb"] is False

    def test_flashbulb_encoding(self):
        et = EmotionalTagger(flashbulb_threshold=0.3)
        result = et.tag("EMERGENCY! CRASH! EXPLOSION! DANGER!")
        assert result["flashbulb"] is True
        assert result["adjusted_salience"] == 1.0
        assert result["adjusted_decay_rate"] == 0.001


# ── Working Memory Buffer (PFC) ──


class TestWorkingMemoryBuffer:
    def test_capacity_limit(self):
        wm = WorkingMemoryBuffer(capacity=4)
        for i in range(6):
            wm.gate_write(f"m{i}", float(i) / 10)
        assert len(wm.get_active_ids()) == 4

    def test_displacement(self):
        wm = WorkingMemoryBuffer(capacity=3)
        wm.gate_write("a", 0.5)
        wm.gate_write("b", 0.3)
        wm.gate_write("c", 0.7)
        displaced = wm.gate_write("d", 0.6)
        assert displaced == "b"  # lowest score
        assert "b" not in wm.get_active_ids()
        assert "d" in wm.get_active_ids()

    def test_no_displacement_if_weak(self):
        wm = WorkingMemoryBuffer(capacity=2)
        wm.gate_write("a", 0.5)
        wm.gate_write("b", 0.6)
        displaced = wm.gate_write("c", 0.3)  # Too weak
        assert displaced is None
        assert "c" not in wm.get_active_ids()

    def test_update_score(self):
        wm = WorkingMemoryBuffer(capacity=4)
        wm.gate_write("a", 0.5)
        wm.gate_write("a", 0.9)  # Update score
        assert len(wm.get_active_ids()) == 1

    def test_remove(self):
        wm = WorkingMemoryBuffer(capacity=4)
        wm.gate_write("a", 0.5)
        assert wm.remove("a") is True
        assert wm.remove("nonexistent") is False

    def test_state_roundtrip(self):
        wm = WorkingMemoryBuffer(capacity=4)
        wm.gate_write("a", 0.5)
        wm.gate_write("b", 0.6)
        state = wm.to_state()
        wm2 = WorkingMemoryBuffer(capacity=4)
        wm2.from_state(state)
        assert set(wm2.get_active_ids()) == {"a", "b"}


# ── TD Learner (Basal Ganglia) ──


class TestTDLearner:
    def test_positive_reward(self):
        td = TDLearner(alpha=0.1)
        emb = np.random.randn(32).tolist()
        values = {}
        values = td.update(emb, "chat", 1.0, values)
        v = td.get_value(emb, "chat", values)
        assert v > 0

    def test_negative_reward(self):
        td = TDLearner(alpha=0.1)
        emb = np.random.randn(32).tolist()
        values = {}
        values = td.update(emb, "chat", -1.0, values)
        v = td.get_value(emb, "chat", values)
        assert v < 0

    def test_value_clamping(self):
        td = TDLearner(alpha=1.0)  # aggressive learning rate
        emb = [1.0] * 32
        values = {}
        for _ in range(100):
            values = td.update(emb, "chat", 1.0, values)
        v = td.get_value(emb, "chat", values)
        assert v <= 1.0

    def test_different_tasks_independent(self):
        td = TDLearner()
        emb = [1.0] * 32
        values = {}
        values = td.update(emb, "chat", 1.0, values)
        values = td.update(emb, "code", -1.0, values)
        assert td.get_value(emb, "chat", values) > 0
        assert td.get_value(emb, "code", values) < 0


# ── Schema Integrator (Neocortex) ──


class TestSchemaIntegrator:
    def test_congruence_with_matching_schema(self):
        si = SchemaIntegrator(congruence_threshold=0.75)
        emb = np.random.randn(32)
        emb = (emb / np.linalg.norm(emb)).tolist()
        centroids = {"python": emb}
        score, key = si.compute_congruence(emb, centroids)
        assert score > 0.99
        assert key == "python"

    def test_no_congruence_empty(self):
        si = SchemaIntegrator()
        score, key = si.compute_congruence([0.1, 0.2], {})
        assert score == 0.0
        assert key == ""

    def test_salience_boost_congruent(self):
        si = SchemaIntegrator(congruence_threshold=0.5)
        emb = np.random.randn(32)
        emb = (emb / np.linalg.norm(emb)).tolist()
        centroids = {"topic": emb}
        boost = si.compute_salience_boost(emb, centroids)
        assert boost > 0

    def test_centroid_update(self):
        si = SchemaIntegrator()
        emb1 = np.random.randn(32).tolist()
        emb2 = np.random.randn(32).tolist()
        centroids = {}
        centroids = si.update_centroids("topic", emb1, centroids)
        assert "topic" in centroids
        centroids = si.update_centroids("topic", emb2, centroids, momentum=0.5)
        # Centroid should have moved towards emb2
        assert centroids["topic"] != emb1

    def test_interleave_count(self):
        si = SchemaIntegrator(interleave_ratio=0.3)
        count = si.select_interleave_memories(["s1", "s2", "s3", "s4", "s5"], 10)
        assert count == 3  # 30% of 10


# ── BrainStateStore ──


class TestBrainStateStore:
    def test_save_and_load(self):
        backend = InMemoryBackend()
        store = BrainStateStore(backend)
        state = BrainState(user_id="u1", working_memory_slots=["m1", "m2"])
        store.save(state)
        loaded = store.load("u1")
        assert loaded.user_id == "u1"
        assert loaded.working_memory_slots == ["m1", "m2"]

    def test_load_default_if_missing(self):
        backend = InMemoryBackend()
        store = BrainStateStore(backend)
        loaded = store.load("nonexistent")
        assert loaded.user_id == "nonexistent"
        assert loaded.working_memory_slots == []


# ── BrainSystem Facade ──


class TestBrainSystem:
    def test_on_observe_enriches_metadata(self):
        backend = InMemoryBackend()
        brain = BrainSystem(user_id="u1", backend=backend)
        item = _make_item(content="I got promoted! Amazing news!")
        enriched = brain.on_observe(item)
        assert "arousal" in enriched.metadata
        assert "sparse_code" in enriched.metadata
        assert "td_cluster" in enriched.metadata
        assert enriched.metadata["maturation_ready"] is False

    def test_on_observe_populates_working_memory(self):
        backend = InMemoryBackend()
        brain = BrainSystem(user_id="u1", backend=backend)
        for i in range(5):
            item = _make_item(memory_id=f"m{i}", salience=0.5 + i * 0.1)
            brain.on_observe(item)
        wm = brain.get_working_memory_ids()
        assert len(wm) <= 4  # Cowan's number

    def test_on_retrieve_returns_reranked(self):
        backend = InMemoryBackend()
        brain = BrainSystem(user_id="u1", backend=backend)
        items = [
            (
                _make_item(memory_id=f"m{i}", metadata={"maturation_ready": True}),
                0.5 + i * 0.1,
            )
            for i in range(3)
        ]
        result = brain.on_retrieve(items, task_type="chat")
        assert len(result) == 3
        # Should be sorted by score descending
        scores = [s for _, s in result]
        assert scores == sorted(scores, reverse=True)

    def test_reinforce_updates_td_values(self):
        backend = InMemoryBackend()
        brain = BrainSystem(user_id="u1", backend=backend)
        emb = np.random.randn(32).tolist()
        brain.reinforce("m1", emb, "chat", reward=1.0)
        state = brain.get_state()
        assert len(state.td_values) > 0


# ── Decay Engine Flashbulb Bypass ──


class TestFlashbulbDecayBypass:
    def test_flashbulb_never_decays(self):
        de = DecayEngine(enabled=True)
        item = _make_item(metadata={"flashbulb": True})
        # Even with old timestamp
        item.last_accessed = datetime.now(timezone.utc) - timedelta(days=365)
        assert de.calculate_decay(item) == 1.0
        assert de.should_forget(item) is False

    def test_normal_memory_still_decays(self):
        de = DecayEngine(enabled=True)
        item = _make_item(metadata={})
        item.last_accessed = datetime.now(timezone.utc) - timedelta(days=365)
        assert de.calculate_decay(item) < 1.0
