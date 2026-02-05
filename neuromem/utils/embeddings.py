"""
Embedding utilities for NeuroMem.

Handles text-to-vector conversion using OpenAI embeddings with
retry logic, rate limiting, and caching.
"""

import os
import hashlib
from typing import List, Optional, Dict
from neuromem.utils.retry import retry_with_exponential_backoff, CircuitBreaker, validate_api_key
from neuromem.utils.logging import get_logger

logger = get_logger(__name__)

# Global circuit breaker for OpenAI API
_openai_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60.0,
    name="openai_embeddings"
)

# Simple in-memory cache for embeddings
_embedding_cache: Dict[str, List[float]] = {}
_cache_enabled = os.getenv("NEUROMEM_CACHE_EMBEDDINGS", "true").lower() == "true"
_max_cache_size = 10000


def _get_cache_key(text: str, model: str) -> str:
    """Generate cache key for text and model."""
    content = f"{model}:{text}"
    return hashlib.sha256(content.encode()).hexdigest()


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
        extra={'text_length': len(text), 'dimensions': dimensions}
    )

    return embedding


@retry_with_exponential_backoff(
    max_retries=3,
    base_delay=1.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True,
    circuit_breaker=_openai_circuit_breaker
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

    response = client.embeddings.create(
        input=text,
        model=model
    )

    return response.data[0].embedding


def get_embedding(
    text: str,
    model: str = "text-embedding-3-large",
    api_key: Optional[str] = None,
    use_cache: bool = True,
    fallback_to_mock: bool = True
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
            extra={'original_length': len(text), 'truncated_length': 100000}
        )
        text = text[:100000]

    # Check cache
    if use_cache and _cache_enabled:
        cache_key = _get_cache_key(text, model)
        if cache_key in _embedding_cache:
            logger.debug("Embedding cache hit", extra={'cache_key': cache_key[:16]})
            return _embedding_cache[cache_key]

    # Get API key
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")

    # Try OpenAI API
    try:
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")

        # Validate API key
        api_key = validate_api_key(api_key, provider="OpenAI")

        # Call API with retry logic
        embedding = _call_openai_api(text, model, api_key)

        # Cache result
        if use_cache and _cache_enabled:
            if len(_embedding_cache) >= _max_cache_size:
                # Simple FIFO eviction
                _embedding_cache.pop(next(iter(_embedding_cache)))
            _embedding_cache[cache_key] = embedding

        logger.debug(
            "Embedding generated successfully",
            extra={'model': model, 'text_length': len(text), 'embedding_dim': len(embedding)}
        )

        return embedding

    except ImportError:
        logger.warning("OpenAI package not installed, using mock embeddings")
        return _generate_mock_embedding(text)

    except Exception as e:
        if fallback_to_mock:
            logger.error(
                "OpenAI API call failed, falling back to mock embeddings",
                exc_info=True,
                extra={'error': str(e)[:200], 'model': model}
            )
            return _generate_mock_embedding(text)
        else:
            logger.error(
                "OpenAI API call failed",
                exc_info=True,
                extra={'error': str(e)[:200], 'model': model}
            )
            raise


def batch_get_embeddings(
    texts: List[str],
    model: str = "text-embedding-3-large",
    api_key: Optional[str] = None,
    use_cache: bool = True,
    fallback_to_mock: bool = True
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

    # For small batches, try batch API
    if len(texts) <= 2048:  # OpenAI batch limit
        try:
            if not api_key:
                api_key = os.getenv("OPENAI_API_KEY")

            if api_key:
                from openai import OpenAI

                api_key = validate_api_key(api_key, provider="OpenAI")
                client = OpenAI(api_key=api_key)

                response = client.embeddings.create(
                    input=texts,
                    model=model
                )

                embeddings = [item.embedding for item in response.data]

                # Cache results
                if use_cache and _cache_enabled:
                    for text, embedding in zip(texts, embeddings):
                        cache_key = _get_cache_key(text, model)
                        if len(_embedding_cache) < _max_cache_size:
                            _embedding_cache[cache_key] = embedding

                logger.info(
                    "Batch embeddings generated",
                    extra={'count': len(texts), 'model': model}
                )

                return embeddings

        except Exception as e:
            logger.warning(
                f"Batch embedding failed, falling back to individual requests: {str(e)[:100]}"
            )

    # Fallback to individual requests
    return [
        get_embedding(text, model, api_key, use_cache, fallback_to_mock)
        for text in texts
    ]


def clear_embedding_cache():
    """Clear the in-memory embedding cache."""
    global _embedding_cache
    _embedding_cache = {}
    logger.info("Embedding cache cleared")


def get_cache_stats() -> Dict[str, int]:
    """
    Get embedding cache statistics.

    Returns:
        Dictionary with cache statistics
    """
    return {
        'size': len(_embedding_cache),
        'max_size': _max_cache_size,
        'enabled': _cache_enabled
    }
