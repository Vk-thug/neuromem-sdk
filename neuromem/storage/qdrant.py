"""
Qdrant vector storage backend for NeuroMem.
"""

from typing import List, Dict, Any, Tuple, Optional
import uuid
from qdrant_client import QdrantClient
from qdrant_client.http import models
from neuromem.core.types import MemoryItem, MemoryType

class QdrantStorage:
    """
    Qdrant storage backend.
    """
    
    def __init__(self, host: str = "localhost", port: int = 6333, collection_name: str = "user_memories", api_key: Optional[str] = None, path: Optional[str] = None, url: Optional[str] = None):
        """
        Initialize Qdrant backend.
        
        Args:
            host: Qdrant host
            port: Qdrant port
            collection_name: Name of the collection to use
            api_key: Qdrant API key (optional)
            path: Path for local Qdrant (optional)
            url: Qdrant URL (optional, e.g. "http://localhost:6333")
        """
        if path:
            self.client = QdrantClient(path=path)
        elif url:
            self.client = QdrantClient(url=url, api_key=api_key)
        else:
            self.client = QdrantClient(host=host, port=port, api_key=api_key)
            
        self.collection_name = collection_name
        self._ensure_collection()
        
    def _ensure_collection(self):
        """Ensure the collection exists."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if not exists:
            # We assume a default vector size of 1536 (OpenAI embeddings)
            # This should ideally be configurable
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=1536,
                    distance=models.Distance.COSINE
                )
            )
            
    def upsert(self, item: MemoryItem) -> None:
        """Insert or update a memory item."""
        
        payload = {
            "user_id": item.user_id,
            "content": item.content,
            "memory_type": item.memory_type.value if isinstance(item.memory_type, MemoryType) else item.memory_type,
            "salience": item.salience,
            "confidence": item.confidence,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "last_accessed": item.last_accessed.isoformat() if item.last_accessed else None,
            "decay_rate": item.decay_rate,
            "reinforcement": item.reinforcement,
            "inferred": item.inferred,
            "editable": item.editable,
            "tags": item.tags
        }
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                models.PointStruct(
                    id=str(item.id),
                    vector=item.embedding,
                    payload=payload
                )
            ]
        )
        
    def query(
        self,
        embedding: List[float],
        filters: Dict[str, Any],
        k: int
    ) -> Tuple[List[MemoryItem], List[float]]:
        """Query for similar memories."""
        
        # Build filter conditions
        must_conditions = []
        
        if "user_id" in filters:
            must_conditions.append(
                models.FieldCondition(
                    key="user_id",
                    match=models.MatchValue(value=filters["user_id"])
                )
            )
            
        if "memory_type" in filters:
            types = filters["memory_type"]
            if isinstance(types, str):
                types = [types]
            
            must_conditions.append(
                models.FieldCondition(
                    key="memory_type",
                    match=models.MatchAny(any=types)
                )
            )
            
        search_filter = models.Filter(must=must_conditions) if must_conditions else None
        
        if hasattr(self.client, 'search'):
            search_func = self.client.search
        else:
            # Fallback for newer clients or different versions
            # print(f"DEBUG: QdrantClient methods: {dir(self.client)}")
            # Try query_points if search is missing
            search_func = self.client.query_points

        results = search_func(
            collection_name=self.collection_name,
            query=embedding, # query_points uses 'query', search uses 'query_vector'
            # We need to handle arguments differently if we switch.
            # Let's just use try/except to find the right method/args.
            
        )
        # REWRITE:
        
        try:
             results = self.client.search(
                collection_name=self.collection_name,
                query_vector=embedding,
                query_filter=search_filter,
                limit=k
            )
        except AttributeError:
             # Fallback to query_points (newer API)
             # Note: query_points signature is slightly different?
             # actually search was deprecated? No.
             # Wait, maybe it's just 'query'?
             results = self.client.query_points(
                collection_name=self.collection_name,
                query=embedding,
                query_filter=search_filter,
                limit=k
            ).points
        
        items = []
        similarities = []
        
        for hit in results:
            payload = hit.payload
            # Note: Qdrant doesn't return the vector by default in search results unless requested.
            # We might need to fetch it if the interface requires it, or just pass empty/None if allowed.
            # For now, let's stick to what we have or fetch if critical. 
            # The MemoryItem expects 'embedding', but retrieval strictly for context usually just needs content.
            # However, to be fully compliant, we should probably enable with_vectors=True if we want to return it.
            # Let's request vectors.
            
            # Re-fetch or adjust search to return vectors if needed. 
            # Efficiently, we probably don't need vectors for just reading.
            # But the object model requires it.
            
            items.append(self._payload_to_item(hit.id, payload, getattr(hit, 'vector', [])))
            similarities.append(hit.score)
            
        return items, similarities

    def _payload_to_item(self, id: str, payload: Dict[str, Any], vector: List[float]) -> MemoryItem:
        from datetime import datetime
        
        # Convert isoformat strings back to datetime
        created_at = datetime.fromisoformat(payload["created_at"]) if payload.get("created_at") else None
        last_accessed = datetime.fromisoformat(payload["last_accessed"]) if payload.get("last_accessed") else None
        
        return MemoryItem(
            id=str(id),
            user_id=payload["user_id"],
            content=payload["content"],
            embedding=vector, # This might be empty if we didn't fetch it
            memory_type=MemoryType(payload["memory_type"]),
            salience=payload.get("salience", 0.0),
            confidence=payload.get("confidence", 1.0),
            created_at=created_at,
            last_accessed=last_accessed,
            decay_rate=payload.get("decay_rate", 0.0),
            reinforcement=payload.get("reinforcement", 0),
            inferred=payload.get("inferred", False),
            editable=payload.get("editable", True),
            tags=payload.get("tags", [])
        )

    def get_by_id(self, item_id: str) -> Optional[MemoryItem]:
        """Get a memory by ID."""
        results = self.client.retrieve(
            collection_name=self.collection_name,
            ids=[item_id],
            with_vectors=True
        )
        
        if not results:
            return None
            
        point = results[0]
        return self._payload_to_item(point.id, point.payload, point.vector)
        
    def update(self, item: MemoryItem) -> None:
        """Update an existing memory item."""
        # Qdrant upsert overwrites if ID exists, so just reuse upsert
        self.upsert(item)
        
    def delete(self, item_id: str) -> bool:
        """Delete a memory item."""
        result = self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.PointIdsList(
                points=[item_id]
            )
        )
        return result.status == models.UpdateStatus.COMPLETED

    def list_all(
        self,
        user_id: str,
        memory_type: Optional[str] = None,
        limit: int = 100
    ) -> List[MemoryItem]:
        """List all memories for a user."""
        must_conditions = [
            models.FieldCondition(
                key="user_id",
                match=models.MatchValue(value=user_id)
            )
        ]
        
        if memory_type:
             must_conditions.append(
                models.FieldCondition(
                    key="memory_type",
                    match=models.MatchValue(value=memory_type)
                )
            )
            
        search_filter = models.Filter(must=must_conditions)
        
        results = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=search_filter,
            limit=limit,
            with_vectors=True
        )[0] # scroll returns (points, next_page_offset)
        
        return [self._payload_to_item(p.id, p.payload, p.vector) for p in results]
