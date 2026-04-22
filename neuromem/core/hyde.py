"""
HyDE (Hypothetical Document Embeddings) for semantic retrieval.

When a query and the answer document don't share keywords or surface vocabulary,
direct embedding similarity fails. HyDE solves this by:

1. Asking an LLM to generate a HYPOTHETICAL answer to the query
2. Embedding the hypothetical answer (instead of the raw query)
3. Using that embedding to retrieve similar REAL documents

The hypothetical answer naturally uses vocabulary similar to actual answers,
bridging the semantic gap. Originally proposed in Gao et al. (2022)
"Precise Zero-Shot Dense Retrieval without Relevance Labels".

For benchmark mode, we cache HyDE results since queries are deterministic.
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Dict, List, Optional

from neuromem.utils.logging import get_logger

logger = get_logger(__name__)

# Persistent cache to avoid re-generating for repeated benchmark queries
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "neuromem" / "hyde"
_hyde_cache_lock = threading.Lock()
_hyde_in_memory_cache: Dict[str, str] = {}


HYDE_PROMPT_TEMPLATE = """Imagine the user asking the question below has previously made statements in their conversation history that contain the answer. Write 2-3 short sentences in the USER'S VOICE that they might have said earlier. Include both factual statements AND emotional/preference statements. Use everyday vocabulary, not formal answer language.

Question: {question}

User's likely past statements (in their own voice, 2-3 short sentences):"""


def _cache_key(query: str, model: str) -> str:
    """Stable cache key for a query+model pair."""
    return hashlib.sha256(f"{model}::{query}".encode()).hexdigest()[:24]


def _get_cached(query: str, model: str, cache_dir: Path) -> Optional[str]:
    """Look up cached hypothetical answer (memory + disk)."""
    key = _cache_key(query, model)
    with _hyde_cache_lock:
        if key in _hyde_in_memory_cache:
            return _hyde_in_memory_cache[key]

    cache_file = cache_dir / f"{key}.json"
    if cache_file.exists():
        try:
            with open(cache_file) as f:
                data = json.load(f)
            answer = data.get("answer", "")
            with _hyde_cache_lock:
                _hyde_in_memory_cache[key] = answer
            return answer
        except Exception:
            return None
    return None


def _save_cache(query: str, model: str, answer: str, cache_dir: Path) -> None:
    """Save hypothetical answer to cache."""
    key = _cache_key(query, model)
    with _hyde_cache_lock:
        _hyde_in_memory_cache[key] = answer

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{key}.json"
        with open(cache_file, "w") as f:
            json.dump({"query": query, "model": model, "answer": answer}, f)
    except Exception as e:
        logger.debug("Failed to save HyDE cache", extra={"error": str(e)})


def generate_hypothetical_answer(
    query: str,
    model: str = "qwen2.5-coder:7b",
    provider: str = "ollama",
    ollama_base_url: str = "http://localhost:11434",
    cache_dir: Path = DEFAULT_CACHE_DIR,
    use_cache: bool = True,
    max_tokens: int = 80,
) -> str:
    """
    Generate a hypothetical answer for a query using an LLM.

    Returns the hypothetical answer text. On failure, returns the original
    query (fallback to standard retrieval).
    """
    if not query or not query.strip():
        return query

    # Check cache first
    if use_cache:
        cached = _get_cached(query, model, cache_dir)
        if cached is not None:
            return cached

    prompt = HYDE_PROMPT_TEMPLATE.format(question=query)

    try:
        if provider == "ollama":
            import ollama

            client = ollama.Client(host=ollama_base_url)
            response = client.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "num_predict": max_tokens,
                    "temperature": 0.0,
                },
            )
            answer = response["message"]["content"].strip()
        elif provider == "openai":
            import openai

            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=max_tokens,
            )
            answer = response.choices[0].message.content.strip()
        else:
            return query

        # Combine query + hypothetical answer for richer signal
        combined = f"{query} {answer}"

        if use_cache:
            _save_cache(query, model, combined, cache_dir)

        return combined

    except Exception as e:
        logger.warning(
            "HyDE generation failed, falling back to query",
            extra={"error": str(e)[:200], "query": query[:80]},
        )
        return query


def batch_generate_hyde(
    queries: List[str],
    model: str = "qwen2.5-coder:7b",
    provider: str = "ollama",
    ollama_base_url: str = "http://localhost:11434",
    cache_dir: Path = DEFAULT_CACHE_DIR,
    use_cache: bool = True,
) -> List[str]:
    """Generate HyDE for a batch of queries (sequential, with caching)."""
    return [
        generate_hypothetical_answer(
            q,
            model=model,
            provider=provider,
            ollama_base_url=ollama_base_url,
            cache_dir=cache_dir,
            use_cache=use_cache,
        )
        for q in queries
    ]
