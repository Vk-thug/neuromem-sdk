"""
Modality-specific encoders.

- TextEncoder: wraps existing get_embedding() (no new dependencies)
- AudioEncoder: Whisper STT + wav2vec2 features (requires torch + transformers)
- VideoEncoder: DINOv2 frame features (requires torch + transformers)
"""
