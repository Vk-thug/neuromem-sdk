"""v0.4.2: GET/PUT /api/config + connection-test endpoints."""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient


@pytest.fixture
def single_mode_app(tmp_path: Path):
    cfg = tmp_path / "neuromem.yaml"
    yaml.safe_dump(
        {
            "neuromem": {
                "mode": "single",
                "setup_complete": False,
                "model": {"embedding": "nomic-embed-text"},
                "storage": {"vector_store": {"type": "memory"}},
            }
        },
        cfg.open("w"),
    )
    os.environ["NEUROMEM_CONFIG"] = str(cfg)
    from neuromem import NeuroMem
    from neuromem.ui.server import create_app

    mem = NeuroMem.from_config(str(cfg), user_id=str(uuid.uuid4()))
    return TestClient(create_app(mem)), cfg


def test_get_config_returns_setup_state(single_mode_app) -> None:
    client, cfg = single_mode_app
    r = client.get("/api/config")
    assert r.status_code == 200
    body = r.json()
    assert body["exists"] is True
    assert body["mode"] == "single"
    assert body["setup_complete"] is False


def test_put_config_marks_setup_complete(single_mode_app) -> None:
    client, cfg = single_mode_app
    r = client.put(
        "/api/config",
        json={"patch": {"setup_complete": True, "ui": {"port": 8888}}},
    )
    assert r.status_code == 200
    raw = yaml.safe_load(cfg.read_text())
    assert raw["neuromem"]["setup_complete"] is True
    assert raw["neuromem"]["ui"]["port"] == 8888
    assert "ui.port" in r.json()["restart_required"]


def test_put_config_rejects_invalid_service_mode(single_mode_app) -> None:
    client, _ = single_mode_app
    # Switching to service mode without persistent DB or auth must 400.
    r = client.put(
        "/api/config",
        json={"patch": {"mode": "service"}},
    )
    assert r.status_code == 400
    assert "service" in r.json()["detail"].lower()


def test_test_connection_unknown_target(single_mode_app) -> None:
    client, _ = single_mode_app
    r = client.post(
        "/api/config/test-connection",
        json={"target": "rabbitmq"},
    )
    assert r.status_code == 400
