"""v0.4.2: ConfigService + Pydantic schema round-trip and validation."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from neuromem.config_schema import ConfigError, ConfigService, NeuroMemDoc


def _tmp_yaml(payload: dict) -> Path:
    f = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
    yaml.safe_dump(payload, f)
    f.close()
    return Path(f.name)


def test_default_doc_is_single_user_local_first() -> None:
    doc = NeuroMemDoc()
    assert doc.mode == "single"
    assert doc.setup_complete is False
    assert doc.auth.type == "none"
    assert doc.model.embedding == "nomic-embed-text"
    assert doc.async_.enabled is False


def test_round_trip_yaml_preserves_async_alias() -> None:
    p = _tmp_yaml({"neuromem": {"async": {"enabled": True}}})
    svc = ConfigService(p)
    doc = svc.load()
    assert doc.async_.enabled is True
    svc.save(doc)
    raw = yaml.safe_load(p.read_text())
    # Round-trip must serialize back as 'async', not 'async_'.
    assert "async" in raw["neuromem"]
    assert "async_" not in raw["neuromem"]


def test_service_mode_requires_persistent_db() -> None:
    p = _tmp_yaml(
        {
            "neuromem": {
                "mode": "service",
                "auth": {"type": "api_key"},
                "storage": {"database": {"type": "memory"}},
            }
        }
    )
    with pytest.raises(ConfigError, match="storage.database.type"):
        ConfigService(p).load()


def test_service_mode_requires_real_auth() -> None:
    p = _tmp_yaml(
        {
            "neuromem": {
                "mode": "service",
                "auth": {"type": "none"},
                "storage": {"database": {"type": "sqlite", "url": "sqlite:///:memory:"}},
            }
        }
    )
    with pytest.raises(ConfigError, match="auth.type"):
        ConfigService(p).load()


def test_unknown_keys_are_preserved() -> None:
    """``extra='allow'`` keeps third-party / future keys around."""
    p = _tmp_yaml(
        {
            "neuromem": {
                "model": {"embedding": "nomic-embed-text"},
                "third_party_extension": {"flag": True},
            }
        }
    )
    doc = ConfigService(p).load()
    raw = doc.model_dump(by_alias=True)
    assert raw.get("third_party_extension") == {"flag": True}


def test_update_merges_deeply() -> None:
    p = _tmp_yaml(
        {
            "neuromem": {
                "memory": {"consolidation_interval": 10, "max_active_memories": 50},
            }
        }
    )
    svc = ConfigService(p)
    doc = svc.update({"memory": {"max_active_memories": 100}})
    assert doc.memory.consolidation_interval == 10  # unchanged
    assert doc.memory.max_active_memories == 100  # patched


def test_load_or_default_when_file_missing() -> None:
    svc = ConfigService(Path("/tmp/does-not-exist-neuromem.yaml"))
    doc = svc.load_or_default()
    assert doc.mode == "single"
