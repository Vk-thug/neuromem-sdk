"""
Memory consolidation engine for NeuroMem.

Handles the promotion of episodic memories to semantic/procedural memory,
mimicking the hippocampus-to-neocortex consolidation process in the brain.
"""

import uuid
from datetime import datetime
from typing import List, Dict
from collections import defaultdict
from neuromem.core.types import MemoryItem, MemoryType, ConsolidationResult


class Consolidator:
    """
    Consolidates episodic memories into semantic and procedural memories.
    
    This mimics the brain's process of:
    1. Identifying repeated patterns in episodic memory
    2. Extracting stable facts (semantic)
    3. Learning behavioral patterns (procedural)
    4. Discarding or decaying unreinforced memories
    """
    
    def __init__(self, llm_model: str = "gpt-4o-mini"):
        """
        Initialize the consolidator.
        
        Args:
            llm_model: LLM model to use for consolidation (optional)
        """
        self.llm_model = llm_model
        self.min_reinforcement_for_promotion = 3
        self.min_confidence_for_promotion = 0.7
    
    def consolidate(
        self,
        episodic_items: List[MemoryItem],
        existing_semantic: List[MemoryItem],
        existing_procedural: List[MemoryItem]
    ) -> ConsolidationResult:
        """
        Perform memory consolidation.
        
        Args:
            episodic_items: Episodic memories to consolidate
            existing_semantic: Existing semantic memories
            existing_procedural: Existing procedural memories
        
        Returns:
            ConsolidationResult with promoted and decayed memories
        """
        result = ConsolidationResult(
            promoted_count=0,
            decayed_count=0,
            merged_count=0
        )
        
        # Group episodic memories by content similarity
        clusters = self._cluster_memories(episodic_items)
        
        # Process each cluster
        for cluster in clusters:
            if len(cluster) >= self.min_reinforcement_for_promotion:
                # Check if this represents a stable fact
                if self._is_factual_pattern(cluster):
                    semantic_memory = self._promote_to_semantic(cluster)
                    if semantic_memory:
                        result.new_semantic_memories.append(semantic_memory)
                        result.promoted_count += 1
                
                # Check if this represents a behavioral pattern
                elif self._is_procedural_pattern(cluster):
                    procedural_memory = self._promote_to_procedural(cluster)
                    if procedural_memory:
                        result.new_procedural_memories.append(procedural_memory)
                        result.promoted_count += 1
        
        return result
    
    def _cluster_memories(self, items: List[MemoryItem]) -> List[List[MemoryItem]]:
        """
        Cluster similar episodic memories together.
        
        In production, this would use embedding similarity.
        For now, we use simple content-based clustering.
        """
        clusters = []
        used = set()
        
        for i, item in enumerate(items):
            if i in used:
                continue
            
            cluster = [item]
            used.add(i)
            
            for j, other in enumerate(items[i+1:], start=i+1):
                if j in used:
                    continue
                
                # Simple similarity check
                if self._are_similar(item.content, other.content):
                    cluster.append(other)
                    used.add(j)
            
            if len(cluster) > 1:
                clusters.append(cluster)
        
        return clusters
    
    def _are_similar(self, content1: str, content2: str, threshold: float = 0.6) -> bool:
        """Check if two memory contents are similar."""
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())
        
        if not words1 or not words2:
            return False
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return (intersection / union) > threshold if union > 0 else False
    
    def _is_factual_pattern(self, cluster: List[MemoryItem]) -> bool:
        """
        Determine if a cluster represents a stable fact.
        
        Factual patterns are:
        - Repeated statements about the same topic
        - High confidence
        - No contradictions
        """
        # Check confidence
        avg_confidence = sum(item.confidence for item in cluster) / len(cluster)
        if avg_confidence < self.min_confidence_for_promotion:
            return False
        
        # Check for contradictions (simplified)
        # In production, use LLM to detect contradictions
        contents = [item.content for item in cluster]
        has_negation = any("not" in c.lower() or "never" in c.lower() for c in contents)
        
        return not has_negation
    
    def _is_procedural_pattern(self, cluster: List[MemoryItem]) -> bool:
        """
        Determine if a cluster represents a behavioral pattern.
        
        Procedural patterns are:
        - Repeated behaviors or preferences
        - Consistent style or approach
        """
        # Look for preference indicators
        preference_keywords = ["prefer", "like", "usually", "always", "typically", "style"]
        
        return any(
            any(keyword in item.content.lower() for keyword in preference_keywords)
            for item in cluster
        )
    
    def _promote_to_semantic(self, cluster: List[MemoryItem]) -> MemoryItem:
        """
        Promote a cluster of episodic memories to semantic memory.
        
        This extracts the stable fact from repeated observations.
        """
        # Use the most confident item as base
        base_item = max(cluster, key=lambda x: x.confidence)
        
        # Calculate new confidence based on reinforcement
        new_confidence = min(base_item.confidence + (len(cluster) * 0.05), 1.0)
        
        return MemoryItem(
            id=str(uuid.uuid4()),
            user_id=base_item.user_id,
            content=base_item.content,
            embedding=base_item.embedding,
            memory_type=MemoryType.SEMANTIC,
            salience=min(base_item.salience + 0.1, 1.0),  # Boost salience
            confidence=new_confidence,
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
            decay_rate=0.01,  # Semantic memories decay slower
            reinforcement=len(cluster),
            inferred=True,  # Promoted memories are inferred
            editable=True,
            tags=base_item.tags + ["consolidated"]
        )
    
    def _promote_to_procedural(self, cluster: List[MemoryItem]) -> MemoryItem:
        """
        Promote a cluster of episodic memories to procedural memory.
        
        This extracts behavioral patterns and preferences.
        """
        # Combine insights from cluster
        base_item = cluster[0]
        
        # For procedural memory, we want to capture the pattern
        pattern_content = self._extract_pattern(cluster)
        
        return MemoryItem(
            id=str(uuid.uuid4()),
            user_id=base_item.user_id,
            content=pattern_content,
            embedding=base_item.embedding,
            memory_type=MemoryType.PROCEDURAL,
            salience=0.8,  # Procedural memories are important
            confidence=0.7,
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
            decay_rate=0.005,  # Procedural memories decay very slowly
            reinforcement=len(cluster),
            inferred=True,
            editable=True,
            tags=base_item.tags + ["pattern", "consolidated"]
        )
    
    def _extract_pattern(self, cluster: List[MemoryItem]) -> str:
        """
        Extract a behavioral pattern from a cluster.
        
        In production, this would use an LLM to synthesize the pattern.
        """
        # Simple pattern extraction for now
        contents = [item.content for item in cluster]
        
        # Find common themes
        if any("concise" in c.lower() for c in contents):
            return "User prefers concise, direct answers"
        elif any("detail" in c.lower() for c in contents):
            return "User prefers detailed explanations"
        else:
            return f"User behavioral pattern: {contents[0]}"
