"""
VAD-gated audio capture for LiveKit.

Only sends audio to the AudioEncoder when voice activity is detected,
reducing compute and noise in the memory pipeline.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class VADSampler:
    """Voice Activity Detection sampler for LiveKit audio streams.

    Buffers audio frames and only yields complete speech segments
    (from START_OF_SPEECH to END_OF_SPEECH).

    Parameters
    ----------
    on_speech_segment:
        Callback invoked with (audio_bytes, sample_rate) when a speech
        segment completes.
    vad_threshold:
        Minimum speech probability for activation (default 0.5).
    sample_rate:
        Audio sample rate in Hz (default 16000).
    """

    def __init__(
        self,
        on_speech_segment: Optional[Callable[[bytes, int], None]] = None,
        vad_threshold: float = 0.5,
        sample_rate: int = 16000,
    ) -> None:
        self.on_speech_segment = on_speech_segment
        self.vad_threshold = vad_threshold
        self.sample_rate = sample_rate
        self._buffer: bytearray = bytearray()
        self._is_speaking = False

    def on_vad_event(self, event) -> None:
        """Handle a LiveKit VAD event.

        Parameters
        ----------
        event:
            A LiveKit VADEvent with attributes:
            - type: START_OF_SPEECH | INFERENCE_DONE | END_OF_SPEECH
            - frames: list of audio frames
            - speaking: bool
        """
        if event.type.name == "START_OF_SPEECH":
            self._is_speaking = True
            self._buffer.clear()
            logger.debug("VAD: speech started")

        elif event.type.name == "INFERENCE_DONE" and self._is_speaking:
            # Accumulate audio frames during speech
            if hasattr(event, "frames") and event.frames:
                for frame in event.frames:
                    if hasattr(frame, "data"):
                        self._buffer.extend(frame.data)

        elif event.type.name == "END_OF_SPEECH":
            self._is_speaking = False
            if self._buffer and self.on_speech_segment:
                audio_bytes = bytes(self._buffer)
                self._buffer.clear()
                logger.debug("VAD: speech ended, %d bytes captured", len(audio_bytes))
                self.on_speech_segment(audio_bytes, self.sample_rate)

    def push_frame(self, frame_data: bytes) -> None:
        """Manually push an audio frame (for non-LiveKit use)."""
        if self._is_speaking:
            self._buffer.extend(frame_data)
