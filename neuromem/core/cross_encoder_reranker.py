"""
Cross-encoder re-ranker for high-precision top-K retrieval.

Cross-encoders take (query, document) pairs as joint input and produce a
relevance score. They are MUCH more accurate than bi-encoders (the standard
sentence transformers used for vector similarity), but also slower.

This is the standard 2-stage retrieval pattern:
  Stage 1: Bi-encoder vector search retrieves top-K (fast, ~100 candidates)
  Stage 2: Cross-encoder re-ranks top-K to find the BEST matches (slower)

Used in production by Bing, Google, and most modern search systems.

v0.4.0 (H1-R4): the reranker is now provider-swappable. Configure via:

    retrieval:
      reranker:
        provider: sentence-transformers   # or "cohere" | "bge" | "openai"
        model: cross-encoder/ms-marco-MiniLM-L-12-v2

The default (sentence-transformers + ms-marco-MiniLM-L-12-v2) preserves
v0.3.x behaviour exactly. ``CrossEncoderProvider`` is a Protocol — register a
custom provider via ``register_provider("name", factory_callable)`` to plug
in any reranker.

Closes Graphiti #1393 (hardcoded OpenAI reranker) — NeuroMem callers can now
A/B different rerankers without forking the SDK.
"""

from __future__ import annotations

import threading
from typing import Callable, Dict, List, Optional, Protocol, Tuple

from neuromem.utils.logging import get_logger
from neuromem.utils.providers import wrap_provider

logger = get_logger(__name__)

# Default cross-encoder: L-12 has more capacity than L-6 for better precision
# on hard cases (implicit reasoning, preference matching). ~2x slower but
# significantly better recall@1 and NDCG.
DEFAULT_CROSS_ENCODER = "cross-encoder/ms-marco-MiniLM-L-12-v2"
DEFAULT_PROVIDER = "sentence-transformers"


class CrossEncoderProvider(Protocol):
    """A pluggable cross-encoder backend.

    Implementations score ``(query, document)`` pairs and return a list of
    floats — one per pair. Higher = more relevant. Score range is
    provider-specific; ``rerank_with_cross_encoder`` min-max normalises.
    """

    def predict(self, pairs: List[Tuple[str, str]]) -> List[float]: ...


# Lazy global cache of provider instances, keyed by (provider, model)
_provider_cache: Dict[Tuple[str, str], Optional[CrossEncoderProvider]] = {}
_provider_lock = threading.Lock()
# Registry of provider name → factory(model_name) -> CrossEncoderProvider
_provider_factories: Dict[str, Callable[[str], CrossEncoderProvider]] = {}


def register_provider(
    name: str, factory: Callable[[str], CrossEncoderProvider]
) -> None:
    """Register a custom CrossEncoderProvider factory by name.

    The factory takes a model name string and returns an object implementing
    ``CrossEncoderProvider`` (i.e. a ``predict(pairs)`` method).
    """
    _provider_factories[name] = factory


# ---------------------------------------------------------------------------
# Built-in providers
# ---------------------------------------------------------------------------


class _SentenceTransformersProvider:
    """sentence-transformers ``CrossEncoder`` adapter (default, in-process)."""

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(model_name)

    @wrap_provider("sentence-transformers")
    def predict(self, pairs: List[Tuple[str, str]]) -> List[float]:
        return [float(s) for s in self._model.predict(pairs, show_progress_bar=False)]


class _BGEProvider(_SentenceTransformersProvider):
    """BAAI BGE cross-encoder family (e.g. ``BAAI/bge-reranker-large``).

    Same wire format as sentence-transformers (BGE rerankers are distributed
    via HuggingFace + sentence-transformers loading), so the implementation
    is shared.
    """


class _CohereProvider:
    """Cohere ``rerank`` API adapter. Requires ``cohere`` extra + API key."""

    def __init__(self, model_name: str) -> None:
        import cohere
        import os

        api_key = os.environ.get("COHERE_API_KEY")
        if not api_key:
            raise RuntimeError("COHERE_API_KEY env var is required for Cohere reranker")
        self._client = cohere.Client(api_key)
        self._model_name = model_name

    @wrap_provider("cohere")
    def predict(self, pairs: List[Tuple[str, str]]) -> List[float]:
        if not pairs:
            return []
        # Cohere's rerank API is keyed by query. NeuroMem batches a single
        # query against many docs per call, so per-query rerank is the right
        # shape. Group pairs by query (almost always one query per call).
        queries: Dict[str, List[int]] = {}
        for i, (q, _) in enumerate(pairs):
            queries.setdefault(q, []).append(i)
        scores = [0.0] * len(pairs)
        for query, indices in queries.items():
            documents = [pairs[i][1] for i in indices]
            resp = self._client.rerank(
                query=query, documents=documents, model=self._model_name
            )
            for r in resp.results:
                scores[indices[r.index]] = float(r.relevance_score)
        return scores


class _OpenAIProvider:
    """Placeholder for OpenAI's ``rerank-N`` API.

    OpenAI announced a managed reranker in late 2025 (see
    ``research/01-sota-landscape.md``). Wire it once GA — for now this raises
    a clear ProviderError instead of silently 404-ing.
    """

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name

    @wrap_provider("openai")
    def predict(self, pairs: List[Tuple[str, str]]) -> List[float]:
        raise NotImplementedError(
            "OpenAI rerank provider is not yet wired in NeuroMem v0.4.0; "
            "use 'sentence-transformers', 'bge', or 'cohere'. Track v0.5.0."
        )


# Register built-ins
register_provider("sentence-transformers", lambda m: _SentenceTransformersProvider(m))
register_provider("bge", lambda m: _BGEProvider(m))
register_provider("cohere", lambda m: _CohereProvider(m))
register_provider("openai", lambda m: _OpenAIProvider(m))


def _get_cross_encoder(
    model_name: str = DEFAULT_CROSS_ENCODER,
    provider: str = DEFAULT_PROVIDER,
) -> Optional[CrossEncoderProvider]:
    """Lazily load and cache a cross-encoder model via the named provider."""
    cache_key = (provider, model_name)
    with _provider_lock:
        if cache_key not in _provider_cache:
            factory = _provider_factories.get(provider)
            if factory is None:
                logger.warning(
                    "Unknown cross-encoder provider, falling back to default",
                    extra={"requested": provider, "default": DEFAULT_PROVIDER},
                )
                factory = _provider_factories[DEFAULT_PROVIDER]
            try:
                _provider_cache[cache_key] = factory(model_name)
                logger.info(
                    "Cross-encoder loaded",
                    extra={"provider": provider, "model": model_name},
                )
            except Exception as e:
                logger.warning(
                    "Failed to load cross-encoder",
                    extra={
                        "provider": provider,
                        "model": model_name,
                        "error": str(e),
                    },
                )
                _provider_cache[cache_key] = None
        return _provider_cache[cache_key]


def rerank_with_cross_encoder(
    query: str,
    items_with_scores: List[Tuple[object, float]],
    top_k: int = 20,
    model_name: str = DEFAULT_CROSS_ENCODER,
    blend_weight: float = 0.7,
    provider: str = DEFAULT_PROVIDER,
) -> List[Tuple[object, float]]:
    """
    Re-rank top-K items using a cross-encoder.

    Args:
        query: The query text.
        items_with_scores: List of (item, similarity_score) tuples to re-rank.
        top_k: Number of top items to re-rank (use cross-encoder on these only).
        model_name: Cross-encoder model name.
        blend_weight: Weight for cross-encoder score in the final blend
                      (0.0 = use only original, 1.0 = use only cross-encoder).
        provider: Reranker provider name. Defaults to ``sentence-transformers``.
                  See ``register_provider`` for plugging in custom backends.

    Returns:
        Re-ranked list of (item, blended_score) tuples.
    """
    if not items_with_scores or len(items_with_scores) < 2:
        return items_with_scores

    if not query or not query.strip():
        return items_with_scores

    model = _get_cross_encoder(model_name, provider)
    if model is None:
        return items_with_scores

    # Take top-K for re-ranking; pass others through
    head = items_with_scores[:top_k]
    tail = items_with_scores[top_k:]

    try:
        # Build (query, doc) pairs with cleaned content.
        # The cognitive pipeline wraps content as:
        #   "User: <actual content>\nAssistant: Memory stored."
        # This confuses CE (trained on web search, not chat wrapping).
        # Strip the noise so CE scores on actual content.
        def _clean_for_ce(content: str) -> str:
            if "\nAssistant: Memory stored." in content:
                content = content.split("\nAssistant: Memory stored.")[0]
            if content.startswith("User: "):
                content = content[6:]
            return content.strip()

        pairs = [(query, _clean_for_ce(getattr(item, "content", ""))) for item, _ in head]

        # Provider predict — returns raw scores (higher = more relevant)
        ce_scores = model.predict(pairs)

        # Normalize cross-encoder scores to [0, 1] using min-max
        if len(ce_scores) > 0:
            ce_min = float(min(ce_scores))
            ce_max = float(max(ce_scores))
            ce_range = ce_max - ce_min if ce_max > ce_min else 1.0
            ce_normalized = [(float(s) - ce_min) / ce_range for s in ce_scores]
        else:
            ce_normalized = []

        # Blend cross-encoder with original similarity
        reranked = [
            (item, blend_weight * ce_normalized[i] + (1 - blend_weight) * orig_sim)
            for i, (item, orig_sim) in enumerate(head)
        ]
        reranked.sort(key=lambda x: x[1], reverse=True)

        return reranked + tail

    except Exception as e:
        logger.warning(
            "Cross-encoder re-ranking failed, returning original order",
            extra={"error": str(e)},
        )
        return items_with_scores
