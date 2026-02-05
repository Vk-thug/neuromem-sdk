"""
Reconsolidation policy - memory editing on retrieval.
"""

from datetime import datetime
from neuromem.core.types import MemoryItem
from typing import Optional


class ReconsolidationPolicy:
    """Handles memory reconsolidation (editing on retrieval)"""
    
    def __init__(self, config: dict = None):
        config = config or {}
        self.enabled = config.get('reconsolidation_enabled', True)
        self.min_retrieval_for_reconsolidation = config.get('min_retrieval_for_reconsolidation', 3)
        self.context_similarity_threshold = config.get('context_similarity_threshold', 0.8)
    
    def should_reconsolidate(self, memory: MemoryItem, context: str = None) -> bool:
        """
        Determine if memory should be reconsolidated.
        
        Reconsolidation happens when:
        - Memory has been retrieved multiple times
        - New context provides additional information
        
        Args:
            memory: Memory to check
            context: New retrieval context
            
        Returns:
            True if memory should be reconsolidated
        """
        if not self.enabled:
            return False
        
        if not memory.retrieval_stats:
            return False
        
        # Only reconsolidate after multiple retrievals
        if memory.retrieval_stats.retrieval_count < self.min_retrieval_for_reconsolidation:
            return False
        
        # If context is provided, check if it adds new information
        if context:
            # Simple heuristic: if context is significantly different from memory content
            # In production, use semantic similarity
            if len(context) > len(memory.content) * 1.5:
                return True
        
        return False
    
    def merge_context(self, original_content: str, new_context: str) -> str:
        """
        Merge original memory with new context.
        
        This is a simple implementation. In production, use LLM for intelligent merging.
        
        Args:
            original_content: Original memory content
            new_context: New context to merge
            
        Returns:
            Merged content
        """
        # Simple merge: append if significantly different
        if new_context not in original_content:
            return f"{original_content}\n\nAdditional context: {new_context}"
        return original_content
    
    def update_memory_after_retrieval(self, memory: MemoryItem, similarity: float):
        """
        Update memory metadata after retrieval.
        
        Args:
            memory: Memory that was retrieved
            similarity: Similarity score from retrieval
        """
        if not memory.retrieval_stats:
            from neuromem.core.types import RetrievalStats
            memory.retrieval_stats = RetrievalStats()
        
        # Update retrieval stats
        memory.retrieval_stats.retrieval_count += 1
        memory.retrieval_stats.last_retrieved = datetime.now()
        memory.retrieval_stats.total_similarity += similarity
        memory.retrieval_stats.avg_similarity = (
            memory.retrieval_stats.total_similarity / memory.retrieval_stats.retrieval_count
        )
        
        # Update performance score (exponential moving average)
        alpha = 0.3  # Learning rate
        memory.retrieval_stats.performance_score = (
            alpha * similarity + (1 - alpha) * memory.retrieval_stats.performance_score
        )
        
        # Reinforce memory
        memory.reinforcement += 1
        memory.last_accessed = datetime.now()
