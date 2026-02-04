"""
Hybrid retrieval system for NeuroMem.

Combines multiple retrieval strategies:
1. Keyword/tag filtering (fast)
2. Semantic vector search (accurate)
3. Temporal boosting (recency)
4. Importance weighting (salience)
5. Context assembly (reconstruction)
"""

from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
import math


class HybridRetrieval:
    """
    Multi-stage retrieval system that mimics human memory recall.
    
    Stages:
    1. Fast filtering by keywords/tags
    2. Semantic similarity ranking
    3. Temporal and importance boosting
    4. Final re-ranking and selection
    """
    
    def __init__(
        self,
        recency_weight: float = 0.2,
        importance_weight: float = 0.3,
        similarity_weight: float = 0.5,
        recency_half_life_days: float = 30.0
    ):
        """
        Initialize hybrid retrieval.
        
        Args:
            recency_weight: Weight for recency boost
            importance_weight: Weight for importance/salience
            similarity_weight: Weight for semantic similarity
            recency_half_life_days: Half-life for temporal decay
        """
        self.recency_weight = recency_weight
        self.importance_weight = importance_weight
        self.similarity_weight = similarity_weight
        self.recency_half_life_days = recency_half_life_days
    
    def calculate_recency_score(
        self,
        created_at: datetime,
        last_accessed: datetime,
        half_life_days: float = None
    ) -> float:
        """
        Calculate recency score using exponential decay.
        
        Args:
            created_at: When memory was created
            last_accessed: When memory was last accessed
            half_life_days: Half-life for decay curve
        
        Returns:
            Recency score (0.0-1.0)
        """
        if half_life_days is None:
            half_life_days = self.recency_half_life_days
        now = datetime.now()
        
        # Use last_accessed if available, otherwise created_at
        reference_time = last_accessed if last_accessed else created_at
        
        # Calculate age in days
        age_days = (now - reference_time).total_seconds() / 86400.0
        
        # Exponential decay: score = 0.5^(age / half_life)
        score = math.pow(0.5, age_days / half_life_days)
        
        return min(1.0, max(0.0, score))
    
    def calculate_importance_score(
        self,
        salience: float,
        reinforcement: int,
        confidence: float
    ) -> float:
        """
        Calculate importance score from memory attributes.
        
        Args:
            salience: Base salience score
            reinforcement: Number of reinforcements
            confidence: Confidence level
        
        Returns:
            Importance score (0.0-1.0)
        """
        # Base importance from salience
        base = salience
        
        # Boost from reinforcement (diminishing returns)
        reinforcement_boost = min(0.3, math.log(1 + reinforcement) * 0.1)
        
        # Confidence factor
        confidence_factor = confidence
        
        # Combined score
        importance = (base + reinforcement_boost) * confidence_factor
        
        return min(1.0, max(0.0, importance))
    
    def _get_attr(self, item: Any, key: str, default: Any = None) -> Any:
        """Helper to get attribute from dict or object."""
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    def rank_results(
        self,
        results: List[Any],
        similarities: List[float]
    ) -> List[Tuple[Any, float]]:
        """
        Re-rank results using hybrid scoring.
        
        Args:
            results: List of memory items (objects or dicts)
            similarities: Semantic similarity scores
        
        Returns:
            List of (memory, final_score) tuples, sorted by score
        """
        ranked = []
        
        for i, memory in enumerate(results):
            # Semantic similarity
            sim_score = similarities[i] if i < len(similarities) else 0.5
            
            # Recency score
            recency_score = self.calculate_recency_score(
                self._get_attr(memory, 'created_at', datetime.now()),
                self._get_attr(memory, 'last_accessed', datetime.now())
            )
            
            # Importance score
            importance_score = self.calculate_importance_score(
                self._get_attr(memory, 'salience', 0.5),
                self._get_attr(memory, 'reinforcement', 1),
                self._get_attr(memory, 'confidence', 0.8)
            )
            
            # Weighted combination
            final_score = (
                self.similarity_weight * sim_score +
                self.recency_weight * recency_score +
                self.importance_weight * importance_score
            )
            
            # Store score on object if possible
            if not isinstance(memory, dict):
                try:
                    setattr(memory, 'score', final_score)
                except:
                    pass
            else:
                memory['score'] = final_score
            
            ranked.append((memory, final_score))
        
        # Sort by final score (descending)
        ranked.sort(key=lambda x: x[1], reverse=True)
        
        return ranked
    
    def filter_by_tags(
        self,
        memories: List[Any],
        required_tags: List[str] = None,
        excluded_tags: List[str] = None
    ) -> List[Any]:
        """
        Filter memories by tags.
        """
        if not required_tags and not excluded_tags:
            return memories
        
        filtered = []
        
        for memory in memories:
            memory_tags = set(self._get_attr(memory, 'tags', []))
            
            # Check required tags
            if required_tags:
                if not all(tag in memory_tags for tag in required_tags):
                    continue
            
            # Check excluded tags
            if excluded_tags:
                if any(tag in memory_tags for tag in excluded_tags):
                    continue
            
            filtered.append(memory)
        
        return filtered
    
    def filter_by_timerange(
        self,
        memories: List[Any],
        start_time: datetime = None,
        end_time: datetime = None
    ) -> List[Any]:
        """
        Filter memories by time range.
        """
        if not start_time and not end_time:
            return memories
        
        filtered = []
        
        for memory in memories:
            created_at = self._get_attr(memory, 'created_at')
            if not created_at:
                continue
            
            if start_time and created_at < start_time:
                continue
            
            if end_time and created_at > end_time:
                continue
            
            filtered.append(memory)
        
        return filtered
    
    def retrieve(
        self,
        query_embedding: List[float],
        all_memories: List[Any],
        similarities: List[float],
        k: int = 10,
        filters: Dict[str, Any] = None
    ) -> List[Any]:
        """
        Perform hybrid retrieval with multi-stage filtering and ranking.
        """
        results = all_memories
        
        # Stage 1: Apply filters
        if filters:
            # Tag filtering
            if 'required_tags' in filters or 'excluded_tags' in filters:
                results = self.filter_by_tags(
                    results,
                    filters.get('required_tags'),
                    filters.get('excluded_tags')
                )
            
            # Time range filtering
            if 'start_time' in filters or 'end_time' in filters:
                results = self.filter_by_timerange(
                    results,
                    filters.get('start_time'),
                    filters.get('end_time')
                )
        
        # Stage 2: Hybrid ranking
        # Note: similarities list must match original all_memories indices
        # If we filtered, we need to map similarities correctly or re-compute
        # For now, simplistic assumption: filtering happens AFTER similarity search
        # But here we are filtering candidates that already have similarities computed.
        # This implementation is slightly flawed if we filter out items and lose their similarity mapping.
        
        # Correct approach:
        # Zip inputs -> Filter -> Unzip
        candidates_with_sims = []
        for i, mem in enumerate(all_memories):
            sim = similarities[i] if i < len(similarities) else 0.0
            candidates_with_sims.append((mem, sim))
            
        # Apply filters to zipped list
        filtered_candidates = []
        if filters:
            for mem, sim in candidates_with_sims:
                # Apply tag logic
                memory_tags = set(self._get_attr(mem, 'tags', []))
                if 'required_tags' in filters:
                    if not all(tag in memory_tags for tag in filters['required_tags']):
                        continue
                if 'excluded_tags' in filters:
                    if any(tag in memory_tags for tag in filters['excluded_tags']):
                        continue
                
                # Apply time logic
                created_at = self._get_attr(mem, 'created_at')
                if 'start_time' in filters and created_at and created_at < filters['start_time']:
                    continue
                if 'end_time' in filters and created_at and created_at > filters['end_time']:
                    continue
                    
                filtered_candidates.append((mem, sim))
            
            # Use filtered list
            results = [x[0] for x in filtered_candidates]
            filtered_sims = [x[1] for x in filtered_candidates]
        else:
            results = all_memories
            filtered_sims = similarities
            
        # Stage 2: Hybrid ranking
        ranked = self.rank_results(results, filtered_sims)
        
        # Stage 3: Select top-k
        top_k = [memory for memory, score in ranked[:k]]
        
        return top_k
    
    def explain_ranking(
        self,
        memory: Any,
        similarity: float
    ) -> Dict[str, Any]:
        """
        Explain why a memory was ranked highly.
        """
        recency = self.calculate_recency_score(
            self._get_attr(memory, 'created_at', datetime.now()),
            self._get_attr(memory, 'last_accessed', datetime.now())
        )
        
        importance = self.calculate_importance_score(
            self._get_attr(memory, 'salience', 0.5),
            self._get_attr(memory, 'reinforcement', 1),
            self._get_attr(memory, 'confidence', 0.8)
        )
        
        final_score = (
            self.similarity_weight * similarity +
            self.recency_weight * recency +
            self.importance_weight * importance
        )
        
        return {
            "final_score": final_score,
            "components": {
                "similarity": {
                    "score": similarity,
                    "weight": self.similarity_weight,
                    "contribution": self.similarity_weight * similarity
                },
                "recency": {
                    "score": recency,
                    "weight": self.recency_weight,
                    "contribution": self.recency_weight * recency
                },
                "importance": {
                    "score": importance,
                    "weight": self.importance_weight,
                    "contribution": self.importance_weight * importance
                }
            }
        }
