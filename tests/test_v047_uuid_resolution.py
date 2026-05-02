"""v0.4.7: ``neuromem ui`` user_id resolution policy (Strategy B).

Order of precedence:
    1. ``--user`` flag (rejecting the literal "default")
    2. yaml ``neuromem.user.id``
    3. ``NEUROMEM_USER_ID`` env var (rejecting the literal "default")
    4. Mint a fresh UUID, persist to yaml, warn the user

These tests exercise :func:`neuromem.ui.cli._resolve_user_id` directly so
we don't have to spin up uvicorn.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import yaml

from neuromem.ui.cli import _resolve_user_id


def _write_yaml(tmp_path: Path, body: dict) -> Path:
    cfg = tmp_path / "neuromem.yaml"
    with cfg.open("w") as f:
        yaml.safe_dump({"neuromem": body}, f)
    return cfg


def _read_yaml_user_id(cfg: Path) -> str | None:
    with cfg.open("r") as f:
        doc = yaml.safe_load(f) or {}
    return (doc.get("neuromem") or {}).get("user", {}).get("id")


def test_cli_user_flag_wins(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NEUROMEM_USER_ID", raising=False)
    cfg = _write_yaml(tmp_path, {"mode": "single", "user": {"id": str(uuid.uuid4())}})
    explicit = "abc123"
    assert _resolve_user_id(str(cfg), explicit) == explicit


def test_yaml_user_id_used_when_no_flag(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NEUROMEM_USER_ID", raising=False)
    yaml_uuid = str(uuid.uuid4())
    cfg = _write_yaml(tmp_path, {"mode": "single", "user": {"id": yaml_uuid}})
    assert _resolve_user_id(str(cfg), None) == yaml_uuid


def test_legacy_yaml_mints_and_persists(tmp_path: Path, monkeypatch, capsys) -> None:
    """Legacy yaml has no ``user.id``; resolver mints, persists, warns."""
    monkeypatch.delenv("NEUROMEM_USER_ID", raising=False)
    cfg = _write_yaml(tmp_path, {"mode": "single"})

    resolved = _resolve_user_id(str(cfg), None)
    parsed = uuid.UUID(resolved)
    assert str(parsed) == resolved

    persisted = _read_yaml_user_id(cfg)
    assert persisted == resolved

    captured = capsys.readouterr()
    assert "minted" in captured.out.lower()
    assert resolved in captured.out


def test_literal_default_user_flag_rejected(tmp_path: Path, monkeypatch) -> None:
    """``--user default`` falls through to yaml resolution (no longer wins)."""
    monkeypatch.delenv("NEUROMEM_USER_ID", raising=False)
    yaml_uuid = str(uuid.uuid4())
    cfg = _write_yaml(tmp_path, {"mode": "single", "user": {"id": yaml_uuid}})
    assert _resolve_user_id(str(cfg), "default") == yaml_uuid


def test_env_user_id_used_after_yaml_miss(tmp_path: Path, monkeypatch) -> None:
    env_uuid = str(uuid.uuid4())
    monkeypatch.setenv("NEUROMEM_USER_ID", env_uuid)
    cfg = _write_yaml(tmp_path, {"mode": "single"})
    # Even with no yaml user.id, env wins over minting.
    assert _resolve_user_id(str(cfg), None) == env_uuid
    # And we should NOT have persisted anything since env took over.
    assert _read_yaml_user_id(cfg) is None


def test_no_yaml_no_env_no_flag_mints_without_persist(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("NEUROMEM_USER_ID", raising=False)
    phantom = tmp_path / "does_not_exist.yaml"
    minted = _resolve_user_id(str(phantom), None)
    assert uuid.UUID(minted)
    # Phantom yaml — we don't create one for the user.
    assert not phantom.exists()
