"""
Dentate Gyrus — Pattern Separation.

The dentate gyrus performs expansion recoding: transforming overlapping input
patterns into sparse, decorrelated representations. Only ~2-5% of granule
cells are active at any time, ensuring similar inputs produce maximally
different sparse codes.

Algorithm:
1. Random projection: input (d) → expanded space (d * expansion_ratio)
2. ReLU non-linearity (biological: firing threshold)
3. k-Winners-Take-All: keep only top-k activations, zero the rest

The projection matrix is seeded per user_id for privacy isolation and
reproducibility across restarts.

Reference: Yassa & Stark (2011), "Pattern separation in the hippocampus"
"""

from __future__ import annotations

import hashlib
from typing import List

import numpy as np

from neuromem.brain.types import SparseCode
from neuromem.constants import DEFAULT_PATTERN_SEPARATION_EXPANSION, DEFAULT_SPARSITY


class PatternSeparator:
    """Dentate Gyrus pattern separation via sparse random projection.

    Parameters
    ----------
    input_dim:
        Dimensionality of the dense input embedding.
    expansion_ratio:
        Factor by which to expand the input space (default 4x).
    sparsity:
        Fraction of units that remain active after k-WTA (default 0.05).
    user_id:
        Seed for the random projection matrix (privacy isolation).
    """

    def __init__(
        self,
        input_dim: int = 1536,
        expansion_ratio: int = DEFAULT_PATTERN_SEPARATION_EXPANSION,
        sparsity: float = DEFAULT_SPARSITY,
        user_id: str = "default",
    ) -> None:
        self.input_dim = input_dim
        self.expansion_ratio = expansion_ratio
        self.expansion_dim = input_dim * expansion_ratio
        self.sparsity = sparsity
        self.k = max(1, int(self.expansion_dim * sparsity))
        self._user_id = user_id

        # Build projection lazily or eagerly
        self._projection = self._build_projection(input_dim)

    def _build_projection(self, input_dim: int) -> np.ndarray:
        """Build the random projection matrix for the given input dimension."""
        expansion_dim = input_dim * self.expansion_ratio
        seed = int(hashlib.md5(self._user_id.encode()).hexdigest()[:8], 16)
        rng = np.random.RandomState(seed)
        # Sparse random projection (Achlioptas, 2003)
        # Values from {-1, 0, +1} with probabilities {1/6, 2/3, 1/6}
        choices = rng.choice(
            [-1.0, 0.0, 1.0],
            size=(expansion_dim, input_dim),
            p=[1 / 6, 2 / 3, 1 / 6],
        )
        return choices / np.sqrt(input_dim)

    def separate(self, embedding: List[float]) -> SparseCode:
        """Apply DG pattern separation to a dense embedding.

        Parameters
        ----------
        embedding:
            Dense input vector (typically 1536d from text-embedding-3-large).

        Returns
        -------
        SparseCode:
            High-dimensional sparse representation with only top-k activations.
        """
        x = np.array(embedding, dtype=np.float64)

        # Auto-adapt projection if input dimension changed
        if x.shape[0] != self._projection.shape[1]:
            self.input_dim = x.shape[0]
            self.expansion_dim = self.input_dim * self.expansion_ratio
            self.k = max(1, int(self.expansion_dim * self.sparsity))
            self._projection = self._build_projection(self.input_dim)

        # Step 1: Random projection into expanded space
        expanded = self._projection @ x

        # Step 2: ReLU (biological firing threshold)
        expanded = np.maximum(expanded, 0.0)

        # Step 3: k-Winners-Take-All
        if len(expanded) > self.k:
            threshold_idx = np.argpartition(expanded, -self.k)[-self.k :]
            mask = np.zeros_like(expanded)
            mask[threshold_idx] = 1.0
            expanded = expanded * mask

        # Extract non-zero indices and values
        nonzero_mask = expanded > 0
        indices = np.where(nonzero_mask)[0].tolist()
        values = expanded[nonzero_mask].tolist()

        actual_sparsity = 1.0 - (len(indices) / self.expansion_dim)

        return SparseCode(
            dense_vector=embedding,
            sparse_indices=indices,
            sparse_values=values,
            sparsity=actual_sparsity,
            expansion_dim=self.expansion_dim,
        )
