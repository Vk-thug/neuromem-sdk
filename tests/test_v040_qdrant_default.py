"""
Tests for v0.4.0 Qdrant default + health-check fallback.
"""

from __future__ import annotations

from unittest import mock

import pytest

from neuromem import _try_qdrant_or_fallback
from neuromem.storage.memory import InMemoryBackend


class TestQdrantFallback:
    def test_qdrant_unreachable_falls_back_to_memory(self):
        """Bad host/port → InMemoryBackend, no exception raised."""
        backend = _try_qdrant_or_fallback(
            {"host": "127.0.0.1", "port": 1, "collection_name": "test"}
        )
        assert isinstance(backend, InMemoryBackend)

    def test_qdrant_client_missing_falls_back_to_memory(self):
        """If qdrant-client is not importable, fall back gracefully."""
        with mock.patch.dict("sys.modules", {"neuromem.storage.qdrant": None}):
            # Force ImportError when trying to import the qdrant submodule.
            # We do this by injecting a sentinel that raises on attribute access.
            import builtins

            real_import = builtins.__import__

            def fake_import(name, *args, **kwargs):
                if name == "neuromem.storage.qdrant":
                    raise ImportError("qdrant-client not installed (simulated)")
                return real_import(name, *args, **kwargs)

            with mock.patch("builtins.__import__", side_effect=fake_import):
                backend = _try_qdrant_or_fallback({"host": "localhost", "port": 6333})
                assert isinstance(backend, InMemoryBackend)

    def test_default_yaml_specifies_qdrant(self):
        """neuromem.yaml at the repo root must default to qdrant in v0.4.0."""
        from pathlib import Path

        import yaml

        repo_root = Path(__file__).resolve().parent.parent
        with open(repo_root / "neuromem.yaml", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        vs = cfg["neuromem"]["storage"]["vector_store"]
        assert (
            vs["type"] == "qdrant"
        ), "v0.4.0 default vector_store.type must be qdrant; got " + repr(vs["type"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
