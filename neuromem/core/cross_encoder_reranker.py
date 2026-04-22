"""
Cross-encoder re-ranker for high-precision top-K retrieval.

Cross-encoders take (query, document) pairs as joint input and produce a
relevance score. They are MUCH more accurate than bi-encoders (the standard
sentence transformers used for vector similarity), but also slower.

This is the standard 2-stage retrieval pattern:
  Stage 1: Bi-encoder vector search retrieves top-K (fast, ~100 candidates)
  Stage 2: Cross-encoder re-ranks top-K to find the BEST matches (slower)

Used in production by Bing, Google, and most modern search systems.
"""

from __future__ import annotations

import threading
from typing import List, Tuple

from neuromem.utils.logging import get_logger

logger = get_logger(__name__)

# Default cross-encoder: L-12 has more capacity than L-6 for better precision
# on hard cases (implicit reasoning, preference matching). ~2x slower but
# significantly better recall@1 and NDCG.
DEFAULT_CROSS_ENCODER = "cross-encoder/ms-marco-MiniLM-L-12-v2"

# Lazy global model cache
_cross_encoder_models: dict = {}
_cross_encoder_lock = threading.Lock()


def _get_cross_encoder(model_name: str = DEFAULT_CROSS_ENCODER):
    """Lazily load and cache a cross-encoder model."""
    with _cross_encoder_lock:
        if model_name not in _cross_encoder_models:
            try:
                from sentence_transformers import CrossEncoder

                _cross_encoder_models[model_name] = CrossEncoder(model_name)
                logger.info(
                    "Cross-encoder loaded",
                    extra={"model": model_name},
                )
            except Exception as e:
                logger.warning(
                    "Failed to load cross-encoder",
                    extra={"model": model_name, "error": str(e)},
                )
                _cross_encoder_models[model_name] = None
        return _cross_encoder_models[model_name]


def rerank_with_cross_encoder(
    query: str,
    items_with_scores: List[Tuple[object, float]],
    top_k: int = 20,
    model_name: str = DEFAULT_CROSS_ENCODER,
    blend_weight: float = 0.7,
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

    Returns:
        Re-ranked list of (item, blended_score) tuples.
    """
    if not items_with_scores or len(items_with_scores) < 2:
        return items_with_scores

    if not query or not query.strip():
        return items_with_scores

    model = _get_cross_encoder(model_name)
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

        # Cross-encoder predict — returns raw logits (higher = more relevant)
        ce_scores = model.predict(pairs, show_progress_bar=False)

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
