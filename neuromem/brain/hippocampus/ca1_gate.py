"""
CA1 — Output Gating (Value-Based Memory Selection).

CA1 acts as the hippocampal output layer, combining CA3's retrieved
patterns with value signals from the basal ganglia (TD learner).
It implements a linear integrator that selects which memories get
forwarded to neocortex based on their learned task-relevance.

The gate applies three adjustments to retrieval scores:
1. TD value boost: memories from high-value clusters get boosted
2. Maturation penalty: recently encoded memories get penalized
3. Working memory priority: items in WM slots get highest priority

Reference: Hasselmo & Eichenbaum (2005), "Hippocampal mechanisms
for the context-dependent retrieval of episodes"
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Tuple

from neuromem.constants import DEFAULT_MATURATION_MINUTES, DEFAULT_MATURATION_PENALTY
from neuromem.core.types import MemoryItem


class CA1Gate:
    """Value-based output gating for hippocampal memory selection.

    Parameters
    ----------
    maturation_minutes:
        Minutes before a memory is considered "matured" (hemodynamic delay).
    maturation_penalty:
        Score reduction applied to unmatured memories.
    """

    def __init__(
        self,
        maturation_minutes: int = DEFAULT_MATURATION_MINUTES,
        maturation_penalty: float = DEFAULT_MATURATION_PENALTY,
    ) -> None:
        self.maturation_minutes = maturation_minutes
        self.maturation_penalty = maturation_penalty

    def gate(
        self,
        ranked_memories: List[Tuple[MemoryItem, float]],
        td_values: Dict[str, float],
        working_memory_ids: List[str],
    ) -> List[Tuple[MemoryItem, float]]:
        """Re-rank memories through value-based gating.

        Parameters
        ----------
        ranked_memories:
            List of (MemoryItem, score) tuples from the basic retrieval engine.
        td_values:
            Task-type → cluster → value mapping from the TD learner.
        working_memory_ids:
            Memory IDs currently in the PFC working memory buffer.

        Returns
        -------
        Re-ranked list of (MemoryItem, adjusted_score) tuples.
        """
        gated = []
        now = datetime.now(timezone.utc)

        for item, base_score in ranked_memories:
            adjusted = base_score

            # 1. TD value boost
            td_cluster = item.metadata.get("td_cluster", "")
            if td_cluster and td_cluster in td_values:
                td_boost = td_values[td_cluster] * 0.15  # Scale TD values to ±0.15
                adjusted += td_boost

            # 2. Maturation penalty (hemodynamic delay analog)
            if not item.metadata.get("maturation_ready", True):
                age_minutes = (now - item.created_at).total_seconds() / 60.0
                if age_minutes < self.maturation_minutes:
                    adjusted -= self.maturation_penalty

            # 3. Working memory priority boost
            if item.id in working_memory_ids:
                adjusted += 0.2  # WM items are immediately accessible

            # 4. Flashbulb memories always score high
            if item.metadata.get("flashbulb", False):
                adjusted = max(adjusted, 0.9)

            gated.append((item, max(0.0, min(1.0, adjusted))))

        # Re-sort by adjusted score
        gated.sort(key=lambda x: x[1], reverse=True)
        return gated
