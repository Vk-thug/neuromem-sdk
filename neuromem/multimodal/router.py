"""
Modality Router — dispatches MultimodalInput to appropriate encoders.

This is the top-level entry point for multimodal encoding.
It replaces get_embedding() when multimodal is enabled, while
maintaining full backward compatibility (encode_text() is a
drop-in shim for the existing pipeline).
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from neuromem.multimodal.encoders.text_encoder import TextEncoder
from neuromem.multimodal.fusion.multimodal_fusion import MultimodalFusionTransformer
from neuromem.multimodal.types import EncodedModality, MultimodalInput

logger = logging.getLogger(__name__)


class ModalityRouter:
    """Route multimodal input to per-modality encoders and fuse.

    Parameters
    ----------
    config:
        Multimodal config dict (from ``NeuroMemConfig.multimodal()``).
    """

    def __init__(self, config: Optional[Dict] = None) -> None:
        cfg = config or {}

        # Text encoder (always available)
        text_cfg = cfg.get("text", {})
        self.text_encoder = TextEncoder(model=text_cfg.get("model", "text-embedding-3-large"))

        # Audio encoder (optional)
        self.audio_encoder = None
        audio_cfg = cfg.get("audio", {})
        if audio_cfg.get("enabled", False):
            try:
                from neuromem.multimodal.encoders.audio_encoder import AudioEncoder

                self.audio_encoder = AudioEncoder(
                    model=audio_cfg.get("model", "wav2vec2-base-960h"),
                    text_fallback_model=text_cfg.get("model", "text-embedding-3-large"),
                    mode=audio_cfg.get("mode", "transcription"),
                )
            except Exception:
                logger.warning("AudioEncoder init failed, audio encoding disabled")

        # Video encoder (optional)
        self.video_encoder = None
        video_cfg = cfg.get("video", {})
        if video_cfg.get("enabled", False):
            try:
                from neuromem.multimodal.encoders.video_encoder import VideoEncoder

                self.video_encoder = VideoEncoder(
                    model=video_cfg.get("model", "dinov2-base"),
                    sample_hz=video_cfg.get("sample_hz", 2),
                    text_fallback_model=text_cfg.get("model", "text-embedding-3-large"),
                )
            except Exception:
                logger.warning("VideoEncoder init failed, video encoding disabled")

        # Fusion transformer
        self.fusion = MultimodalFusionTransformer(
            target_dim=cfg.get("fusion_dim", 1536),
            modality_dropout=cfg.get("modality_dropout", 0.3),
        )

    def encode(self, inp: MultimodalInput) -> List[float]:
        """Route multimodal input to encoders and fuse into unified embedding.

        Parameters
        ----------
        inp:
            MultimodalInput with one or more modalities populated.

        Returns
        -------
        Unified embedding vector (drop-in compatible with MemoryItem.embedding).
        """
        encoded_modalities: List[EncodedModality] = []

        # Text
        if inp.text:
            encoded_modalities.append(self.text_encoder.encode(inp.text))

        # Audio
        if inp.audio_bytes and self.audio_encoder:
            try:
                encoded_modalities.append(
                    self.audio_encoder.encode(inp.audio_bytes, inp.audio_sample_rate)
                )
            except Exception:
                logger.warning("Audio encoding failed, skipping", exc_info=True)

        # Video
        if inp.video_frames and self.video_encoder:
            try:
                encoded_modalities.append(self.video_encoder.encode(inp.video_frames))
            except Exception:
                logger.warning("Video encoding failed, skipping", exc_info=True)

        if not encoded_modalities:
            logger.warning("No modalities encoded, returning zero vector")
            return [0.0] * self.fusion.target_dim

        # If only text, bypass fusion (preserve original embedding quality)
        if len(encoded_modalities) == 1 and encoded_modalities[0].modality == "text":
            return encoded_modalities[0].features

        # Multi-modal fusion
        return self.fusion.fuse(encoded_modalities, training=False)

    def encode_text(self, text: str) -> List[float]:
        """Backward-compatible shim — encodes text-only input.

        This is a drop-in replacement for ``get_embedding(text, model)``.
        """
        return self.text_encoder.encode(text).features
