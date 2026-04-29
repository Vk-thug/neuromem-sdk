"""v0.4.2: service-mode API-key auth end-to-end."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
import yaml

pytest.importorskip("fastapi", reason="requires neuromem-sdk[ui]")
pytest.importorskip("sqlalchemy", reason="requires neuromem-sdk[ui]")
pytest.importorskip("bcrypt", reason="requires neuromem-sdk[ui]")
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def service_app(tmp_path: Path):
    db_path = tmp_path / "users.db"
    cfg = tmp_path / "neuromem.yaml"
    yaml.safe_dump(
        {
            "neuromem": {
                "mode": "service",
                "setup_complete": True,
                "auth": {"type": "api_key", "secret_env": "NEUROMEM_AUTH_SECRET"},
                "storage": {
                    "vector_store": {"type": "memory"},
                    "database": {"type": "sqlite", "url": f"sqlite:///{db_path}"},
                },
            }
        },
        cfg.open("w"),
    )
    os.environ["NEUROMEM_CONFIG"] = str(cfg)

    from neuromem.user import UserManager

    UserManager.reset()
    from neuromem import NeuroMem
    from neuromem.ui.server import create_app

    mem = NeuroMem.from_config(str(cfg), user_id=str(uuid.uuid4()))
    yield TestClient(create_app(mem))
    UserManager.reset()


def test_health_is_exempt(service_app) -> None:
    assert service_app.get("/api/health").status_code == 200


def test_protected_routes_require_key(service_app) -> None:
    assert service_app.post("/api/memories", json={"content": "x"}).status_code == 401


def test_first_user_bootstraps_without_key(service_app) -> None:
    r = service_app.post("/api/users", json={"external_id": "admin@local"})
    assert r.status_code == 200
    body = r.json()
    assert body["api_key"].startswith("nm_")
    assert body["user"]["external_id"] == "admin@local"


def test_subsequent_user_creation_requires_key(service_app) -> None:
    r = service_app.post("/api/users", json={"external_id": "first@local"})
    key = r.json()["api_key"]
    # Second user without key — denied.
    r2 = service_app.post("/api/users", json={"external_id": "second@local"})
    assert r2.status_code == 401
    # With valid key — accepted.
    r3 = service_app.post(
        "/api/users",
        json={"external_id": "second@local"},
        headers={"X-API-Key": key},
    )
    assert r3.status_code == 200


def test_invalid_key_is_rejected(service_app) -> None:
    service_app.post("/api/users", json={"external_id": "first@local"})
    r = service_app.get("/api/users/me", headers={"X-API-Key": "nm_bad"})
    assert r.status_code == 401


def test_me_returns_authenticated_user(service_app) -> None:
    r = service_app.post("/api/users", json={"external_id": "me@local"})
    key = r.json()["api_key"]
    r2 = service_app.get("/api/users/me", headers={"X-API-Key": key})
    assert r2.status_code == 200
    assert r2.json()["external_id"] == "me@local"
