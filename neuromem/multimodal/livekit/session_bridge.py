"""
LiveKit Session Bridge — connects LiveKit AgentSession to NeuroMem.

All LiveKit imports are lazy — this module loads without livekit-agents installed.
Raises ModalityUnavailableError on instantiation if livekit is missing.

Usage::

    from neuromem import NeuroMem
    from neuromem.multimodal.livekit.session_bridge import LiveKitSessionBridge

    memory = NeuroMem.for_livekit(user_id="user_123")

    async with LiveKitSessionBridge(memory) as bridge:
        await bridge.connect(session)  # LiveKit AgentSession
        # Bridge auto-hooks:
        #   on_user_input_transcribed → memory.observe()
        #   video frames → memory.observe_multimodal()
"""

from __future__ import annotations

import logging
from typing import Any

from neuromem.multimodal.errors import ModalityUnavailableError
from neuromem.multimodal.livekit.frame_sampler import VideoFrameSampler
from neuromem.multimodal.livekit.vad_sampler import VADSampler

logger = logging.getLogger(__name__)


class LiveKitSessionBridge:
    """Bridge between LiveKit AgentSession and NeuroMem memory system.

    Parameters
    ----------
    neuromem:
        NeuroMem instance to store memories into.
    video_sample_hz:
        Video frame sampling rate (default 2Hz, TribeV2 pattern).
    vad_threshold:
        VAD activation threshold (default 0.5).
    auto_observe:
        If True, automatically store transcribed utterances as memories.
    """

    def __init__(
        self,
        neuromem: Any,
        video_sample_hz: int = 2,
        vad_threshold: float = 0.5,
        auto_observe: bool = True,
    ) -> None:
        # Lazy import check
        try:
            import livekit.agents  # noqa: F401

            self._lk_available = True
        except ImportError:
            self._lk_available = False

        self.neuromem = neuromem
        self.auto_observe = auto_observe
        self._session = None

        # Initialize samplers
        self.vad_sampler = VADSampler(
            on_speech_segment=self._on_speech_segment,
            vad_threshold=vad_threshold,
        )
        self.video_sampler = VideoFrameSampler(
            sample_hz=video_sample_hz,
            on_frame_batch=self._on_video_batch,
        )

    async def connect(self, session: Any) -> None:
        """Connect to a LiveKit AgentSession and register event handlers.

        Parameters
        ----------
        session:
            A LiveKit ``AgentSession`` instance.

        Raises
        ------
        ModalityUnavailableError:
            If livekit-agents is not installed.
        """
        if not self._lk_available:
            raise ModalityUnavailableError(
                "LiveKit not installed. Run: pip install neuromem[livekit]"
            )

        self._session = session

        # Register event handlers
        @session.on("user_input_transcribed")
        def on_transcript(ev: Any) -> None:
            if ev.is_final and self.auto_observe:
                transcript = ev.transcript if hasattr(ev, "transcript") else str(ev)
                logger.debug("LiveKit transcript: %s", transcript[:100])
                try:
                    self.neuromem.observe(
                        user_input=transcript,
                        assistant_output="[awaiting response]",
                    )
                except Exception:
                    logger.warning("Failed to observe transcript", exc_info=True)

        @session.on("conversation_item_added")
        def on_item(ev: Any) -> None:
            # Sync conversation items to memory
            if hasattr(ev, "item") and hasattr(ev.item, "text_content"):
                role = getattr(ev.item, "role", "unknown")
                text = ev.item.text_content or ""
                if role == "assistant" and text:
                    logger.debug("LiveKit assistant response: %s", text[:100])

        logger.info("LiveKitSessionBridge connected to session")

    def _on_speech_segment(self, audio_bytes: bytes, sample_rate: int) -> None:
        """Handle a complete speech segment from VAD."""
        if not self.auto_observe:
            return
        try:
            self.neuromem.observe_multimodal(
                audio_bytes=audio_bytes,
                assistant_output="[processing audio]",
                source="livekit",
            )
        except Exception:
            logger.warning("Failed to observe audio segment", exc_info=True)

    def _on_video_batch(self, frames: list) -> None:
        """Handle a batch of video frames from the frame sampler."""
        if not self.auto_observe:
            return
        try:
            self.neuromem.observe_multimodal(
                video_frames=frames,
                assistant_output="[processing video]",
                source="livekit",
            )
        except Exception:
            logger.warning("Failed to observe video batch", exc_info=True)

    async def disconnect(self) -> None:
        """Flush samplers and disconnect."""
        self.video_sampler.flush()
        self._session = None
        logger.info("LiveKitSessionBridge disconnected")

    async def __aenter__(self) -> LiveKitSessionBridge:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()
