"""
Brain-inspired retrieval engine for NeuroMem.

This module implements goal-driven memory retrieval with scoring based on:
- Semantic similarity
- Salience (importance)
- Recency
- Reinforcement (how often accessed)
- Confidence
"""

import math
from datetime import datetime
from typing import List, Tuple
from neuromem.core.types import MemoryItem
from neuromem import constants


class RetrievalEngine:
    """
    Retrieval engine that mimics human attention and memory recall.
    
    Unlike pure vector similarity, this engine considers multiple factors
    that influence human memory retrieval:
    - What's relevant (semantic similarity)
    - What's important (salience)
    - What's recent (recency)
    - What's been reinforced (repetition)
    - What we're confident about (confidence)
    """
    
    def __init__(
        self,
        similarity_weight: float = None,
        salience_weight: float = None,
        recency_weight: float = None,
        reinforcement_weight: float = None,
        confidence_weight: float = None
    ):
        """
        Initialize the retrieval engine with scoring weights.

        Args:
            similarity_weight: Weight for semantic similarity (default from constants)
            salience_weight: Weight for memory importance (default from constants)
            recency_weight: Weight for how recent the memory is (default from constants)
            reinforcement_weight: Weight for repetition/access count (default from constants)
            confidence_weight: Weight for confidence level (default from constants)
        """
        self.similarity_weight = similarity_weight or constants.DEFAULT_SIMILARITY_WEIGHT
        self.salience_weight = salience_weight or constants.DEFAULT_SALIENCE_WEIGHT
        self.recency_weight = recency_weight or constants.DEFAULT_RECENCY_WEIGHT
        self.reinforcement_weight = reinforcement_weight or constants.DEFAULT_REINFORCEMENT_WEIGHT
        self.confidence_weight = confidence_weight or constants.DEFAULT_CONFIDENCE_WEIGHT
    
    def score(self, item: MemoryItem, similarity: float) -> float:
        """
        Calculate a brain-inspired relevance score for a memory item.
        
        Args:
            item: The memory item to score
            similarity: Cosine similarity between query and memory (0.0-1.0)
        
        Returns:
            Composite score (0.0-1.0)
        """
        # Calculate recency score (exponential decay)
        age_days = (datetime.utcnow() - item.last_accessed).days + 1
        recency = math.exp(-constants.DEFAULT_RECENCY_DECAY_LAMBDA * age_days)

        # Normalize reinforcement (cap at configured max for scoring)
        reinforcement_normalized = min(
            item.reinforcement / constants.DEFAULT_MAX_REINFORCEMENT_FOR_SCORING,
            1.0
        )
        
        # Composite score
        score = (
            self.similarity_weight * similarity +
            self.salience_weight * item.salience +
            self.recency_weight * recency +
            self.reinforcement_weight * reinforcement_normalized +
            self.confidence_weight * item.confidence
        )
        
        return min(score, 1.0)  # Cap at 1.0
    
    def rank(
        self,
        items: List[MemoryItem],
        similarities: List[float]
    ) -> List[Tuple[MemoryItem, float]]:
        """
        Rank memory items by composite score.
        
        Args:
            items: List of memory items
            similarities: Corresponding similarity scores
        
        Returns:
            List of (item, score) tuples, sorted by score descending
        """
        scored_items = [
            (item, self.score(item, sim))
            for item, sim in zip(items, similarities)
        ]
        
        # Sort by score descending
        scored_items.sort(key=lambda x: x[1], reverse=True)
        
        return scored_items
    
    def apply_inhibition(
        self,
        ranked_items: List[Tuple[MemoryItem, float]],
        diversity_threshold: float = None
    ) -> List[Tuple[MemoryItem, float]]:
        """
        Apply competitive inhibition to prevent near-duplicate memories.

        This mimics lateral inhibition in the brain, where similar neurons
        suppress each other to enhance signal diversity.

        Args:
            ranked_items: List of (item, score) tuples
            diversity_threshold: Similarity threshold for inhibition (default from constants)

        Returns:
            Filtered list with diverse memories
        """
        if not ranked_items:
            return []

        if diversity_threshold is None:
            diversity_threshold = constants.DEFAULT_DIVERSITY_THRESHOLD
        
        selected = [ranked_items[0]]  # Always keep the top result
        
        for item, score in ranked_items[1:]:
            # Check if this item is too similar to already selected items
            is_diverse = True
            for selected_item, _ in selected:
                # Simple content-based diversity check
                # In production, use embedding similarity
                if self._content_similarity(item.content, selected_item.content) > diversity_threshold:
                    is_diverse = False
                    break
            
            if is_diverse:
                selected.append((item, score))
        
        return selected
    
    def _content_similarity(self, content1: str, content2: str) -> float:
        """
        Simple content similarity measure.
        
        In production, this should use embedding similarity.
        """
        # Simple word overlap for now
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def filter_by_confidence(
        self,
        items: List[Tuple[MemoryItem, float]],
        min_confidence: float = None
    ) -> List[Tuple[MemoryItem, float]]:
        """
        Filter out low-confidence memories.

        Args:
            items: List of (item, score) tuples
            min_confidence: Minimum confidence threshold (default from constants)

        Returns:
            Filtered list
        """
        if min_confidence is None:
            min_confidence = constants.DEFAULT_MIN_CONFIDENCE_THRESHOLD

        return [
            (item, score)
            for item, score in items
            if item.confidence >= min_confidence
        ]
