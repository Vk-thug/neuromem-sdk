"""
Procedural memory for NeuroMem.

Stores user style, preferences, and behavioral patterns (how the user thinks).
"""

import statistics
from typing import List, Dict, Any, Tuple
from neuromem.core.types import MemoryItem, MemoryType
from neuromem.storage.base import MemoryBackend


class ProceduralMemory:
    """
    Procedural memory - user style and behavioral patterns.
    
    This learns "how the user thinks" - their communication style,
    preferences, and patterns. This is your moat.
    """
    
    def __init__(self, backend: MemoryBackend, user_id: str):
        """
        Initialize procedural memory.
        
        Args:
            backend: Storage backend
            user_id: User ID this memory belongs to
        """
        self.backend = backend
        self.user_id = user_id
    
    def store(self, item: MemoryItem):
        """
        Store a procedural memory.
        
        Args:
            item: Memory item to store
        """
        if item.memory_type != MemoryType.PROCEDURAL:
            raise ValueError("Item must be procedural memory type")
        
        # Write to vector store
        self.backend.upsert(item)
    
    def retrieve(
        self,
        embedding: List[float],
        filters: Dict[str, Any],
        k: int
    ) -> Tuple[List[MemoryItem], List[float]]:
        """
        Retrieve procedural memories.
        
        Args:
            embedding: Query embedding
            filters: Additional filters
            k: Number of results
        
        Returns:
            Tuple of (items, similarities)
        """
        filters["user_id"] = self.user_id
        filters["memory_type"] = MemoryType.PROCEDURAL.value
        
        return self.backend.query(embedding, filters, k)
    
    def get_all(self, limit: int = 100) -> List[MemoryItem]:
        """
        Get all procedural memories for the user.
        
        Args:
            limit: Maximum number to return
        
        Returns:
            List of procedural memories
        """
        return self.backend.list_all(
            self.user_id,
            memory_type=MemoryType.PROCEDURAL.value,
            limit=limit
        )
    
    def get_by_id(self, memory_id: str) -> MemoryItem | None:
        """
        Get a specific procedural memory.
        
        Args:
            memory_id: Memory ID
        
        Returns:
            Memory item or None
        """
        item = self.backend.get_by_id(memory_id)
        if item and item.user_id == self.user_id and item.memory_type == MemoryType.PROCEDURAL:
            return item
        return None
    
    def update(self, item: MemoryItem):
        """
        Update a procedural memory.
        
        Args:
            item: Updated memory item
        """
        if item.user_id != self.user_id:
            raise ValueError("Cannot update memory for different user")
        
        # Update vector store
        self.backend.update(item)
    
    def delete(self, memory_id: str) -> bool:
        """
        Delete a procedural memory.
        
        Args:
            memory_id: Memory ID
        
        Returns:
            True if deleted
        """
        item = self.get_by_id(memory_id)
        if item:
            # Delete from vector store
            return self.backend.delete(memory_id)
        return False
    
    def extract_style_profile(self, messages: List[str]) -> Dict[str, Any]:
        """
        Extract user style profile from messages.
        
        This is the "moat" - learning how the user communicates.
        
        Args:
            messages: List of user messages
        
        Returns:
            Style profile dictionary
        """
        if not messages:
            return {}
        
        # Analyze message length
        lengths = [len(m.split()) for m in messages]
        avg_length = statistics.mean(lengths) if lengths else 0
        
        # Detect structure preference
        prefers_bullets = sum(1 for m in messages if "- " in m or "* " in m or "\n" in m) / len(messages)
        
        # Detect technical depth
        tech_terms = ["agent", "schema", "vector", "graph", "embedding", "api", "database", "function"]
        tech_density = sum(
            sum(1 for term in tech_terms if term in m.lower())
            for m in messages
        ) / len(messages)
        
        # Detect tone
        analytical_indicators = ["why", "how", "explain", "because", "therefore"]
        analytical_score = sum(
            sum(1 for ind in analytical_indicators if ind in m.lower())
            for m in messages
        ) / len(messages)
        
        # Detect question frequency
        question_ratio = sum(1 for m in messages if "?" in m) / len(messages)
        
        return {
            "avg_message_length": avg_length,
            "length_category": "concise" if avg_length < 20 else "detailed" if avg_length > 50 else "moderate",
            "prefers_bullets": prefers_bullets > 0.3,
            "technical_depth": "high" if tech_density > 2 else "medium" if tech_density > 0.5 else "low",
            "tone": "analytical" if analytical_score > 0.5 else "direct",
            "asks_questions": question_ratio > 0.3,
            "sample_size": len(messages)
        }
    
    def get_style_summary(self) -> str:
        """
        Get a human-readable summary of user style.
        
        Returns:
            Style summary string
        """
        procedural_items = self.get_all()
        
        if not procedural_items:
            return "No style profile available yet."
        
        # Extract key patterns
        patterns = []
        for item in procedural_items:
            patterns.append(item.content)
        
        return "\n".join(patterns)
