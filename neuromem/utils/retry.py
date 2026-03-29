"""
Retry and circuit breaker utilities for external API calls.

Provides robust error handling for OpenAI API and other external services.
"""

import time
import random
from typing import Callable, TypeVar, Optional
from functools import wraps
from neuromem.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    pass


class CircuitBreaker:
    """
    Circuit breaker pattern for external API calls.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, reject all requests
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(
        self, failure_threshold: int = 5, recovery_timeout: float = 60.0, name: str = "default"
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying again
            name: Name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name

        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"

    def call(self, func: Callable[[], T]) -> T:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
        """
        if self.state == "OPEN":
            if self._should_attempt_reset():
                logger.info(f"Circuit breaker {self.name}: Attempting reset (HALF_OPEN)")
                self.state = "HALF_OPEN"
            else:
                logger.warning(f"Circuit breaker {self.name}: Request rejected (OPEN)")
                raise CircuitBreakerError(
                    f"Circuit breaker {self.name} is OPEN. "
                    f"Try again in {self.recovery_timeout} seconds"
                )

        try:
            result = func()
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) >= self.recovery_timeout

    def _on_success(self):
        """Handle successful request."""
        if self.state == "HALF_OPEN":
            logger.info(f"Circuit breaker {self.name}: Reset successful (CLOSED)")
        self.failure_count = 0
        self.state = "CLOSED"

    def _on_failure(self):
        """Handle failed request."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.error(
                f"Circuit breaker {self.name}: Opened after {self.failure_count} failures",
                extra={"threshold": self.failure_threshold},
            )


def retry_with_exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    circuit_breaker: Optional[CircuitBreaker] = None,
):
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exponential_base: Base for exponential backoff calculation
        jitter: Add random jitter to prevent thundering herd
        circuit_breaker: Optional circuit breaker instance

    Example:
        @retry_with_exponential_backoff(max_retries=3, base_delay=1.0)
        def call_api():
            return requests.get("https://api.example.com")
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # If circuit breaker is open, fail fast
            if circuit_breaker and circuit_breaker.state == "OPEN":
                if not circuit_breaker._should_attempt_reset():
                    raise CircuitBreakerError(f"Circuit breaker {circuit_breaker.name} is OPEN")

            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    if circuit_breaker:
                        result = circuit_breaker.call(lambda: func(*args, **kwargs))
                    else:
                        result = func(*args, **kwargs)

                    if attempt > 0:
                        logger.info(
                            f"Retry successful for {func.__name__}",
                            extra={"attempt": attempt, "max_retries": max_retries},
                        )
                    return result

                except Exception as e:
                    last_exception = e

                    # Check if error is retryable
                    if not _is_retryable_error(e):
                        logger.error(
                            f"Non-retryable error in {func.__name__}: {type(e).__name__}",
                            exc_info=True,
                        )
                        raise

                    if attempt < max_retries:
                        # Calculate delay with exponential backoff
                        delay = min(base_delay * (exponential_base**attempt), max_delay)

                        # Add jitter to prevent thundering herd
                        if jitter:
                            delay = delay * (0.5 + random.random() * 0.5)

                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                            f"after {delay:.2f}s delay. Error: {str(e)[:100]}",
                            extra={
                                "attempt": attempt,
                                "delay": delay,
                                "error_type": type(e).__name__,
                            },
                        )

                        time.sleep(delay)
                    else:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}",
                            exc_info=True,
                            extra={"max_retries": max_retries},
                        )

            # All retries exhausted
            raise last_exception

        return wrapper

    return decorator


def _is_retryable_error(error: Exception) -> bool:
    """
    Determine if an error is retryable.

    Retryable errors:
    - Network errors (timeouts, connection errors)
    - Rate limit errors (429)
    - Server errors (5xx)

    Non-retryable errors:
    - Authentication errors (401, 403)
    - Invalid request errors (400, 422)
    - Not found errors (404)
    """
    error_type = type(error).__name__
    error_msg = str(error).lower()

    # OpenAI specific errors
    if "RateLimitError" in error_type or "rate_limit" in error_msg or "429" in error_msg:
        return True

    if "APIConnectionError" in error_type or "connection" in error_msg:
        return True

    if "Timeout" in error_type or "timeout" in error_msg:
        return True

    if "APIError" in error_type or "500" in error_msg or "502" in error_msg or "503" in error_msg:
        return True

    # HTTP client errors (non-retryable)
    if any(code in error_msg for code in ["400", "401", "403", "404", "422"]):
        return False

    # By default, retry on unknown errors (defensive)
    return True


def validate_api_key(api_key: Optional[str], provider: str = "OpenAI") -> str:
    """
    Validate API key format and existence.

    Args:
        api_key: API key to validate
        provider: Provider name for error messages

    Returns:
        Validated API key

    Raises:
        ValueError: If API key is invalid
    """
    if not api_key:
        raise ValueError(
            f"{provider} API key not found. "
            f"Set OPENAI_API_KEY environment variable or pass api_key parameter."
        )

    if not isinstance(api_key, str):
        raise ValueError(f"{provider} API key must be a string, got {type(api_key)}")

    if len(api_key) < 10:
        raise ValueError(f"{provider} API key appears to be invalid (too short)")

    # OpenAI keys start with "sk-"
    if provider == "OpenAI" and not api_key.startswith("sk-"):
        logger.warning(
            f"{provider} API key does not start with 'sk-'. This may indicate an invalid key.",
            extra={"key_prefix": api_key[:3]},
        )

    return api_key
