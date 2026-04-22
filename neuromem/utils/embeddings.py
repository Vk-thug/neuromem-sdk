"""
Embedding utilities for NeuroMem.

Handles text-to-vector conversion using OpenAI embeddings with
retry logic, rate limiting, and caching.
"""

import os
import hashlib
import threading
from collections import OrderedDict
from typing import List, Optional, Dict
from neuromem.utils.retry import retry_with_exponential_backoff, CircuitBreaker, validate_api_key
from neuromem.utils.logging import get_logger

logger = get_logger(__name__)

# Global circuit breaker for OpenAI API
_openai_circuit_breaker = CircuitBreaker(
    failure_threshold=5, recovery_timeout=60.0, name="openai_embeddings"
)

# Thread-safe LRU cache for embeddings.
# Replaces the previous bare dict which was not safe under concurrent
# retrieval (3 threads in _retrieve_parallel all calling get_embedding).
_cache_lock = threading.Lock()
_embedding_cache: OrderedDict[str, List[float]] = OrderedDict()
_cache_enabled = os.getenv("NEUROMEM_CACHE_EMBEDDINGS", "true").lower() == "true"
_max_cache_size = 10000


def _cache_get(key: str) -> Optional[List[float]]:
    """Thread-safe cache read with LRU promotion."""
    with _cache_lock:
        if key in _embedding_cache:
            _embedding_cache.move_to_end(key)
            return _embedding_cache[key]
    return None


def _cache_put(key: str, value: List[float]) -> None:
    """Thread-safe cache write with LRU eviction."""
    with _cache_lock:
        if key in _embedding_cache:
            _embedding_cache.move_to_end(key)
            _embedding_cache[key] = value
        else:
            if len(_embedding_cache) >= _max_cache_size:
                _embedding_cache.popitem(last=False)  # Evict oldest
            _embedding_cache[key] = value


def _get_cache_key(text: str, model: str) -> str:
    """Generate cache key for text and model."""
    content = f"{model}:{text}"
    return hashlib.sha256(content.encode()).hexdigest()


def _call_ollama_embed(text: str, model: str) -> List[float]:
    """
    Generate embedding using Ollama local model.

    Args:
        text: Text to embed
        model: Ollama model name (e.g., 'nomic-embed-text')

    Returns:
        Embedding vector
    """
    import ollama

    # Strip 'ollama/' prefix if present
    model_name = model.replace("ollama/", "")
    response = ollama.embed(model=model_name, input=text)
    return response.embeddings[0]


def _is_ollama_model(model: str) -> bool:
    """Check if the model name indicates an Ollama embedding model."""
    ollama_models = {
        "nomic-embed-text",
        "mxbai-embed-large",
        "all-minilm",
        "snowflake-arctic-embed",
    }
    clean = model.replace("ollama/", "")
    return model.startswith("ollama/") or clean in ollama_models


# Sentence-transformers model cache (loaded on first use, reused thereafter)
_st_models: Dict[str, object] = {}
_st_lock = threading.Lock()


def _get_st_model(model: str):
    """Lazily load and cache a SentenceTransformer model."""
    with _st_lock:
        if model not in _st_models:
            from sentence_transformers import SentenceTransformer

            # Strip 'sentence-transformers/' prefix if present
            model_name = model.replace("sentence-transformers/", "")
            _st_models[model] = SentenceTransformer(model_name)
        return _st_models[model]


def _call_st_embed(text: str, model: str) -> List[float]:
    """Generate embedding using a local sentence-transformers model."""
    st_model = _get_st_model(model)
    embedding = st_model.encode([text], convert_to_numpy=True)[0]
    return embedding.tolist()


def _call_st_embed_batch(texts: List[str], model: str) -> List[List[float]]:
    """Generate embeddings for a batch of texts using sentence-transformers."""
    st_model = _get_st_model(model)
    embeddings = st_model.encode(texts, convert_to_numpy=True, batch_size=32)
    return [e.tolist() for e in embeddings]


def _is_st_model(model: str) -> bool:
    """Check if the model name indicates a sentence-transformers model."""
    st_models = {
        "all-MiniLM-L6-v2",
        "all-MiniLM-L12-v2",
        "all-mpnet-base-v2",
        "multi-qa-MiniLM-L6-cos-v1",
        "multi-qa-mpnet-base-dot-v1",
        "paraphrase-MiniLM-L6-v2",
        "paraphrase-mpnet-base-v2",
        "BAAI/bge-small-en-v1.5",
        "BAAI/bge-base-en-v1.5",
        "BAAI/bge-large-en-v1.5",
    }
    clean = model.replace("sentence-transformers/", "")
    return (
        model.startswith("sentence-transformers/")
        or clean in st_models
        or clean.startswith("BAAI/")
    )


def _generate_mock_embedding(text: str, dimensions: int = 1536) -> List[float]:
    """
    Generate deterministic mock embedding for testing.

    Args:
        text: Text to embed
        dimensions: Embedding dimensions

    Returns:
        Mock embedding vector
    """
    import numpy as np

    # Create deterministic but realistic-looking embeddings
    hash_obj = hashlib.md5(text.encode())
    seed = int(hash_obj.hexdigest(), 16) % (2**32)
    np.random.seed(seed)

    # Generate vector
    embedding = np.random.randn(dimensions).tolist()

    logger.warning(
        "Using mock embeddings (OpenAI API not available)",
        extra={"text_length": len(text), "dimensions": dimensions},
    )

    return embedding


@retry_with_exponential_backoff(
    max_retries=3,
    base_delay=1.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True,
    circuit_breaker=_openai_circuit_breaker,
)
def _call_openai_api(text: str, model: str, api_key: str) -> List[float]:
    """
    Call OpenAI API with retry logic.

    Args:
        text: Text to embed
        model: Embedding model
        api_key: OpenAI API key

    Returns:
        Embedding vector

    Raises:
        Various OpenAI API errors (will be retried if retryable)
    """
    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    response = client.embeddings.create(input=text, model=model)

    return response.data[0].embedding


def get_embedding(
    text: str,
    model: str = "text-embedding-3-large",
    api_key: Optional[str] = None,
    use_cache: bool = True,
    fallback_to_mock: bool = True,
) -> List[float]:
    """
    Get embedding vector for text with retry logic and caching.

    Args:
        text: Text to embed
        model: Embedding model to use (default: text-embedding-3-large)
        api_key: OpenAI API key (if not provided, uses OPENAI_API_KEY env var)
        use_cache: Use in-memory cache (default: True)
        fallback_to_mock: Fallback to mock embeddings if API fails (default: True)

    Returns:
        Embedding vector

    Raises:
        ValueError: If API key is invalid
        Exception: If API call fails and fallback_to_mock=False

    Example:
        >>> embedding = get_embedding("Hello world")
        >>> len(embedding)
        1536
    """
    # Validate text
    if not isinstance(text, str):
        raise ValueError(f"text must be a string, got: {type(text)}")

    if not text or not text.strip():
        # For empty or whitespace-only queries, return a zero vector
        # This allows retrieval with empty queries (returns general context)
        logger.debug("Empty text provided for embedding, returning zero vector")
        return [0.0] * 1536

    if len(text) > 100000:
        logger.warning(
            "Text too long for embedding, truncating",
            extra={"original_length": len(text), "truncated_length": 100000},
        )
        text = text[:100000]

    # Check cache (thread-safe LRU)
    cache_key = _get_cache_key(text, model)
    if use_cache and _cache_enabled:
        cached = _cache_get(cache_key)
        if cached is not None:
            logger.debug("Embedding cache hit", extra={"cache_key": cache_key[:16]})
            return cached

    # Route to sentence-transformers (local, fast, zero API cost)
    if _is_st_model(model):
        try:
            embedding = _call_st_embed(text, model)
            if use_cache and _cache_enabled:
                _cache_put(cache_key, embedding)
            logger.debug(
                "Sentence-transformers embedding generated",
                extra={"model": model, "text_length": len(text), "embedding_dim": len(embedding)},
            )
            return embedding
        except Exception as e:
            if fallback_to_mock:
                logger.error(
                    "sentence-transformers failed, falling back to mock",
                    extra={"error": str(e)[:200], "model": model},
                )
                return _generate_mock_embedding(text, dimensions=384)
            raise

    # Route to Ollama if model is an Ollama embedding model
    if _is_ollama_model(model):
        try:
            embedding = _call_ollama_embed(text, model)

            if use_cache and _cache_enabled:
                _cache_put(cache_key, embedding)

            logger.debug(
                "Ollama embedding generated",
                extra={"model": model, "text_length": len(text), "embedding_dim": len(embedding)},
            )
            return embedding

        except Exception as e:
            if fallback_to_mock:
                logger.error(
                    "Ollama embedding failed, falling back to mock",
                    extra={"error": str(e)[:200], "model": model},
                )
                return _generate_mock_embedding(text, dimensions=768)
            raise

    # Get API key for OpenAI
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")

    # Try OpenAI API
    try:
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")

        api_key = validate_api_key(api_key, provider="OpenAI")
        embedding = _call_openai_api(text, model, api_key)

        if use_cache and _cache_enabled:
            _cache_put(cache_key, embedding)

        logger.debug(
            "Embedding generated successfully",
            extra={"model": model, "text_length": len(text), "embedding_dim": len(embedding)},
        )
        return embedding

    except ImportError:
        # OpenAI not installed — try Ollama as fallback
        try:
            embedding = _call_ollama_embed("nomic-embed-text", model="nomic-embed-text")
            # If Ollama works, re-route to it
            embedding = _call_ollama_embed(text, model="nomic-embed-text")
            logger.info("OpenAI not installed, using Ollama nomic-embed-text")
            return embedding
        except Exception:
            pass
        logger.warning("No embedding provider available, using mock")
        return _generate_mock_embedding(text)

    except Exception as e:
        if fallback_to_mock:
            # Try Ollama before mock
            try:
                embedding = _call_ollama_embed(text, model="nomic-embed-text")
                logger.info("OpenAI failed, using Ollama nomic-embed-text")
                return embedding
            except Exception:
                pass
            logger.error(
                "All embedding providers failed, using mock",
                extra={"error": str(e)[:200], "model": model},
            )
            return _generate_mock_embedding(text)
        else:
            raise


def batch_get_embeddings(
    texts: List[str],
    model: str = "text-embedding-3-large",
    api_key: Optional[str] = None,
    use_cache: bool = True,
    fallback_to_mock: bool = True,
) -> List[List[float]]:
    """
    Get embeddings for multiple texts in batch (with retry and caching).

    Args:
        texts: List of texts to embed
        model: Embedding model to use
        api_key: OpenAI API key (if not provided, uses env var)
        use_cache: Use in-memory cache
        fallback_to_mock: Fallback to mock embeddings if API fails

    Returns:
        List of embedding vectors

    Example:
        >>> texts = ["Hello", "World"]
        >>> embeddings = batch_get_embeddings(texts)
        >>> len(embeddings)
        2
    """
    if not texts or not isinstance(texts, list):
        raise ValueError(f"texts must be a non-empty list, got: {type(texts)}")

    # Route to sentence-transformers (local, batched, fastest path)
    if _is_st_model(model):
        try:
            embeddings = _call_st_embed_batch(texts, model)
            if use_cache and _cache_enabled:
                for text, emb in zip(texts, embeddings):
                    _cache_put(_get_cache_key(text, model), emb)
            return embeddings
        except Exception as e:
            logger.warning(f"sentence-transformers batch failed, falling back: {str(e)[:100]}")
            # Fall through to per-item loop

    # Route Ollama models to per-item (Ollama doesn't have true batch API)
    if _is_ollama_model(model):
        return [get_embedding(t, model, api_key, use_cache, fallback_to_mock) for t in texts]

    # For small batches, try batch API
    if len(texts) <= 2048:  # OpenAI batch limit
        try:
            if not api_key:
                api_key = os.getenv("OPENAI_API_KEY")

            if api_key:
                from openai import OpenAI

                api_key = validate_api_key(api_key, provider="OpenAI")
                client = OpenAI(api_key=api_key)

                response = client.embeddings.create(input=texts, model=model)

                embeddings = [item.embedding for item in response.data]

                # Cache results (thread-safe)
                if use_cache and _cache_enabled:
                    for text, embedding in zip(texts, embeddings):
                        ck = _get_cache_key(text, model)
                        _cache_put(ck, embedding)

                logger.info(
                    "Batch embeddings generated", extra={"count": len(texts), "model": model}
                )

                return embeddings

        except Exception as e:
            logger.warning(
                f"Batch embedding failed, falling back to individual requests: {str(e)[:100]}"
            )

    # Fallback to individual requests
    return [get_embedding(text, model, api_key, use_cache, fallback_to_mock) for text in texts]


def clear_embedding_cache():
    """Clear the in-memory embedding cache."""
    with _cache_lock:
        _embedding_cache.clear()
    logger.info("Embedding cache cleared")


def get_cache_stats() -> Dict[str, int]:
    """
    Get embedding cache statistics.

    Returns:
        Dictionary with cache statistics
    """
    return {"size": len(_embedding_cache), "max_size": _max_cache_size, "enabled": _cache_enabled}
