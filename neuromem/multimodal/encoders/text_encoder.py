"""
Text Encoder — wraps existing get_embedding() with zero changes.

This is the default modality encoder. It produces a single-layer feature
vector using the configured embedding model (text-embedding-3-large by default).
"""

from __future__ import annotations


from neuromem.multimodal.types import EncodedModality
from neuromem.utils.embeddings import get_embedding


class TextEncoder:
    """Text modality encoder using the existing embedding pipeline.

    Parameters
    ----------
    model:
        Embedding model name (default: text-embedding-3-large).
    """

    def __init__(self, model: str = "text-embedding-3-large") -> None:
        self.model = model

    def encode(self, text: str) -> EncodedModality:
        """Encode text content into a feature vector.

        Parameters
        ----------
        text:
            Raw text string.

        Returns
        -------
        EncodedModality with features from the text embedding model.
        """
        features = get_embedding(text, self.model)
        return EncodedModality(
            modality="text",
            features=features,
            layers=1,
            confidence=1.0,
            metadata={"model": self.model, "text_length": len(text)},
        )
