"""
Error types for the multimodal pipeline.
"""


class ModalityUnavailableError(ImportError):
    """Raised when a modality encoder's dependencies are not installed.

    Example::

        pip install neuromem[multimodal]   # for torch + transformers
        pip install neuromem[livekit]      # for livekit-agents
    """

    pass
