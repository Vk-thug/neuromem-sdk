"""
Prefrontal Cortex — Working Memory Buffer.

Implements Cowan's 4-slot capacity limit with attention-gated write.
The basal ganglia disinhibitory motif controls when new items enter:
a new item displaces the lowest-scoring current occupant only if
its score exceeds the minimum.

Displaced items are NOT deleted — they remain in episodic storage —
but they exit the immediate attention window.

Reference: Cowan (2001), "The magical number 4 in short-term memory"
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from neuromem.constants import DEFAULT_WORKING_MEMORY_CAPACITY

logger = logging.getLogger(__name__)


class WorkingMemoryBuffer:
    """4-slot working memory buffer with attention gating.

    Parameters
    ----------
    capacity:
        Maximum number of simultaneously active items (default 4).
    """

    CAPACITY: int = DEFAULT_WORKING_MEMORY_CAPACITY

    def __init__(self, capacity: int = DEFAULT_WORKING_MEMORY_CAPACITY) -> None:
        self.CAPACITY = capacity
        self._slots: List[Tuple[str, float]] = []  # (memory_id, score)

    def gate_write(self, memory_id: str, score: float) -> Optional[str]:
        """Attempt to write a memory into working memory.

        The new item enters if there is a free slot or if its score
        exceeds the lowest-scoring current occupant.

        Parameters
        ----------
        memory_id:
            ID of the memory to add.
        score:
            Retrieval/importance score of the memory.

        Returns
        -------
        The ID of the displaced memory, or None if a free slot was used.
        """
        # Already in WM — just update score
        for i, (mid, _) in enumerate(self._slots):
            if mid == memory_id:
                self._slots[i] = (memory_id, score)
                return None

        # Free slot available
        if len(self._slots) < self.CAPACITY:
            self._slots.append((memory_id, score))
            return None

        # Find minimum occupant
        min_idx = min(range(len(self._slots)), key=lambda i: self._slots[i][1])
        min_id, min_score = self._slots[min_idx]

        if score > min_score:
            self._slots[min_idx] = (memory_id, score)
            logger.debug(
                "WM: displaced %s (%.3f) for %s (%.3f)",
                min_id,
                min_score,
                memory_id,
                score,
            )
            return min_id

        # New item not strong enough to enter
        return None

    def get_active_ids(self) -> List[str]:
        """Return IDs of memories currently in working memory."""
        return [mid for mid, _ in self._slots]

    def get_active_with_scores(self) -> List[Tuple[str, float]]:
        """Return (memory_id, score) tuples sorted by score descending."""
        return sorted(self._slots, key=lambda x: x[1], reverse=True)

    def remove(self, memory_id: str) -> bool:
        """Explicitly remove a memory from working memory."""
        for i, (mid, _) in enumerate(self._slots):
            if mid == memory_id:
                self._slots.pop(i)
                return True
        return False

    def clear(self) -> None:
        """Clear all working memory slots."""
        self._slots.clear()

    def to_state(self) -> List[str]:
        """Serialize to list of IDs for BrainState persistence."""
        return self.get_active_ids()

    def from_state(self, memory_ids: List[str], default_score: float = 0.5) -> None:
        """Restore from persisted BrainState."""
        self._slots = [(mid, default_score) for mid in memory_ids[: self.CAPACITY]]
