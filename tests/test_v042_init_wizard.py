"""v0.4.2: ``neuromem init`` wizard answers → expected yaml."""

from __future__ import annotations

from neuromem.cli.init import _build_yaml


def test_single_user_ollama_qdrant_defaults() -> None:
    answers = {
        "mode": "single",
        "embedding_provider": "ollama",
        "openai_key": "",
        "storage": "qdrant",
        "postgres_url": "",
        "sqlite_url": "",
        "port": 7777,
    }
    doc = _build_yaml(answers)["neuromem"]
    assert doc["mode"] == "single"
    assert doc["setup_complete"] is True
    assert doc["auth"]["type"] == "none"
    assert doc["model"]["embedding"] == "nomic-embed-text"
    assert doc["storage"]["vector_store"]["type"] == "qdrant"
    assert doc["storage"]["vector_store"]["config"]["vector_size"] == 768
    assert doc["storage"]["database"]["type"] == "memory"


def test_single_user_openai_picks_3072_dim() -> None:
    answers = {
        "mode": "single",
        "embedding_provider": "openai",
        "openai_key": "sk-test",
        "storage": "qdrant",
        "postgres_url": "",
        "sqlite_url": "",
        "port": 7777,
    }
    doc = _build_yaml(answers)["neuromem"]
    assert doc["model"]["embedding"] == "text-embedding-3-large"
    assert doc["storage"]["vector_store"]["config"]["vector_size"] == 3072
    assert doc["model"]["consolidation_llm"] == "gpt-4o-mini"


def test_service_mode_forces_postgres_database() -> None:
    answers = {
        "mode": "service",
        "embedding_provider": "ollama",
        "openai_key": "",
        "storage": "memory",
        "postgres_url": "postgresql://u:p@h:5432/d",
        "sqlite_url": "",
        "port": 7777,
    }
    doc = _build_yaml(answers)["neuromem"]
    assert doc["mode"] == "service"
    assert doc["auth"]["type"] == "api_key"
    # Even with vector_store=memory, service mode forces a postgres user DB.
    assert doc["storage"]["database"]["type"] == "postgres"
    assert doc["storage"]["database"]["url"] == "postgresql://u:p@h:5432/d"


def test_single_mode_mints_user_uuid() -> None:
    import uuid as _uuid

    answers = {
        "mode": "single",
        "embedding_provider": "ollama",
        "openai_key": "",
        "storage": "qdrant",
        "postgres_url": "",
        "sqlite_url": "",
        "port": 7777,
    }
    doc = _build_yaml(answers)["neuromem"]
    user_id = doc["user"]["id"]
    # Must be a valid UUID, never the literal "default".
    parsed = _uuid.UUID(user_id)
    assert str(parsed) == user_id


def test_single_mode_writes_mcp_block_enabled() -> None:
    answers = {
        "mode": "single",
        "embedding_provider": "ollama",
        "openai_key": "",
        "storage": "qdrant",
        "postgres_url": "",
        "sqlite_url": "",
        "port": 7777,
    }
    doc = _build_yaml(answers)["neuromem"]
    assert doc["mcp"]["enabled"] is True
    assert doc["mcp"]["mount_path"] == "/mcp"


def test_service_mode_omits_user_block() -> None:
    answers = {
        "mode": "service",
        "embedding_provider": "ollama",
        "openai_key": "",
        "storage": "memory",
        "postgres_url": "postgresql://u:p@h:5432/d",
        "sqlite_url": "",
        "port": 7777,
    }
    doc = _build_yaml(answers)["neuromem"]
    # Service mode manages identities through SqlUserStore, not yaml.
    assert doc["user"] == {}


def test_single_user_sqlite_storage() -> None:
    answers = {
        "mode": "single",
        "embedding_provider": "ollama",
        "openai_key": "",
        "storage": "sqlite",
        "postgres_url": "",
        "sqlite_url": "sqlite:///~/.neuromem/memory.db",
        "port": 7777,
    }
    doc = _build_yaml(answers)["neuromem"]
    assert doc["storage"]["vector_store"]["type"] == "sqlite"
    assert doc["storage"]["vector_store"]["config"]["url"] == "sqlite:///~/.neuromem/memory.db"
    assert doc["storage"]["database"]["type"] == "sqlite"
    assert doc["storage"]["database"]["url"] == "sqlite:///~/.neuromem/memory.db"
