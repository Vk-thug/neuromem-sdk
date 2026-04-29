"""``/api/config`` — read, update, and validate ``neuromem.yaml`` from the UI.

The wizard (``/onboarding``) and settings page (``/settings``) both go
through these endpoints. All writes round-trip through
:class:`neuromem.config_schema.ConfigService` so the yaml on disk can
never become invalid via the UI.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from neuromem.config_schema import ConfigError, ConfigService, NeuroMemDoc

# Fields where changing the value mid-process won't take effect until
# the server restarts. The UI flags these with a "restart required" badge.
_RESTART_REQUIRED_PATHS = {
    "storage.vector_store.type",
    "storage.vector_store.config.host",
    "storage.vector_store.config.port",
    "storage.vector_store.config.collection_name",
    "storage.vector_store.config.vector_size",
    "storage.database.type",
    "storage.database.url",
    "model.embedding",
    "mode",
    "auth.type",
    "ui.port",
    "ui.host",
}


class ConfigPatch(BaseModel):
    """Partial update payload — any subset of NeuroMemDoc fields."""

    patch: Dict[str, Any]


class TestConnectionRequest(BaseModel):
    target: str  # 'ollama' | 'qdrant' | 'postgres'
    host: Optional[str] = None
    port: Optional[int] = None
    url: Optional[str] = None


def _resolve_config_path() -> Path:
    """Resolve the active config path from env, falling back to cwd."""
    return Path(os.environ.get("NEUROMEM_CONFIG", "neuromem.yaml"))


def _flatten(doc: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in doc.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, path))
        else:
            out[path] = v
    return out


def _restart_required_diff(before: NeuroMemDoc, after: NeuroMemDoc) -> List[str]:
    bf = _flatten(before.model_dump(mode="json", by_alias=True))
    af = _flatten(after.model_dump(mode="json", by_alias=True))
    changed = [p for p in af if af.get(p) != bf.get(p)]
    return [p for p in changed if p in _RESTART_REQUIRED_PATHS]


def build_router() -> APIRouter:
    router = APIRouter(prefix="/api/config", tags=["config"])

    @router.get("")
    def get_config() -> Dict[str, Any]:
        path = _resolve_config_path()
        service = ConfigService(path)
        doc = service.load_or_default()
        return {
            "path": str(path),
            "exists": path.exists(),
            "config": doc.model_dump(mode="json", by_alias=True),
            "setup_complete": doc.setup_complete,
            "mode": doc.mode,
        }

    @router.put("")
    def put_config(payload: ConfigPatch) -> Dict[str, Any]:
        path = _resolve_config_path()
        service = ConfigService(path)
        before = service.load_or_default()
        try:
            after = service.update(payload.patch)
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "ok": True,
            "config": after.model_dump(mode="json", by_alias=True),
            "restart_required": _restart_required_diff(before, after),
        }

    @router.post("/validate")
    def validate_config(payload: ConfigPatch) -> Dict[str, Any]:
        path = _resolve_config_path()
        service = ConfigService(path)
        current = service.load_or_default().model_dump(mode="json", by_alias=True)
        from neuromem.config_schema import _deep_merge

        merged = _deep_merge(current, payload.patch)
        try:
            doc = ConfigService._parse({"neuromem": merged})
            ConfigService.validate_full(doc)
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}

    @router.post("/test-connection")
    def test_connection(req: TestConnectionRequest) -> Dict[str, Any]:
        from neuromem.cli.doctor import _check_ollama, _check_postgres, _check_qdrant

        if req.target == "ollama":
            ok, msg = _check_ollama(req.host or "localhost", req.port or 11434)
        elif req.target == "qdrant":
            ok, msg = _check_qdrant(req.host or "localhost", req.port or 6333)
        elif req.target == "postgres":
            if not req.url:
                raise HTTPException(status_code=400, detail="postgres test requires url")
            ok, msg = _check_postgres(req.url)
        else:
            raise HTTPException(status_code=400, detail=f"unknown target: {req.target}")

        return {"ok": ok, "message": msg}

    return router
