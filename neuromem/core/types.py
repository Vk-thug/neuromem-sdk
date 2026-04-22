"""
Core type definitions for the NeuroMem SDK.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional
from enum import Enum


class MemoryType(str, Enum):
    """Types of memory in the NeuroMem system."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    AFFECTIVE = "affective"
    WORKING = "working"  # Transient PFC working memory (never persisted to backend)


@dataclass
class EmbeddingMetadata:
    """Metadata about the embedding for ML versioning"""

    model_name: str = "text-embedding-3-large"
    model_version: str = "v1"
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    dimension: int = 3072


@dataclass
class RetrievalStats:
    """Statistics about memory retrieval performance"""

    retrieval_count: int = 0
    avg_similarity: float = 0.0
    last_retrieved: Optional[datetime] = None
    performance_score: float = 1.0  # 0-1, decays if not retrieved
    total_similarity: float = 0.0  # For calculating average


@dataclass
class MemoryItem:
    """
    A single memory item in the NeuroMem system.

    Attributes:
        id: Unique identifier for the memory
        user_id: ID of the user this memory belongs to
        content: The actual memory content
        embedding: Vector embedding of the content
        memory_type: Type of memory (episodic, semantic, procedural, affective)
        salience: How important/salient this memory is (0.0-1.0)
        confidence: How confident we are in this memory (0.0-1.0)
        created_at: When the memory was created
        last_accessed: When the memory was last retrieved
        decay_rate: Rate at which this memory decays over time
        reinforcement: Number of times this memory has been reinforced
        inferred: Whether this memory was inferred vs explicitly stated
        editable: Whether the user can edit this memory
        tags: Optional tags for categorization
    """

    id: str
    user_id: str
    content: str
    embedding: List[float]
    memory_type: MemoryType
    salience: float
    confidence: float
    created_at: datetime
    last_accessed: datetime
    decay_rate: float
    reinforcement: int
    inferred: bool
    editable: bool
    tags: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    embedding_metadata: Optional[EmbeddingMetadata] = None
    retrieval_stats: Optional[RetrievalStats] = None
    strength: float = 1.0  # Salience-based memory strength

    def to_dict(self):
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "content": self.content,
            "embedding": self.embedding,
            "memory_type": (
                self.memory_type.value
                if isinstance(self.memory_type, MemoryType)
                else self.memory_type
            ),
            "salience": self.salience,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "decay_rate": self.decay_rate,
            "reinforcement": self.reinforcement,
            "inferred": self.inferred,
            "editable": self.editable,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Create from dictionary."""
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            content=data["content"],
            embedding=data["embedding"],
            memory_type=MemoryType(data["memory_type"]),
            salience=data["salience"],
            confidence=data["confidence"],
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if isinstance(data["created_at"], str)
                else data["created_at"]
            ),
            last_accessed=(
                datetime.fromisoformat(data["last_accessed"])
                if isinstance(data["last_accessed"], str)
                else data["last_accessed"]
            ),
            decay_rate=data["decay_rate"],
            reinforcement=data["reinforcement"],
            inferred=data["inferred"],
            editable=data["editable"],
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class MemoryLink:
    """An explicit relationship between two memories."""

    source_id: str
    target_id: str
    link_type: str  # "derived_from" | "contradicts" | "reinforces" | "related" | "supersedes"
    strength: float  # 0.0-1.0
    created_at: datetime
    metadata: dict = field(default_factory=dict)
    # Temporal validity (v0.4.0) — when this relationship is/was active
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None  # None = still active

    def to_dict(self) -> dict:
        result = {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "link_type": self.link_type,
            "strength": self.strength,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }
        if self.valid_from is not None:
            result["valid_from"] = self.valid_from.isoformat()
        if self.valid_to is not None:
            result["valid_to"] = self.valid_to.isoformat()
        return result

    def is_active(self, as_of: Optional[datetime] = None) -> bool:
        """Check if this link is active at the given time."""
        if as_of is None:
            as_of = datetime.now(timezone.utc)
        if self.valid_from and as_of < self.valid_from:
            return False
        if self.valid_to and as_of > self.valid_to:
            return False
        return True


@dataclass
class RetrievalContext:
    """Context for memory retrieval."""

    query: str
    task_type: str
    k: int
    filters: dict = field(default_factory=dict)


@dataclass
class ConsolidationResult:
    """Result of a consolidation operation."""

    promoted_count: int
    decayed_count: int
    merged_count: int
    new_semantic_memories: List[MemoryItem] = field(default_factory=list)
    new_procedural_memories: List[MemoryItem] = field(default_factory=list)
