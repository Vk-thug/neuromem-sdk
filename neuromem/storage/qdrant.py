"""
Qdrant vector storage backend for NeuroMem.

Compatible with qdrant-client >= 1.17 (query_points API).
"""

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timezone
from qdrant_client import QdrantClient
from qdrant_client.http import models
from neuromem.core.types import MemoryItem, MemoryType
from neuromem.utils.logging import get_logger

logger = get_logger(__name__)


class QdrantStorage:
    """Qdrant storage backend for NeuroMem."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = "neuromem",
        vector_size: int = 768,
        api_key: Optional[str] = None,
        path: Optional[str] = None,
        url: Optional[str] = None,
    ):
        if path:
            self.client = QdrantClient(path=path)
        elif url:
            self.client = QdrantClient(url=url, api_key=api_key)
        else:
            self.client = QdrantClient(host=host, port=port, api_key=api_key)

        self.collection_name = collection_name
        self.vector_size = vector_size
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Ensure the collection exists with correct vector config."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
            logger.info(
                "Created Qdrant collection",
                extra={"collection": self.collection_name, "vector_size": self.vector_size},
            )

    def upsert(self, item: MemoryItem) -> None:
        """Insert or update a memory item."""
        payload = {
            "user_id": item.user_id,
            "content": item.content,
            "memory_type": (
                item.memory_type.value
                if isinstance(item.memory_type, MemoryType)
                else item.memory_type
            ),
            "salience": item.salience,
            "confidence": item.confidence,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "last_accessed": item.last_accessed.isoformat() if item.last_accessed else None,
            "decay_rate": item.decay_rate,
            "reinforcement": item.reinforcement,
            "inferred": item.inferred,
            "editable": item.editable,
            "tags": item.tags,
            "metadata": item.metadata if isinstance(item.metadata, dict) else {},
        }

        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                models.PointStruct(
                    id=str(item.id),
                    vector=item.embedding,
                    payload=payload,
                )
            ],
        )

    def query(
        self,
        embedding: List[float],
        filters: Dict[str, Any],
        k: int,
    ) -> Tuple[List[MemoryItem], List[float]]:
        """Query for similar memories using vector search."""
        query_filter = self._build_filter(filters)

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=embedding,
            query_filter=query_filter,
            limit=k,
            with_payload=True,
        )

        items = []
        similarities = []

        for point in results.points:
            items.append(self._point_to_item(point.id, point.payload, []))
            similarities.append(point.score)

        return items, similarities

    def get_by_id(self, item_id: str) -> Optional[MemoryItem]:
        """Get a memory by ID."""
        results = self.client.retrieve(
            collection_name=self.collection_name,
            ids=[item_id],
            with_vectors=True,
        )

        if not results:
            return None

        point = results[0]
        return self._point_to_item(point.id, point.payload, point.vector)

    def update(self, item: MemoryItem) -> None:
        """Update an existing memory item."""
        self.upsert(item)

    def delete(self, item_id: str) -> bool:
        """Delete a memory item."""
        result = self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.PointIdsList(points=[item_id]),
        )
        return result.status == models.UpdateStatus.COMPLETED

    def list_all(
        self,
        user_id: str,
        memory_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[MemoryItem]:
        """List all memories for a user."""
        must_conditions = [
            models.FieldCondition(
                key="user_id",
                match=models.MatchValue(value=user_id),
            )
        ]

        if memory_type:
            must_conditions.append(
                models.FieldCondition(
                    key="memory_type",
                    match=models.MatchValue(value=memory_type),
                )
            )

        results, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(must=must_conditions),
            limit=limit,
            with_vectors=True,
        )

        return [self._point_to_item(p.id, p.payload, p.vector) for p in results]

    def close(self) -> None:
        """Close the client connection."""
        self.client.close()

    def _build_filter(self, filters: Dict[str, Any]) -> Optional[models.Filter]:
        """Build Qdrant filter from dict."""
        must_conditions = []

        if "user_id" in filters:
            must_conditions.append(
                models.FieldCondition(
                    key="user_id",
                    match=models.MatchValue(value=filters["user_id"]),
                )
            )

        if "memory_type" in filters:
            types = filters["memory_type"]
            if isinstance(types, str):
                types = [types]
            must_conditions.append(
                models.FieldCondition(
                    key="memory_type",
                    match=models.MatchAny(any=types),
                )
            )

        return models.Filter(must=must_conditions) if must_conditions else None

    def _point_to_item(
        self, point_id: str, payload: Dict[str, Any], vector: List[float]
    ) -> MemoryItem:
        """Convert Qdrant point to MemoryItem."""
        created_at = (
            datetime.fromisoformat(payload["created_at"])
            if payload.get("created_at")
            else datetime.now(timezone.utc)
        )
        last_accessed = (
            datetime.fromisoformat(payload["last_accessed"])
            if payload.get("last_accessed")
            else datetime.now(timezone.utc)
        )

        return MemoryItem(
            id=str(point_id),
            user_id=payload.get("user_id", ""),
            content=payload.get("content", ""),
            embedding=vector if vector else [],
            memory_type=MemoryType(payload.get("memory_type", "episodic")),
            salience=payload.get("salience", 0.5),
            confidence=payload.get("confidence", 0.8),
            created_at=created_at,
            last_accessed=last_accessed,
            decay_rate=payload.get("decay_rate", 0.05),
            reinforcement=payload.get("reinforcement", 1),
            inferred=payload.get("inferred", False),
            editable=payload.get("editable", True),
            tags=payload.get("tags", []),
            metadata=payload.get("metadata", {}),
        )
