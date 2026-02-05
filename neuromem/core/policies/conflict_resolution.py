"""
Conflict resolution for contradicting memories.
"""

from neuromem.core.types import MemoryItem
from typing import Tuple


class ConflictResolver:
    """Resolves conflicts between contradicting memories"""
    
    def __init__(self, config: dict = None):
        config = config or {}
        self.recency_weight = config.get('conflict_recency_weight', 0.4)
        self.confidence_weight = config.get('conflict_confidence_weight', 0.3)
        self.reinforcement_weight = config.get('conflict_reinforcement_weight', 0.3)
    
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
        # Simple heuristic: same tags but different content
        if set(mem1.tags) & set(mem2.tags):
            # Check for negation words
            negation_words = ['not', 'no', 'never', 'don\'t', 'doesn\'t']
            mem1_has_negation = any(word in mem1.content.lower() for word in negation_words)
            mem2_has_negation = any(word in mem2.content.lower() for word in negation_words)
            
            if mem1_has_negation != mem2_has_negation:
                return True
        
        return False
    
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
            mem2.metadata['deprecated'] = True
            mem2.metadata['superseded_by'] = mem1.id
            mem2.metadata['deprecation_reason'] = 'conflict_resolution'
            return (mem1, mem2)
        else:
            # mem2 is preferred
            mem1.metadata['deprecated'] = True
            mem1.metadata['superseded_by'] = mem2.id
            mem1.metadata['deprecation_reason'] = 'conflict_resolution'
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
            self.recency_weight * recency_score +
            self.confidence_weight * confidence_score +
            self.reinforcement_weight * reinforcement_score
        )
        
        return score
