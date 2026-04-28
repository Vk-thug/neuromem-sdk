"""
Provider-tagged exceptions (v0.4.0, H1-R10/R7).

NeuroMem makes calls to multiple external providers — OpenAI, Ollama, Cohere,
Anthropic, Google, sentence-transformers, BGE, etc. — across the embedding,
HyDE, LLM-rerank, cross-encoder, and consolidation paths. When a provider
fails, the upstream error message is opaque about *which* provider produced
it (Letta issue #3310 documents this exact pain: "Rate limited by OpenAI"
shown for a Cohere rate limit because the wrapper layer didn't tag).

This module provides:

* ``ProviderError`` — the base exception, with ``provider`` and ``upstream``
  attributes plus a kind hint (rate-limit / auth / timeout / unavailable /
  unknown).
* ``ProviderRateLimitError``, ``ProviderAuthError``, ``ProviderTimeoutError``,
  ``ProviderUnavailableError`` — specialisations for callers that want to
  branch on category.
* ``wrap_provider(provider_name, *, kind=None)`` — a decorator that catches
  any exception from the wrapped function and re-raises tagged with the
  provider name. The original exception is preserved as ``__cause__``.
* ``classify_upstream(exc)`` — a heuristic that maps known upstream
  exceptions / status codes to a ``ProviderErrorKind``.

The decorator is intentionally narrow: it only translates the exception. It
does not retry, does not log (logging is the caller's job), and does not
swallow. ``ProviderError`` always propagates.
"""

from __future__ import annotations

import functools
from enum import Enum
from typing import Any, Callable, Optional, TypeVar


F = TypeVar("F", bound=Callable[..., Any])


class ProviderErrorKind(str, Enum):
    """High-level category of a provider-side failure.

    Callers branching on these get a stable contract regardless of which
    provider raised. ``UNKNOWN`` is the safe default — never invent a more
    specific kind without evidence.
    """

    RATE_LIMIT = "rate_limit"
    AUTH = "auth"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    BAD_REQUEST = "bad_request"
    UNKNOWN = "unknown"


class ProviderError(Exception):
    """Base class for any provider-side failure tagged with a provider name.

    Attributes:
        provider: The provider that failed (e.g. ``"openai"``, ``"ollama"``,
            ``"cohere"``, ``"sentence-transformers"``).
        upstream: The original exception, also stored as ``__cause__``.
        kind: Optional high-level category; useful for retry / fallback logic.
    """

    def __init__(
        self,
        provider: str,
        message: str,
        upstream: Optional[BaseException] = None,
        kind: ProviderErrorKind = ProviderErrorKind.UNKNOWN,
    ) -> None:
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        self.upstream = upstream
        self.kind = kind


class ProviderRateLimitError(ProviderError):
    """Provider rejected the call because of rate limiting / quota."""

    def __init__(
        self, provider: str, message: str, upstream: Optional[BaseException] = None
    ) -> None:
        super().__init__(provider, message, upstream, ProviderErrorKind.RATE_LIMIT)


class ProviderAuthError(ProviderError):
    """Provider rejected the call because of bad / missing credentials."""

    def __init__(
        self, provider: str, message: str, upstream: Optional[BaseException] = None
    ) -> None:
        super().__init__(provider, message, upstream, ProviderErrorKind.AUTH)


class ProviderTimeoutError(ProviderError):
    """Provider call exceeded the timeout."""

    def __init__(
        self, provider: str, message: str, upstream: Optional[BaseException] = None
    ) -> None:
        super().__init__(provider, message, upstream, ProviderErrorKind.TIMEOUT)


class ProviderUnavailableError(ProviderError):
    """Provider returned 5xx / connection refused / DNS failure / similar."""

    def __init__(
        self, provider: str, message: str, upstream: Optional[BaseException] = None
    ) -> None:
        super().__init__(provider, message, upstream, ProviderErrorKind.UNAVAILABLE)


_KIND_TO_CLASS = {
    ProviderErrorKind.RATE_LIMIT: ProviderRateLimitError,
    ProviderErrorKind.AUTH: ProviderAuthError,
    ProviderErrorKind.TIMEOUT: ProviderTimeoutError,
    ProviderErrorKind.UNAVAILABLE: ProviderUnavailableError,
}


# Status-code → kind heuristic. Tightly scoped: we only claim categories we
# can defend. Unknown 4xx → BAD_REQUEST so callers don't retry. Unknown 5xx →
# UNAVAILABLE so callers can retry.
_STATUS_TO_KIND = {
    400: ProviderErrorKind.BAD_REQUEST,
    401: ProviderErrorKind.AUTH,
    403: ProviderErrorKind.AUTH,
    408: ProviderErrorKind.TIMEOUT,
    429: ProviderErrorKind.RATE_LIMIT,
    500: ProviderErrorKind.UNAVAILABLE,
    502: ProviderErrorKind.UNAVAILABLE,
    503: ProviderErrorKind.UNAVAILABLE,
    504: ProviderErrorKind.TIMEOUT,
}


def classify_upstream(exc: BaseException) -> ProviderErrorKind:
    """Heuristic mapping of an upstream exception to a kind.

    Looks at, in order:
    1. The class name (``RateLimitError``, ``AuthenticationError``, ``Timeout``).
    2. A ``status_code`` / ``http_status`` attribute via ``_STATUS_TO_KIND``.
    3. The string of the exception (last-resort substring match).

    Returns ``UNKNOWN`` when the exception doesn't match any known shape.
    """
    name = type(exc).__name__.lower()
    if "ratelimit" in name or "rate_limit" in name or "quota" in name:
        return ProviderErrorKind.RATE_LIMIT
    if "auth" in name or "permissiondenied" in name or "forbidden" in name:
        return ProviderErrorKind.AUTH
    if "timeout" in name:
        return ProviderErrorKind.TIMEOUT
    if "connection" in name or "unavailable" in name or "service" in name:
        return ProviderErrorKind.UNAVAILABLE

    status = getattr(exc, "status_code", None) or getattr(exc, "http_status", None)
    if isinstance(status, int) and status in _STATUS_TO_KIND:
        return _STATUS_TO_KIND[status]

    text = str(exc).lower()
    if "rate limit" in text or "rate_limit" in text or "quota" in text:
        return ProviderErrorKind.RATE_LIMIT
    if "timeout" in text or "timed out" in text:
        return ProviderErrorKind.TIMEOUT
    if "unauthorized" in text or "invalid api key" in text or "authentication" in text:
        return ProviderErrorKind.AUTH
    if "connection refused" in text or "service unavailable" in text:
        return ProviderErrorKind.UNAVAILABLE

    return ProviderErrorKind.UNKNOWN


def wrap_provider(
    provider: str, *, kind: Optional[ProviderErrorKind] = None
) -> Callable[[F], F]:
    """Decorator that re-raises any exception as a tagged ``ProviderError``.

    Use at the boundary where NeuroMem code calls into a third-party SDK.
    Re-raises ``ProviderError`` instances unchanged (so nested wraps don't
    double-tag). Otherwise classifies the upstream exception and re-raises
    with the appropriate ``ProviderError`` subclass.

    Args:
        provider: Stable provider name string. Lower-case, hyphenated.
        kind: Optional override of the auto-classified kind. Pass when the
            call site has more specific knowledge than the heuristic.

    Example:
        >>> @wrap_provider("openai")
        ... def _embed(text: str) -> list[float]:
        ...     return openai.embeddings.create(...)
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except ProviderError:
                # Already tagged — let it through unchanged.
                raise
            except Exception as exc:
                resolved_kind = kind or classify_upstream(exc)
                cls = _KIND_TO_CLASS.get(resolved_kind, ProviderError)
                if cls is ProviderError:
                    raise ProviderError(
                        provider, str(exc), upstream=exc, kind=resolved_kind
                    ) from exc
                raise cls(provider, str(exc), upstream=exc) from exc

        return wrapper  # type: ignore[return-value]

    return decorator


__all__ = [
    "ProviderErrorKind",
    "ProviderError",
    "ProviderRateLimitError",
    "ProviderAuthError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "classify_upstream",
    "wrap_provider",
]
