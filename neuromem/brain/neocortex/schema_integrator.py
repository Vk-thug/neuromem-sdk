"""
Neocortex — Schema-Based Integration (Complementary Learning Systems).

The neocortex maintains schema centroids — average embeddings for known
topics/entities. When new information is schema-congruent (high similarity
to an existing centroid), it consolidates faster. When schema-incongruent,
it requires full hippocampal encoding and slow consolidation.

The interleave ratio controls how many old semantic memories are included
in consolidation prompts alongside new episodic ones, preventing
catastrophic forgetting.

Reference: McClelland, McNaughton & O'Reilly (1995), "Why there are
complementary learning systems in the hippocampus and neocortex"
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from neuromem.constants import (
    DEFAULT_INTERLEAVE_RATIO,
    DEFAULT_SCHEMA_CONGRUENCE_THRESHOLD,
)


class SchemaIntegrator:
    """Neocortical schema tracking and congruence-based consolidation.

    Parameters
    ----------
    congruence_threshold:
        Cosine similarity above which new info is considered schema-congruent.
    interleave_ratio:
        Fraction of old semantic memories to mix into consolidation replay.
    """

    def __init__(
        self,
        congruence_threshold: float = DEFAULT_SCHEMA_CONGRUENCE_THRESHOLD,
        interleave_ratio: float = DEFAULT_INTERLEAVE_RATIO,
    ) -> None:
        self.congruence_threshold = congruence_threshold
        self.interleave_ratio = interleave_ratio

    def compute_congruence(
        self,
        embedding: List[float],
        schema_centroids: Dict[str, List[float]],
    ) -> Tuple[float, str]:
        """Compute how well a new memory fits existing schemas.

        Parameters
        ----------
        embedding:
            The new memory's embedding.
        schema_centroids:
            Entity/topic → centroid embedding mapping.

        Returns
        -------
        Tuple of (max_congruence_score, best_matching_schema_key).
        Returns (0.0, "") if no schemas exist.
        """
        if not schema_centroids:
            return 0.0, ""

        emb = np.array(embedding, dtype=np.float64)
        emb_norm = np.linalg.norm(emb)
        if emb_norm < 1e-12:
            return 0.0, ""
        emb = emb / emb_norm

        best_score = 0.0
        best_key = ""

        for key, centroid in schema_centroids.items():
            c = np.array(centroid, dtype=np.float64)
            c_norm = np.linalg.norm(c)
            if c_norm < 1e-12:
                continue
            c = c / c_norm
            score = float(np.dot(emb, c))
            if score > best_score:
                best_score = score
                best_key = key

        return best_score, best_key

    def compute_salience_boost(
        self,
        embedding: List[float],
        schema_centroids: Dict[str, List[float]],
    ) -> float:
        """Compute salience boost based on schema congruence.

        Schema-congruent memories get accelerated consolidation (higher salience).
        Schema-incongruent memories get no boost (require slow consolidation).

        Returns
        -------
        Boost value in [0.0, 0.5].
        """
        score, _ = self.compute_congruence(embedding, schema_centroids)
        if score >= self.congruence_threshold:
            # Linear boost: 0.0 at threshold, 0.5 at 1.0
            return (
                0.5
                * (score - self.congruence_threshold)
                / (1.0 - self.congruence_threshold + 1e-12)
            )
        return 0.0

    def update_centroids(
        self,
        entity: str,
        embedding: List[float],
        schema_centroids: Dict[str, List[float]],
        momentum: float = 0.9,
    ) -> Dict[str, List[float]]:
        """Update a schema centroid with exponential moving average.

        Parameters
        ----------
        entity:
            The entity/topic key to update.
        embedding:
            New embedding to incorporate.
        schema_centroids:
            Current centroids (mutated in place).
        momentum:
            EMA momentum (0.9 = slow update, preserves existing schema).

        Returns
        -------
        Updated schema_centroids dict.
        """
        emb = np.array(embedding, dtype=np.float64)

        if entity in schema_centroids:
            old = np.array(schema_centroids[entity], dtype=np.float64)
            updated = momentum * old + (1 - momentum) * emb
            # Re-normalize to unit sphere
            norm = np.linalg.norm(updated)
            if norm > 1e-12:
                updated = updated / norm
            schema_centroids[entity] = updated.tolist()
        else:
            norm = np.linalg.norm(emb)
            if norm > 1e-12:
                emb = emb / norm
            schema_centroids[entity] = emb.tolist()

        return schema_centroids

    def select_interleave_memories(
        self,
        existing_semantic_ids: List[str],
        new_count: int,
    ) -> int:
        """Compute how many old semantic memories to interleave in replay.

        Parameters
        ----------
        existing_semantic_ids:
            Available semantic memory IDs.
        new_count:
            Number of new episodic memories being consolidated.

        Returns
        -------
        Number of old semantic memories to include.
        """
        target = int(new_count * self.interleave_ratio)
        return min(target, len(existing_semantic_ids))
