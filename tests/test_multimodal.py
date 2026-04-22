"""
Tests for the multimodal encoding pipeline (v0.3.0).

Tests encoders, fusion, router, and LiveKit bridge components.
All tests use mock data — no torch or LiveKit dependencies required.
"""

import pytest
import numpy as np

from neuromem.multimodal.types import MultimodalInput, EncodedModality
from neuromem.multimodal.errors import ModalityUnavailableError
from neuromem.multimodal.fusion.multimodal_fusion import MultimodalFusionTransformer
from neuromem.multimodal.router import ModalityRouter
from neuromem.multimodal.livekit.vad_sampler import VADSampler
from neuromem.multimodal.livekit.frame_sampler import VideoFrameSampler


# ── MultimodalInput Type ──


class TestMultimodalInput:
    def test_text_only(self):
        inp = MultimodalInput(text="hello")
        assert inp.active_modalities == ["text"]
        assert not inp.is_multimodal

    def test_multimodal(self):
        inp = MultimodalInput(text="hello", audio_bytes=b"data")
        assert set(inp.active_modalities) == {"text", "audio"}
        assert inp.is_multimodal

    def test_all_modalities(self):
        inp = MultimodalInput(text="x", audio_bytes=b"y", video_frames=[1, 2])
        assert len(inp.active_modalities) == 3

    def test_empty_video_not_counted(self):
        inp = MultimodalInput(text="x", video_frames=[])
        assert inp.active_modalities == ["text"]

    def test_source_default(self):
        inp = MultimodalInput()
        assert inp.source == "text"


# ── EncodedModality Type ──


class TestEncodedModality:
    def test_frozen(self):
        em = EncodedModality(modality="text", features=[0.1, 0.2])
        with pytest.raises(AttributeError):
            em.modality = "audio"

    def test_defaults(self):
        em = EncodedModality(modality="audio", features=[])
        assert em.layers == 1
        assert em.confidence == 1.0


# ── Multimodal Fusion ──


class TestMultimodalFusionTransformer:
    def test_single_modality_projects(self):
        ft = MultimodalFusionTransformer(target_dim=16)
        text_mod = EncodedModality(modality="text", features=np.random.randn(32).tolist())
        result = ft.fuse([text_mod])
        assert len(result) == 16

    def test_multi_modality_concatenates(self):
        ft = MultimodalFusionTransformer(target_dim=16)
        text_mod = EncodedModality(modality="text", features=np.random.randn(20).tolist())
        audio_mod = EncodedModality(modality="audio", features=np.random.randn(12).tolist())
        result = ft.fuse([text_mod, audio_mod])
        assert len(result) == 16

    def test_empty_input(self):
        ft = MultimodalFusionTransformer(target_dim=8)
        result = ft.fuse([])
        assert result == [0.0] * 8

    def test_exact_dim_passthrough(self):
        ft = MultimodalFusionTransformer(target_dim=10)
        mod = EncodedModality(modality="text", features=list(range(10)))
        result = ft.fuse([mod])
        assert result == list(range(10))

    def test_modality_dropout(self):
        ft = MultimodalFusionTransformer(target_dim=16, modality_dropout=1.0)
        mods = [
            EncodedModality(modality="text", features=np.random.randn(8).tolist()),
            EncodedModality(modality="audio", features=np.random.randn(8).tolist()),
        ]
        np.random.seed(42)
        result = ft.fuse(mods, training=True)
        assert len(result) == 16

    def test_l2_normalized(self):
        ft = MultimodalFusionTransformer(target_dim=16)
        mod = EncodedModality(modality="text", features=np.random.randn(64).tolist())
        result = ft.fuse([mod])
        norm = np.linalg.norm(result)
        assert abs(norm - 1.0) < 0.01  # Should be unit-normalized


# ── Modality Router ──


class TestModalityRouter:
    def test_text_only_bypass_fusion(self):
        router = ModalityRouter(config={"text": {"model": "text-embedding-3-large"}})
        inp = MultimodalInput(text="hello world")
        result = router.encode(inp)
        assert len(result) > 0

    def test_encode_text_shim(self):
        router = ModalityRouter()
        emb1 = router.encode_text("test")
        emb2 = router.encode(MultimodalInput(text="test"))
        assert emb1 == emb2

    def test_no_modality_returns_zeros(self):
        router = ModalityRouter()
        inp = MultimodalInput()  # nothing populated
        result = router.encode(inp)
        assert all(x == 0.0 for x in result)


# ── VAD Sampler ──


class TestVADSampler:
    def test_captures_speech_segment(self):
        captured = []
        vad = VADSampler(on_speech_segment=lambda b, sr: captured.append(b))

        class MockEvent:
            def __init__(self, name, frames=None):
                self.type = type("T", (), {"name": name})()
                self.frames = frames or []

        vad.on_vad_event(MockEvent("START_OF_SPEECH"))
        vad.push_frame(b"audio_data_1")
        vad.push_frame(b"audio_data_2")
        vad.on_vad_event(MockEvent("END_OF_SPEECH"))

        assert len(captured) == 1
        assert b"audio_data_1" in captured[0]
        assert b"audio_data_2" in captured[0]

    def test_no_capture_outside_speech(self):
        captured = []
        vad = VADSampler(on_speech_segment=lambda b, sr: captured.append(b))
        vad.push_frame(b"noise")
        assert len(captured) == 0


# ── Video Frame Sampler ──


class TestVideoFrameSampler:
    def test_batch_callback(self):
        batches = []
        fs = VideoFrameSampler(
            sample_hz=1000,
            batch_size=3,
            on_frame_batch=lambda b: batches.append(len(b)),
        )
        # Force reset interval so all frames are sampled
        for i in range(6):
            fs._last_sample_time = 0  # reset so every frame passes
            fs.push_frame(f"frame_{i}")
        assert len(batches) == 2  # 6 frames / 3 batch_size

    def test_flush(self):
        batches = []
        fs = VideoFrameSampler(
            sample_hz=1000,
            batch_size=10,
            on_frame_batch=lambda b: batches.append(len(b)),
        )
        fs._last_sample_time = 0
        fs.push_frame("f1")
        fs._last_sample_time = 0
        fs.push_frame("f2")
        result = fs.flush()
        assert result is not None
        assert len(result) == 2


# ── LiveKit Session Bridge ──


class TestLiveKitSessionBridge:
    def test_loads_without_livekit(self):
        from neuromem.multimodal.livekit.session_bridge import LiveKitSessionBridge

        bridge = LiveKitSessionBridge(neuromem=None)
        assert bridge._lk_available is False

    def test_connect_raises_without_livekit(self):
        import asyncio
        from neuromem.multimodal.livekit.session_bridge import LiveKitSessionBridge

        bridge = LiveKitSessionBridge(neuromem=None)
        with pytest.raises(ModalityUnavailableError):
            asyncio.get_event_loop().run_until_complete(bridge.connect(None))


# ── ModalityUnavailableError ──


class TestModalityUnavailableError:
    def test_is_import_error(self):
        assert issubclass(ModalityUnavailableError, ImportError)

    def test_catchable_as_import_error(self):
        with pytest.raises(ImportError):
            raise ModalityUnavailableError("test")
