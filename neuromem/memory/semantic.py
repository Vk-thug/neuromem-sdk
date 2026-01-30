"""
Semantic memory for NeuroMem.

Stores stable facts and knowledge about the user (what is true).
"""

from typing import List, Dict, Any, Tuple
from neuromem.core.types import MemoryItem, MemoryType
from neuromem.storage.base import MemoryBackend


class SemanticMemory:
    """
    Semantic memory - stable facts and knowledge.
    
    This is like the neocortex in the brain - stores consolidated
    knowledge that has been verified through repetition.
    """
    
    def __init__(self, backend: MemoryBackend, user_id: str):
        """
        Initialize semantic memory.
        
        Args:
            backend: Storage backend
            user_id: User ID this memory belongs to
        """
        self.backend = backend
        self.user_id = user_id
    
    def store(self, item: MemoryItem):
        """
        Store a semantic memory.
        
        Args:
            item: Memory item to store
        """
        if item.memory_type != MemoryType.SEMANTIC:
            raise ValueError("Item must be semantic memory type")
        
        self.backend.upsert(item)
    
    def retrieve(
        self,
        embedding: List[float],
        filters: Dict[str, Any],
        k: int
    ) -> Tuple[List[MemoryItem], List[float]]:
        """
        Retrieve similar semantic memories.
        
        Args:
            embedding: Query embedding
            filters: Additional filters
            k: Number of results
        
        Returns:
            Tuple of (items, similarities)
        """
        filters["user_id"] = self.user_id
        
        # Allow querying both semantic and procedural if not specified
        if "memory_type" not in filters:
            filters["memory_type"] = [MemoryType.SEMANTIC.value]
        
        return self.backend.query(embedding, filters, k)
    
    def get_all(self, limit: int = 100) -> List[MemoryItem]:
        """
        Get all semantic memories for the user.
        
        Args:
            limit: Maximum number to return
        
        Returns:
            List of semantic memories
        """
        return self.backend.list_all(
            self.user_id,
            memory_type=MemoryType.SEMANTIC.value,
            limit=limit
        )
    
    def get_by_id(self, memory_id: str) -> MemoryItem | None:
        """
        Get a specific semantic memory.
        
        Args:
            memory_id: Memory ID
        
        Returns:
            Memory item or None
        """
        item = self.backend.get_by_id(memory_id)
        if item and item.user_id == self.user_id and item.memory_type == MemoryType.SEMANTIC:
            return item
        return None
    
    def update(self, item: MemoryItem):
        """
        Update a semantic memory.
        
        Args:
            item: Updated memory item
        """
        if item.user_id != self.user_id:
            raise ValueError("Cannot update memory for different user")
        
        self.backend.update(item)
    
    def delete(self, memory_id: str) -> bool:
        """
        Delete a semantic memory.
        
        Args:
            memory_id: Memory ID
        
        Returns:
            True if deleted
        """
        item = self.get_by_id(memory_id)
        if item:
            return self.backend.delete(memory_id)
        return False
