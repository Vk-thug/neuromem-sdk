"""
Video frame sampler for LiveKit.

Captures video frames at a configurable rate (default 2Hz, matching TribeV2)
and yields batches to the VideoEncoder.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, List, Optional

logger = logging.getLogger(__name__)


class VideoFrameSampler:
    """Sample video frames at a fixed rate for encoding.

    Parameters
    ----------
    sample_hz:
        Target frame rate in Hz (default 2).
    batch_size:
        Number of frames to accumulate before yielding a batch (default 5).
    on_frame_batch:
        Callback invoked with a list of frames when a batch is ready.
    """

    def __init__(
        self,
        sample_hz: int = 2,
        batch_size: int = 5,
        on_frame_batch: Optional[Callable[[List[Any]], None]] = None,
    ) -> None:
        self.sample_hz = sample_hz
        self.batch_size = batch_size
        self.on_frame_batch = on_frame_batch
        self._interval = 1.0 / sample_hz
        self._last_sample_time = 0.0
        self._buffer: List[Any] = []

    def push_frame(self, frame: Any) -> None:
        """Push a video frame, sampling at the configured rate.

        Parameters
        ----------
        frame:
            Video frame (numpy array or PIL Image). Only sampled if
            enough time has passed since the last sample.
        """
        now = time.monotonic()
        if now - self._last_sample_time < self._interval:
            return  # Skip frame — not time for next sample yet

        self._last_sample_time = now
        self._buffer.append(frame)

        if len(self._buffer) >= self.batch_size:
            batch = self._buffer[:]
            self._buffer.clear()
            logger.debug("VideoFrameSampler: yielding batch of %d frames", len(batch))
            if self.on_frame_batch:
                self.on_frame_batch(batch)

    def flush(self) -> Optional[List[Any]]:
        """Flush remaining buffered frames."""
        if self._buffer:
            batch = self._buffer[:]
            self._buffer.clear()
            if self.on_frame_batch:
                self.on_frame_batch(batch)
            return batch
        return None
