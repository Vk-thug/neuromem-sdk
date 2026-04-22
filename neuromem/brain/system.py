"""
BrainSystem — Unified facade for all brain region modules.

The MemoryController calls three hook methods:
- on_observe(): enrich a new memory with brain metadata before storage
- on_retrieve(): re-rank retrieved memories through hippocampal gating
- get_working_memory(): return current PFC buffer contents

All hooks are wrapped in try/except — the brain system is an enhancement
layer that must never break the core observe/retrieve pipeline.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from neuromem.brain.amygdala.emotional_tagger import EmotionalTagger
from neuromem.brain.basal_ganglia.td_learner import TDLearner
from neuromem.brain.hippocampus.ca1_gate import CA1Gate
from neuromem.brain.hippocampus.pattern_completion import PatternCompleter
from neuromem.brain.hippocampus.pattern_separation import PatternSeparator
from neuromem.brain.neocortex.schema_integrator import SchemaIntegrator
from neuromem.brain.prefrontal.working_memory import WorkingMemoryBuffer
from neuromem.brain.state_store import BrainStateStore
from neuromem.brain.types import BrainState
from neuromem.core.types import MemoryItem

logger = logging.getLogger(__name__)


class BrainSystem:
    """Unified brain-faithful processing layer.

    Parameters
    ----------
    user_id:
        The user this brain system is initialized for.
    backend:
        Storage backend for BrainState persistence.
    config:
        Brain configuration dict (from ``NeuroMemConfig.brain()``).
    """

    def __init__(
        self,
        user_id: str,
        backend: Any,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        cfg = config or {}
        hippo_cfg = cfg.get("hippocampus", {})
        pfc_cfg = cfg.get("prefrontal", {})
        amyg_cfg = cfg.get("amygdala", {})
        bg_cfg = cfg.get("basal_ganglia", {})
        neo_cfg = cfg.get("neocortex", {})

        self.user_id = user_id

        # Initialize brain regions
        self.pattern_separator = PatternSeparator(
            expansion_ratio=hippo_cfg.get("pattern_separation_expansion", 4),
            sparsity=hippo_cfg.get("sparsity", 0.05),
            user_id=user_id,
        )
        self.pattern_completer = PatternCompleter(
            iterations=hippo_cfg.get("completion_iterations", 3),
        )
        self.ca1_gate = CA1Gate(
            maturation_minutes=hippo_cfg.get("maturation_minutes", 30),
        )
        self.emotional_tagger = EmotionalTagger(
            flashbulb_threshold=amyg_cfg.get("flashbulb_arousal_threshold", 0.8),
        )
        self.working_memory = WorkingMemoryBuffer(
            capacity=pfc_cfg.get("working_memory_capacity", 4),
        )
        self.td_learner = TDLearner(
            alpha=bg_cfg.get("td_alpha", 0.1),
            gamma=bg_cfg.get("td_gamma", 0.9),
        )
        self.schema_integrator = SchemaIntegrator(
            congruence_threshold=neo_cfg.get("schema_congruence_threshold", 0.75),
            interleave_ratio=neo_cfg.get("interleave_ratio", 0.3),
        )

        # State persistence
        self._state_store = BrainStateStore(backend)
        self._state = self._state_store.load(user_id)

        # Restore working memory from persisted state
        self.working_memory.from_state(self._state.working_memory_slots)

    def on_observe(self, item: MemoryItem) -> MemoryItem:
        """Enrich a new memory with brain region metadata before storage.

        Called by MemoryController after embedding generation, before upsert.
        Returns the enriched item (mutated in place via metadata dict).
        """
        try:
            # 1. Amygdala: emotional tagging
            emotional = self.emotional_tagger.tag(item.content, item.salience)
            item.metadata["arousal"] = emotional["arousal"]
            item.metadata["valence"] = emotional["valence"]
            item.metadata["emotional_weight"] = emotional["emotional_weight"]
            item.metadata["flashbulb"] = emotional["flashbulb"]

            if emotional["adjusted_salience"] is not None:
                item.salience = emotional["adjusted_salience"]
            if emotional["adjusted_decay_rate"] is not None:
                item.decay_rate = emotional["adjusted_decay_rate"]

            # 2. Dentate Gyrus: pattern separation
            sparse_code = self.pattern_separator.separate(item.embedding)
            item.metadata["sparse_code"] = sparse_code.to_dict()

            # 3. Neocortex: schema congruence check
            schema_boost = self.schema_integrator.compute_salience_boost(
                item.embedding, self._state.schema_centroids
            )
            item.metadata["schema_boost"] = schema_boost
            item.salience = min(1.0, item.salience + schema_boost)

            # 4. Basal ganglia: tag with cluster ID for TD learning
            cluster_id = self.td_learner.get_cluster_id(item.embedding)
            item.metadata["td_cluster"] = cluster_id

            # 5. Maturation: mark as not yet ready (hemodynamic delay)
            item.metadata["maturation_ready"] = False

            # 6. Working memory: attempt to gate in
            score = item.salience * item.confidence
            self.working_memory.gate_write(item.id, score)

            # Persist state
            self._state.working_memory_slots = self.working_memory.to_state()
            self._state_store.save(self._state)

        except Exception:
            logger.warning(
                "BrainSystem.on_observe failed for item %s, returning unmodified",
                item.id,
                exc_info=True,
            )

        return item

    def on_retrieve(
        self,
        ranked_memories: List[Tuple[MemoryItem, float]],
        task_type: str,
    ) -> List[Tuple[MemoryItem, float]]:
        """Re-rank retrieved memories through hippocampal gating.

        Called by MemoryController after basic scoring, before conflict detection.
        """
        try:
            # 1. CA3 pattern completion: if query is a partial cue,
            #    find the best attractor match among candidates
            #    (The actual completion is done via the existing similarity
            #    search — CA3 here re-weights based on attractor convergence)

            # 2. CA1 output gating: value-based re-ranking
            td_flat = {}
            for task_vals in self._state.td_values.values():
                td_flat.update(task_vals)
            # Merge current task type's values on top
            if task_type in self._state.td_values:
                td_flat.update(self._state.td_values[task_type])

            ranked_memories = self.ca1_gate.gate(
                ranked_memories,
                td_values=td_flat,
                working_memory_ids=self.working_memory.get_active_ids(),
            )

        except Exception:
            logger.warning(
                "BrainSystem.on_retrieve failed, returning unmodified ranking",
                exc_info=True,
            )

        return ranked_memories

    def reinforce(
        self,
        memory_id: str,
        embedding: List[float],
        task_type: str,
        reward: float,
    ) -> None:
        """Update TD values based on retrieval feedback.

        Called when a user/agent marks a retrieved memory as helpful/unhelpful.
        """
        try:
            self._state.td_values = self.td_learner.update(
                embedding, task_type, reward, self._state.td_values
            )
            self._state_store.save(self._state)
        except Exception:
            logger.warning("BrainSystem.reinforce failed", exc_info=True)

    def get_working_memory_ids(self) -> List[str]:
        """Return IDs of memories currently in working memory."""
        return self.working_memory.get_active_ids()

    def get_state(self) -> BrainState:
        """Return current brain state (for inspection/debugging)."""
        return self._state
