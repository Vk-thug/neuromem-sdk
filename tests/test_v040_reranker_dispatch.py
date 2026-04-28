"""
Tests for v0.4.0 H1-R4: swappable reranker provider dispatch.
"""

from __future__ import annotations

from typing import List, Tuple

import pytest

from neuromem.core import cross_encoder_reranker as cer
from neuromem.core.cross_encoder_reranker import (
    DEFAULT_PROVIDER,
    rerank_with_cross_encoder,
    register_provider,
)


class _StubProvider:
    """Always scores docs by their length — deterministic and simple."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def predict(self, pairs: List[Tuple[str, str]]) -> List[float]:
        return [float(len(doc)) for _, doc in pairs]


@pytest.fixture(autouse=True)
def _clear_provider_cache():
    cer._provider_cache.clear()
    yield
    cer._provider_cache.clear()


class _Item:
    def __init__(self, content: str) -> None:
        self.content = content


class TestProviderDispatch:
    def test_default_provider_string_is_sentence_transformers(self):
        assert DEFAULT_PROVIDER == "sentence-transformers"

    def test_register_and_use_custom_provider(self):
        register_provider("stub-test", lambda m: _StubProvider(m))

        items = [(_Item("short"), 0.5), (_Item("a much longer document"), 0.5)]
        out = rerank_with_cross_encoder(
            query="anything",
            items_with_scores=items,
            top_k=2,
            blend_weight=1.0,  # use only stub scores
            model_name="any-model",
            provider="stub-test",
        )
        # Length-based scoring puts the long doc first.
        assert out[0][0].content == "a much longer document"
        assert out[1][0].content == "short"

    def test_unknown_provider_falls_back_silently(self):
        # An unregistered provider should not raise — it falls back to default.
        # We don't actually load the default model in tests (no internet);
        # instead, set the default to our stub for the duration of this test.
        original = cer._provider_factories[DEFAULT_PROVIDER]
        cer._provider_factories[DEFAULT_PROVIDER] = lambda m: _StubProvider(m)
        try:
            items = [(_Item("a"), 0.5), (_Item("ab"), 0.5)]
            out = rerank_with_cross_encoder(
                query="anything",
                items_with_scores=items,
                top_k=2,
                blend_weight=1.0,
                model_name="any-model",
                provider="totally-not-registered",
            )
            assert out[0][0].content == "ab"
        finally:
            cer._provider_factories[DEFAULT_PROVIDER] = original


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
