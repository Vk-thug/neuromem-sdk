"""
LLM-based final re-ranker for the highest-precision top-K.

When a cross-encoder isn't enough (e.g., for queries requiring REASONING
about implicit connections, preferences, or nuanced semantic links), an
LLM can directly evaluate which candidate best matches the query intent.

This is the most expensive re-ranking step, used as a final pass on the
top-N (typically 5-10) candidates from the cross-encoder. Batched into a
SINGLE LLM call per query to keep latency manageable.

Cached so repeated benchmark queries are fast.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from neuromem.utils.logging import get_logger

logger = get_logger(__name__)

# Persistent cache for LLM re-rank decisions
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "neuromem" / "llm_rerank"
_rerank_cache_lock = threading.Lock()
_rerank_in_memory_cache: Dict[str, List[int]] = {}


RERANK_PROMPT_TEMPLATE = """You are searching a conversation history to find which past statement is most RELEVANT to the user's current query.

IMPORTANT: The best answer is usually a past statement from the USER's OWN VOICE that contains the factual or preference information needed. It may NOT look like a direct answer — it's the user sharing their own experience, preference, or situation that indirectly relates to the query.

QUERY: {query}

CANDIDATE PAST STATEMENTS:
{passages}

Rank candidates by which one best contains the information needed to answer the query. Prefer user statements over assistant suggestions when relevant.

Output ONLY a comma-separated list from most to least relevant.
Example: 3,1,5,2,4

Ranking:"""


def _cache_key(query: str, passage_texts: List[str], model: str) -> str:
    """Stable cache key for query+passages+model."""
    content = f"{model}::{query}::" + "|".join(p[:200] for p in passage_texts)
    return hashlib.sha256(content.encode()).hexdigest()[:24]


def _get_cached(
    query: str, passages: List[str], model: str, cache_dir: Path
) -> Optional[List[int]]:
    """Look up cached rank order."""
    key = _cache_key(query, passages, model)
    with _rerank_cache_lock:
        if key in _rerank_in_memory_cache:
            return _rerank_in_memory_cache[key]

    cache_file = cache_dir / f"{key}.json"
    if cache_file.exists():
        try:
            with open(cache_file) as f:
                data = json.load(f)
            ranking = data.get("ranking", [])
            with _rerank_cache_lock:
                _rerank_in_memory_cache[key] = ranking
            return ranking
        except Exception:
            return None
    return None


def _save_cache(
    query: str,
    passages: List[str],
    model: str,
    ranking: List[int],
    cache_dir: Path,
) -> None:
    """Save rank order to cache."""
    key = _cache_key(query, passages, model)
    with _rerank_cache_lock:
        _rerank_in_memory_cache[key] = ranking

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{key}.json"
        with open(cache_file, "w") as f:
            json.dump({"ranking": ranking}, f)
    except Exception as e:
        logger.debug("Failed to save rerank cache", extra={"error": str(e)})


def _parse_ranking(text: str, n: int) -> List[int]:
    """
    Parse a comma-separated list of integers from LLM output.

    Returns 0-indexed positions. If parsing fails or is incomplete,
    fills missing positions in original order.
    """
    # Find the longest numeric sequence
    matches = re.findall(r"\d+", text)
    seen = set()
    parsed: List[int] = []
    for m in matches:
        idx = int(m) - 1  # Convert to 0-indexed
        if 0 <= idx < n and idx not in seen:
            parsed.append(idx)
            seen.add(idx)

    # Fill in any missing positions
    for i in range(n):
        if i not in seen:
            parsed.append(i)

    return parsed[:n]


def llm_rerank(
    query: str,
    items_with_scores: List[Tuple[object, float]],
    top_k: int = 5,
    model: str = "qwen2.5-coder:7b",
    provider: str = "ollama",
    ollama_base_url: str = "http://localhost:11434",
    cache_dir: Path = DEFAULT_CACHE_DIR,
    use_cache: bool = True,
    max_passage_chars: int = 300,
    blend_weight: float = 0.5,
) -> List[Tuple[object, float]]:
    """
    Re-rank top-K items using an LLM in a single batch call.

    Blends LLM rank-based scores with the input scores using blend_weight:
        final_score = blend_weight * llm_score + (1 - blend_weight) * original_score

    blend_weight=1.0 fully trusts the LLM; 0.0 keeps the original order.
    0.5 (default) lets strong original signals (like high cross-encoder
    scores) survive LLM reordering when the LLM is uncertain.

    Args:
        query: The original query text.
        items_with_scores: List of (item, score) tuples from previous ranking.
        top_k: Number of top items to re-rank with the LLM.
        model: LLM model name.
        provider: LLM provider.
        cache_dir: Persistent cache location.
        use_cache: Use the persistent cache.
        max_passage_chars: Truncate each passage to this length to fit in prompt.
        blend_weight: Weight for LLM score in the final blend (0-1).

    Returns:
        Re-ranked list (top_k LLM-ranked items first, then the rest).
    """
    if not items_with_scores or len(items_with_scores) < 2:
        return items_with_scores
    if not query or not query.strip():
        return items_with_scores

    head = items_with_scores[:top_k]
    tail = items_with_scores[top_k:]

    passages = [getattr(item, "content", "")[:max_passage_chars] for item, _ in head]

    def _blend_and_sort(head_items, ranking):
        """Blend LLM rank-based score with original score, then sort."""
        # LLM score decreases by position in ranking: position 0 → 1.0, 1 → 0.8, 2 → 0.6 etc
        llm_scores = [0.0] * len(head_items)
        n = len(ranking)
        for pos, orig_idx in enumerate(ranking):
            if 0 <= orig_idx < len(llm_scores):
                llm_scores[orig_idx] = max(0.0, 1.0 - (pos / max(n - 1, 1)))

        blended = [
            (
                item,
                blend_weight * llm_scores[i] + (1 - blend_weight) * orig_score,
            )
            for i, (item, orig_score) in enumerate(head_items)
        ]
        blended.sort(key=lambda x: x[1], reverse=True)
        return blended

    # Check cache first
    if use_cache:
        cached_ranking = _get_cached(query, passages, model, cache_dir)
        if cached_ranking is not None:
            try:
                blended = _blend_and_sort(head, cached_ranking)
                return blended + tail
            except (IndexError, ValueError):
                pass

    # Build prompt
    passage_block = "\n".join(f"{i + 1}: {p}" for i, p in enumerate(passages))
    prompt = RERANK_PROMPT_TEMPLATE.format(query=query, passages=passage_block)

    try:
        if provider == "ollama":
            import ollama

            client = ollama.Client(host=ollama_base_url)
            response = client.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "num_predict": 30,
                    "temperature": 0.0,
                },
            )
            output = response["message"]["content"].strip()
        elif provider == "openai":
            import openai

            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=30,
            )
            output = response.choices[0].message.content.strip()
        else:
            return items_with_scores

        ranking = _parse_ranking(output, len(head))

        if use_cache:
            _save_cache(query, passages, model, ranking, cache_dir)

        blended = _blend_and_sort(head, ranking)
        return blended + tail

    except Exception as e:
        logger.warning(
            "LLM re-rank failed, returning original order",
            extra={"error": str(e)[:200]},
        )
        return items_with_scores
