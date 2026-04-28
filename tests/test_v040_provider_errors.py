"""
Tests for v0.4.0 H1-R7: provider-tagged exceptions (ProviderError family).
"""

from __future__ import annotations

import pytest

from neuromem.utils.providers import (
    ProviderAuthError,
    ProviderError,
    ProviderErrorKind,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    classify_upstream,
    wrap_provider,
)


class TestProviderErrorBasics:
    def test_provider_attribute_set(self):
        err = ProviderError("openai", "boom")
        assert err.provider == "openai"
        assert "[openai]" in str(err)

    def test_subclasses_carry_kind(self):
        assert ProviderRateLimitError("x", "y").kind is ProviderErrorKind.RATE_LIMIT
        assert ProviderAuthError("x", "y").kind is ProviderErrorKind.AUTH
        assert ProviderTimeoutError("x", "y").kind is ProviderErrorKind.TIMEOUT
        assert ProviderUnavailableError("x", "y").kind is ProviderErrorKind.UNAVAILABLE


class TestClassifyUpstream:
    def test_class_name_rate_limit(self):
        class RateLimitError(Exception): ...

        assert classify_upstream(RateLimitError("over quota")) is ProviderErrorKind.RATE_LIMIT

    def test_class_name_timeout(self):
        class APITimeoutError(Exception): ...

        assert classify_upstream(APITimeoutError("slow")) is ProviderErrorKind.TIMEOUT

    def test_status_code_429(self):
        exc = Exception("nope")
        exc.status_code = 429  # type: ignore[attr-defined]
        assert classify_upstream(exc) is ProviderErrorKind.RATE_LIMIT

    def test_status_code_401(self):
        exc = Exception("denied")
        exc.status_code = 401  # type: ignore[attr-defined]
        assert classify_upstream(exc) is ProviderErrorKind.AUTH

    def test_message_substring_fallback(self):
        assert classify_upstream(Exception("Connection refused")) is ProviderErrorKind.UNAVAILABLE

    def test_unknown_default(self):
        assert classify_upstream(ValueError("???")) is ProviderErrorKind.UNKNOWN


class TestWrapProviderDecorator:
    def test_passthrough_on_success(self):
        @wrap_provider("openai")
        def f():
            return 42

        assert f() == 42

    def test_tags_unknown_exception(self):
        @wrap_provider("ollama")
        def f():
            raise ValueError("kaboom")

        with pytest.raises(ProviderError) as exc_info:
            f()
        assert exc_info.value.provider == "ollama"
        assert isinstance(exc_info.value.upstream, ValueError)
        # Unknown shape → base ProviderError, not a subclass.
        assert exc_info.value.kind is ProviderErrorKind.UNKNOWN

    def test_tags_rate_limit_via_subclass(self):
        class RateLimitError(Exception): ...

        @wrap_provider("openai")
        def f():
            raise RateLimitError("over quota")

        with pytest.raises(ProviderRateLimitError) as exc_info:
            f()
        assert exc_info.value.provider == "openai"

    def test_does_not_double_tag(self):
        @wrap_provider("inner")
        def inner():
            raise ProviderRateLimitError("outer", "already tagged")

        # The outer wrap re-raises ProviderError unchanged: provider stays "outer".
        with pytest.raises(ProviderRateLimitError) as exc_info:
            inner()
        assert exc_info.value.provider == "outer"

    def test_kind_override(self):
        @wrap_provider("custom", kind=ProviderErrorKind.UNAVAILABLE)
        def f():
            raise RuntimeError("anything")

        with pytest.raises(ProviderUnavailableError):
            f()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
