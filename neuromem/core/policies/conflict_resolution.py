"""
Conflict resolution for contradicting memories.
"""

import string as _string
from neuromem.core.types import MemoryItem
from neuromem import constants
from typing import Tuple


class ConflictResolver:
    """Resolves conflicts between contradicting memories"""

    def __init__(self, config: dict = None):
        config = config or {}
        self.recency_weight = config.get("conflict_recency_weight", 0.4)
        self.confidence_weight = config.get("conflict_confidence_weight", 0.3)
        self.reinforcement_weight = config.get("conflict_reinforcement_weight", 0.3)

    def detect_conflict(self, mem1: MemoryItem, mem2: MemoryItem) -> bool:
        """
        Detect if two memories conflict.

        This is a placeholder. In production, use LLM to detect semantic conflicts.

        Args:
            mem1: First memory
            mem2: Second memory

        Returns:
            True if memories conflict
        """
        # Content-based conflict detection: shared significant words + negation asymmetry
        # This avoids dependency on auto-tagger tags which can be inconsistent
        user1 = mem1.content.split("\nAssistant:")[0].replace("User: ", "").lower()
        user2 = mem2.content.split("\nAssistant:")[0].replace("User: ", "").lower()

        stop_words = constants.RETRIEVAL_STOP_WORDS
        words1 = {
            w.strip(_string.punctuation)
            for w in user1.split()
            if w.strip(_string.punctuation) not in stop_words
            and len(w.strip(_string.punctuation)) > 2
        }
        words2 = {
            w.strip(_string.punctuation)
            for w in user2.split()
            if w.strip(_string.punctuation) not in stop_words
            and len(w.strip(_string.punctuation)) > 2
        }

        shared_words = words1 & words2
        # Require high overlap (at least 3 shared words AND >40% of the smaller set)
        # to avoid false positives from topically related but non-conflicting memories
        min_set_size = min(len(words1), len(words2)) if words1 and words2 else 0
        overlap_ratio = len(shared_words) / min_set_size if min_set_size > 0 else 0
        if len(shared_words) < 3 or overlap_ratio < 0.4:
            return False

        negation_words = {
            "not",
            "never",
            "don't",
            "doesn't",
            "isn't",
            "aren't",
            "won't",
            "hate",
            "dislike",
            "switched",
            "no longer",
            "stop",
            "quit",
        }
        neg1 = any(f" {w} " in f" {user1} " for w in negation_words)
        neg2 = any(f" {w} " in f" {user2} " for w in negation_words)

        return neg1 != neg2

    def resolve(self, mem1: MemoryItem, mem2: MemoryItem) -> Tuple[MemoryItem, MemoryItem]:
        """
        Resolve conflict between two memories.

        Prefers:
        - Newer memories
        - Higher confidence
        - More reinforced

        Args:
            mem1: First memory
            mem2: Second memory

        Returns:
            Tuple of (preferred_memory, deprecated_memory)
        """
        score1 = self._calculate_preference_score(mem1, mem2)
        score2 = self._calculate_preference_score(mem2, mem1)

        if score1 > score2:
            # mem1 is preferred
            mem2.metadata["deprecated"] = True
            mem2.metadata["superseded_by"] = mem1.id
            mem2.metadata["deprecation_reason"] = "conflict_resolution"
            return (mem1, mem2)
        else:
            # mem2 is preferred
            mem1.metadata["deprecated"] = True
            mem1.metadata["superseded_by"] = mem2.id
            mem1.metadata["deprecation_reason"] = "conflict_resolution"
            return (mem2, mem1)

    def _calculate_preference_score(self, mem: MemoryItem, other: MemoryItem) -> float:
        """Calculate preference score for a memory"""
        # Recency score
        recency_score = 1.0 if mem.created_at > other.created_at else 0.0

        # Confidence score (normalized)
        confidence_score = mem.confidence

        # Reinforcement score (capped at 10)
        reinforcement_score = min(mem.reinforcement / 10.0, 1.0)

        # Weighted sum
        score = (
            self.recency_weight * recency_score
            + self.confidence_weight * confidence_score
            + self.reinforcement_weight * reinforcement_score
        )

        return score
