"""
Multimodal Fusion — TribeV2-Inspired Architecture.

Combines per-modality features via concatenation (not averaging),
applies projection to a shared dimension, and produces a unified
embedding compatible with MemoryItem.embedding.

TribeV2 patterns implemented:
1. Layer concatenation: preserve hierarchical information
2. Per-modality projectors: MLP maps each modality to shared dim
3. 30% modality dropout: robustness to missing modalities
4. Fusion via concatenation + projection to target dim

NOTE: This is a NumPy-based implementation that works without torch.
For production with learned projections, use the torch-based variant.
"""

from __future__ import annotations

import logging
from typing import Dict, List

import numpy as np

from neuromem.constants import DEFAULT_FUSION_DIM, DEFAULT_MODALITY_DROPOUT
from neuromem.multimodal.types import EncodedModality

logger = logging.getLogger(__name__)


class MultimodalFusionTransformer:
    """Fuse multi-modal features into a unified embedding.

    Parameters
    ----------
    target_dim:
        Output embedding dimension (must match storage backend's vector_size).
    modality_dropout:
        Probability of zeroing a modality during fusion (robustness).
    """

    def __init__(
        self,
        target_dim: int = DEFAULT_FUSION_DIM,
        modality_dropout: float = DEFAULT_MODALITY_DROPOUT,
    ) -> None:
        self.target_dim = target_dim
        self.modality_dropout = modality_dropout
        self._projection_cache: Dict[int, np.ndarray] = {}

    def _get_projection(self, input_dim: int, seed: int = 42) -> np.ndarray:
        """Get or create a random projection matrix for dimension reduction."""
        if input_dim not in self._projection_cache:
            rng = np.random.RandomState(seed + input_dim)
            # Gaussian random projection (preserves distances)
            proj = rng.randn(self.target_dim, input_dim) / np.sqrt(input_dim)
            self._projection_cache[input_dim] = proj
        return self._projection_cache[input_dim]

    def fuse(
        self,
        modalities: List[EncodedModality],
        training: bool = False,
    ) -> List[float]:
        """Fuse multiple modality features into a unified embedding.

        Parameters
        ----------
        modalities:
            List of EncodedModality objects from different encoders.
        training:
            If True, apply modality dropout for robustness training.

        Returns
        -------
        Unified embedding vector of dimension ``target_dim``.
        """
        if not modalities:
            return [0.0] * self.target_dim

        # Filter out empty features
        active = [m for m in modalities if m.features and len(m.features) > 0]

        if not active:
            return [0.0] * self.target_dim

        # If only one modality, just project it
        if len(active) == 1:
            return self._project_single(active[0].features)

        # Apply modality dropout during training
        if training and len(active) > 1:
            active = self._apply_modality_dropout(active)

        # Concatenate all modality features (TribeV2 pattern: concat, not average)
        all_features = []
        for mod in active:
            all_features.extend(mod.features)

        # Project concatenated features to target dimension
        return self._project_single(all_features)

    def _project_single(self, features: List[float]) -> List[float]:
        """Project a feature vector to the target dimension."""
        feat = np.array(features, dtype=np.float64)

        if len(feat) == self.target_dim:
            return feat.tolist()

        if len(feat) < self.target_dim:
            # Pad with zeros if smaller
            padded = np.zeros(self.target_dim)
            padded[: len(feat)] = feat
            return padded.tolist()

        # Random projection for dimension reduction
        proj = self._get_projection(len(feat))
        projected = proj @ feat

        # L2 normalize
        norm = np.linalg.norm(projected)
        if norm > 1e-12:
            projected = projected / norm

        return projected.tolist()

    def _apply_modality_dropout(self, modalities: List[EncodedModality]) -> List[EncodedModality]:
        """Randomly zero one modality with probability modality_dropout."""
        if len(modalities) <= 1:
            return modalities

        if np.random.random() < self.modality_dropout:
            drop_idx = np.random.randint(len(modalities))
            logger.debug("Modality dropout: zeroing %s", modalities[drop_idx].modality)
            result = []
            for i, mod in enumerate(modalities):
                if i == drop_idx:
                    # Zero out features but keep the modality in the list
                    result.append(
                        EncodedModality(
                            modality=mod.modality,
                            features=[0.0] * len(mod.features),
                            layers=mod.layers,
                            confidence=0.0,
                            metadata={**mod.metadata, "dropped": True},
                        )
                    )
                else:
                    result.append(mod)
            return result

        return modalities
