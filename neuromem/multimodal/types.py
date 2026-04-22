"""
Type definitions for the multimodal encoding pipeline.

MultimodalInput is the unified input type accepted by ModalityRouter.
EncodedModality represents a single modality's encoder output before fusion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class EncodedModality:
    """Output from a single modality encoder, before fusion.

    Attributes:
        modality: Source modality name (``"text"``, ``"audio"``, ``"video"``).
        features: Raw encoder output vector.
        layers: Number of encoder layers used (for multi-depth extraction).
        timestamp: When the encoding was produced.
        confidence: Encoder's self-reported confidence (1.0 for text, may vary for ASR).
        metadata: Encoder-specific metadata (e.g., language, sample_rate).
    """

    modality: str
    features: List[float]
    layers: int = 1
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MultimodalInput:
    """Unified input container for the multimodal encoding pipeline.

    Exactly one or more modalities should be populated. The ``ModalityRouter``
    dispatches to the appropriate encoder(s) based on which fields are set.

    Attributes:
        text: Raw text content (always available in text-only mode).
        audio_bytes: Raw audio bytes (PCM/WAV from LiveKit or file).
        audio_sample_rate: Sample rate of audio_bytes (default 16000 Hz).
        video_frames: List of video frames as numpy arrays (H, W, C).
        timestamp: When this input was captured.
        source: Origin of the input (``"text"``, ``"livekit"``, ``"file"``).
        user_id: User who produced this input.
        session_id: Conversation/session identifier.
        metadata: Additional context (e.g., language, device info).
    """

    text: Optional[str] = None
    audio_bytes: Optional[bytes] = None
    audio_sample_rate: int = 16000
    video_frames: Optional[List[Any]] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "text"
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def active_modalities(self) -> List[str]:
        """Return list of modalities that have data."""
        modalities = []
        if self.text is not None:
            modalities.append("text")
        if self.audio_bytes is not None:
            modalities.append("audio")
        if self.video_frames is not None and len(self.video_frames) > 0:
            modalities.append("video")
        return modalities

    @property
    def is_multimodal(self) -> bool:
        """True if more than one modality is populated."""
        return len(self.active_modalities) > 1
