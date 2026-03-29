"""
Embedding optimization policy with ML versioning.
"""

from datetime import datetime, timezone
from neuromem.core.types import MemoryItem
from neuromem.utils.time import ensure_utc


class EmbeddingOptimizationPolicy:
    """Decides when to re-embed memories"""
    
    def __init__(self, config: dict = None):
        config = config or {}
        self.current_model = config.get('embedding_model', 'text-embedding-3-large')
        self.min_retrieval_count = config.get('min_retrieval_count_for_reembed', 5)
        self.min_salience_for_reembed = config.get('min_salience_for_reembed', 0.8)
        self.performance_threshold = config.get('performance_threshold', 0.5)
        self.max_age_days = config.get('max_embedding_age_days', 180)
    
    def should_reembed(self, memory: MemoryItem) -> bool:
        """
        Decide if memory needs re-embedding.
        
        Only re-embed if:
        1. Model changed AND memory is valuable (frequently retrieved or high salience)
        2. Performance degraded (low retrieval success)
        3. Embedding is very old
        
        Args:
            memory: Memory to check
            
        Returns:
            True if memory should be re-embedded
        """
        if not memory.embedding_metadata:
            # No metadata - should re-embed to add it
            return True
        
        # Model changed?
        model_changed = memory.embedding_metadata.model_name != self.current_model
        
        if model_changed:
            # Only re-embed valuable memories
            if memory.retrieval_stats and memory.retrieval_stats.retrieval_count >= self.min_retrieval_count:
                return True
            if memory.salience >= self.min_salience_for_reembed:
                return True
        
        # Performance degraded?
        if memory.retrieval_stats and memory.retrieval_stats.performance_score < self.performance_threshold:
            return True
        
        # Embedding too old?
        age_days = (datetime.now(timezone.utc) - ensure_utc(memory.embedding_metadata.last_updated)).days
        if age_days > self.max_age_days and memory.salience >= self.min_salience_for_reembed:
            return True
        
        return False
    
    def get_reembedding_priority(self, memory: MemoryItem) -> float:
        """
        Calculate priority for re-embedding (0.0-1.0, higher = more urgent).
        
        Args:
            memory: Memory to prioritize
            
        Returns:
            Priority score
        """
        priority = 0.0
        
        # High salience = higher priority
        priority += 0.4 * memory.salience
        
        # Frequently retrieved = higher priority
        if memory.retrieval_stats:
            retrieval_factor = min(memory.retrieval_stats.retrieval_count / 20.0, 1.0)
            priority += 0.3 * retrieval_factor
        
        # Low performance = higher priority
        if memory.retrieval_stats:
            performance_deficit = 1.0 - memory.retrieval_stats.performance_score
            priority += 0.3 * performance_deficit
        
        return min(priority, 1.0)
