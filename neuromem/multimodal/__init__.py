"""
Multimodal encoding pipeline for NeuroMem.

Provides modality-specific encoders (text, audio, video) and a fusion
transformer inspired by TribeV2's architecture:
- Per-modality projectors with multi-layer feature concatenation
- Learned temporal smoothing (depthwise Conv1d)
- 30% modality dropout for robustness to partial input
- Per-user output heads on a shared backbone
"""

from neuromem.multimodal.types import EncodedModality, MultimodalInput
from neuromem.multimodal.errors import ModalityUnavailableError

__all__ = ["MultimodalInput", "EncodedModality", "ModalityUnavailableError"]
