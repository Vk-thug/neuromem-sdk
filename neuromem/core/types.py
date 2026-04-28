"""
Core type definitions for the NeuroMem SDK.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterator, List, Optional
from enum import Enum, IntEnum


class MemoryType(str, Enum):
    """Types of memory in the NeuroMem system."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    AFFECTIVE = "affective"
    WORKING = "working"  # Transient PFC working memory (never persisted to backend)


class BeliefState(IntEnum):
    """Source-monitoring framework (Johnson, Hashtroudi, Lindsay 1993).

    Replaces the v0.3.x ``inferred: bool`` 1-bit signal with a 4-level tier so
    downstream LLMs can calibrate confidence in retrieved context. Ordered by
    epistemic strength so ``BeliefState.KNOWN > BeliefState.BELIEVED`` is True
    and tiebreaks (per H1-R12) sort KNOWN first.
    """

    SPECULATED = 0   # LLM-extrapolated beyond stated facts
    INFERRED = 1     # LLM-extracted from stated facts
    BELIEVED = 2     # User-stated, not corroborated
    KNOWN = 3        # User-stated, cross-corroborated across sessions

    @classmethod
    def from_legacy_inferred(cls, inferred: bool) -> "BeliefState":
        """Migrate v0.3.x ``inferred: bool`` to a BeliefState.

        ``inferred=True`` → INFERRED. ``inferred=False`` → BELIEVED (NOT KNOWN —
        KNOWN requires cross-session corroboration that v0.3.x never tracked).
        """
        return cls.INFERRED if inferred else cls.BELIEVED


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
        inferred: DEPRECATED in v0.4.0 — kept for backward-compat. Use
            ``belief_state`` instead. Mirrors ``belief_state == INFERRED``.
        editable: Whether the user can edit this memory
        tags: Optional tags for categorization
        belief_state: Source-monitoring tier (SPECULATED/INFERRED/BELIEVED/KNOWN).
            Default ``BELIEVED`` for direct user observations. v0.4.0+.
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
    belief_state: BeliefState = BeliefState.BELIEVED

    def __post_init__(self) -> None:
        """Reconcile ``inferred`` (legacy) and ``belief_state`` (v0.4.0+).

        If only ``inferred`` is set (legacy callers), derive belief_state. If
        only belief_state is set, derive inferred. If both are set explicitly,
        belief_state wins and inferred is recomputed — single source of truth.
        """
        # Caller passed inferred=True but left belief_state at default → migrate.
        if self.inferred and self.belief_state == BeliefState.BELIEVED:
            self.belief_state = BeliefState.INFERRED
        # Always re-mirror so the legacy field stays consistent.
        self.inferred = self.belief_state == BeliefState.INFERRED

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
            "belief_state": int(self.belief_state),
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Create from dictionary.

        Backward-compat: rows persisted by v0.3.x lack ``belief_state`` — derive
        from legacy ``inferred`` via ``BeliefState.from_legacy_inferred``.
        """
        legacy_inferred = data["inferred"]
        if "belief_state" in data and data["belief_state"] is not None:
            belief_state = BeliefState(int(data["belief_state"]))
        else:
            belief_state = BeliefState.from_legacy_inferred(legacy_inferred)

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
            inferred=legacy_inferred,
            editable=data["editable"],
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            belief_state=belief_state,
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


class RetrievalResult(List[MemoryItem]):
    """Wrapper around a retrieval call's items + metadata.

    v0.4.0 introduces this so v0.5.0's H2-D7 calibrated abstention can populate
    ``confidence`` and ``abstained`` without a second breaking change.

    Backward-compat: subclasses ``list[MemoryItem]`` directly, so:
    - ``isinstance(memory.retrieve(...), list)`` is True.
    - ``memory.retrieve(...) == []`` works for empty results.
    - ``for item in result`` / ``len(result)`` / ``result[0]`` all unchanged.

    The new attributes (``confidence``, ``abstained``, ``abstention_reason``)
    are populated by H2-D7 in v0.5.0; defaults preserve v0.3.x semantics.
    """

    confidence: float
    abstained: bool
    abstention_reason: Optional[str]

    def __init__(
        self,
        items: Optional[List[MemoryItem]] = None,
        *,
        confidence: float = 1.0,
        abstained: bool = False,
        abstention_reason: Optional[str] = None,
    ) -> None:
        super().__init__(items or [])
        self.confidence = confidence
        self.abstained = abstained
        self.abstention_reason = abstention_reason

    @property
    def items(self) -> List[MemoryItem]:
        """Alias — `result.items` returns self as a list view.

        Provided so call-sites that prefer the dataclass-style access
        (``result.items``) read the same data as iteration over ``result``.
        """
        return list(self)
