"""
Salience-based memory strength calculation.
"""

import math
from datetime import datetime, timezone
from neuromem.core.types import MemoryItem
from neuromem.utils.time import ensure_utc


class SalienceCalculator:
    """Calculates multi-factor memory strength"""

    @staticmethod
    def calculate_strength(memory: MemoryItem) -> float:
        """
        Calculate memory strength based on multiple factors.

        Mimics human memory consolidation:
        - Recent memories are stronger
        - Repeated memories are stronger
        - Emotional/important memories are stronger
        - Successfully retrieved memories are stronger

        Returns:
            Strength score (0.0-1.0)
        """
        # Recency score (exponential decay)
        age_days = (datetime.now(timezone.utc) - ensure_utc(memory.created_at)).days
        recency_score = math.exp(-0.1 * age_days)

        # Repetition score (capped at 10 reinforcements)
        repetition_score = min(memory.reinforcement / 10.0, 1.0)

        # Emotional/importance score
        emotional_score = memory.metadata.get("emotional_weight", memory.salience)

        # Retrieval performance score
        retrieval_score = (
            memory.retrieval_stats.performance_score if memory.retrieval_stats else 0.5
        )

        # Weighted combination
        strength = (
            0.3 * recency_score
            + 0.2 * repetition_score
            + 0.2 * emotional_score
            + 0.3 * retrieval_score
        )

        return min(strength, 1.0)

    @staticmethod
    def should_decay(memory: MemoryItem, min_strength: float = 0.1, min_age_days: int = 30) -> bool:
        """
        Determine if memory should be decayed/deleted.

        Args:
            memory: Memory to check
            min_strength: Minimum strength threshold
            min_age_days: Minimum age before deletion

        Returns:
            True if memory should be deleted
        """
        strength = SalienceCalculator.calculate_strength(memory)
        age_days = (datetime.now(timezone.utc) - ensure_utc(memory.created_at)).days

        return strength < min_strength and age_days > min_age_days
