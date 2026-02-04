"""
Main Memory class for NeuroMem.

This class serves as the main entry point for the SDK, orchestrating
interactions between Vector Stores, History Stores, and LLMs.
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import yaml
from neuromem.core.types import MemoryItem
from neuromem.storage.base import MemoryBackend
from neuromem.storage.qdrant import QdrantStorage
from neuromem.storage.postgres import PostgresBackend
from neuromem.storage.sqlite import SQLiteBackend

class Memory:
    """
    Main Memory class.
    
    Orchestrates storage backends and provides a unified API.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Memory.
        
        Args:
            config: Configuration dictionary. If None, looks for neuromem.yaml.
        """
        self.config = config or self._load_config()
        self.vector_store = self._init_vector_store()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        # Simple default for now, ideally load from file
        return {
            "vector_store": {"type": "qdrant", "config": {"host": "localhost", "port": 6333}}
        }
        
    def _init_vector_store(self) -> MemoryBackend:
        """Initialize vector store based on config."""
        vs_config = self.config.get("vector_store", {})
        param_config = vs_config.get("config", {})
        
        type_ = vs_config.get("type", "qdrant")
        
        if type_ == "qdrant":
            return QdrantStorage(**param_config)
        elif type_ == "postgres":
             return PostgresBackend(conn_str=param_config.get("url"))
        elif type_ == "sqlite":
             return SQLiteBackend(db_path=param_config.get("url", "neuromem.db"))
             
        # Default fallback
        return QdrantStorage(**param_config)

    def add(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a memory.
        
        Args:
            messages: Content to store (str or list of messages)
            user_id: User ID
            metadata: Additional metadata
            filters: Filters
            
        Returns:
            Info about stored memory
        """
        # 2. Embed and Store in Vector Store
        # For simplicity, assuming 'messages' is a string content for now
        # In a real impl, we'd use an Embedder here.
        
        content = str(messages)
        # Mock embedding for now or use the one if passed
        embedding = [0.1] * 1536 
        
        import uuid
        item = MemoryItem(
            id=str(uuid.uuid4()),
            user_id=user_id,
            content=content,
            embedding=embedding,
            memory_type="episodic", # default
            salience=1.0,
            confidence=1.0,
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
            decay_rate=0.0,
            reinforcement=1,
            inferred=False,
            editable=True,
            tags=list(metadata.keys()) if metadata else []
        )
        
        self.vector_store.upsert(item)
        
        return {"id": item.id, "status": "success"}

    def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search memories.
        
        Args:
            query: Search query
            user_id: User ID
            limit: Number of results
            filters: Additional filters
            
        Returns:
            List of search results
        """
        # Mock embedding of query
        query_embedding = [0.1] * 1536 
        
        search_filters = filters or {}
        if user_id:
            search_filters["user_id"] = user_id
            
        items, scores = self.vector_store.query(query_embedding, search_filters, limit)
        
        results = []
        for item, score in zip(items, scores):
            results.append({
                "id": item.id,
                "content": item.content,
                "score": score,
                "metadata": {
                    "created_at": item.created_at,
                    "tags": item.tags
                }
            })
            
        return results

    def get_all(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """GetAll memories for a user."""
        items = self.vector_store.list_all(user_id=user_id, limit=limit)
        return [
            {"id": i.id, "content": i.content, "metadata": {"tags": i.tags}}
            for i in items
        ]
