"""
Core type definitions for the brain-faithful memory system.

SparseCode models dentate gyrus pattern separation output.
BrainState persists per-user brain system state across sessions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass(frozen=True)
class SparseCode:
    """Sparse representation produced by the dentate gyrus pattern separator.

    The dentate gyrus expands inputs into a high-dimensional space and
    applies k-winners-take-all to decorrelate similar memories.

    Attributes:
        dense_vector: Original dense embedding (preserved for backward compat).
        sparse_indices: Indices of active units after k-WTA selection.
        sparse_values: Activation values at the active indices.
        sparsity: Fraction of units that are zero (typically 0.95).
        expansion_dim: Dimensionality of the expanded space.
    """

    dense_vector: List[float]
    sparse_indices: List[int]
    sparse_values: List[float]
    sparsity: float
    expansion_dim: int

    def to_dict(self) -> dict:
        return {
            "sparse_indices": self.sparse_indices,
            "sparse_values": self.sparse_values,
            "sparsity": self.sparsity,
            "expansion_dim": self.expansion_dim,
        }

    @classmethod
    def from_dict(cls, data: dict, dense_vector: List[float]) -> SparseCode:
        return cls(
            dense_vector=dense_vector,
            sparse_indices=data["sparse_indices"],
            sparse_values=data["sparse_values"],
            sparsity=data["sparsity"],
            expansion_dim=data["expansion_dim"],
        )


@dataclass
class BrainState:
    """Per-user brain system state persisted across sessions.

    Stored as a JSON sidecar in the existing storage backend
    (special MemoryItem with id ``__brain_state__{user_id}``).

    Attributes:
        user_id: Owner of this brain state.
        working_memory_slots: Up to 4 memory IDs currently in working memory.
        td_values: Task-type → embedding-cluster → learned value estimates.
        schema_centroids: Entity → centroid embedding for schema congruence.
        last_ripple: Timestamp of the last sharp-wave ripple replay cycle.
        maturation_queue: Memory IDs pending maturation (hemodynamic delay).
    """

    user_id: str
    working_memory_slots: List[str] = field(default_factory=list)
    td_values: Dict[str, Dict[str, float]] = field(default_factory=dict)
    schema_centroids: Dict[str, List[float]] = field(default_factory=dict)
    last_ripple: Optional[datetime] = None
    maturation_queue: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "working_memory_slots": self.working_memory_slots,
            "td_values": self.td_values,
            "schema_centroids": self.schema_centroids,
            "last_ripple": (self.last_ripple.isoformat() if self.last_ripple else None),
            "maturation_queue": self.maturation_queue,
        }

    @classmethod
    def from_dict(cls, data: dict) -> BrainState:
        last_ripple = data.get("last_ripple")
        if isinstance(last_ripple, str):
            last_ripple = datetime.fromisoformat(last_ripple)
        return cls(
            user_id=data["user_id"],
            working_memory_slots=data.get("working_memory_slots", []),
            td_values=data.get("td_values", {}),
            schema_centroids=data.get("schema_centroids", {}),
            last_ripple=last_ripple,
            maturation_queue=data.get("maturation_queue", []),
        )
