"""Pydantic schema for ``neuromem.yaml`` and the ``ConfigService`` facade.

This module is the v0.4.2 source of truth for config validation. The
legacy :class:`neuromem.config.NeuroMemConfig` continues to back runtime
code paths that read the raw dict — both share the same yaml file, but
the wizard, UI editor, and ``neuromem config`` CLI go through the
schema below so changes are validated before they reach disk.

Design notes:

* Schema mirrors yaml shape exactly. Round-trip (yaml → model → yaml)
  is byte-stable enough for diff previews in the UI.
* ``mode`` is an explicit top-level field (single | service). The
  wizard sets it; ``UserManager`` reads it to pick its backend.
* Unknown keys are preserved (``extra='allow'``). This keeps third-party
  extensions and future fields working without lockstep schema bumps.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Permissive(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ModelConfig(_Permissive):
    embedding: str = "nomic-embed-text"
    consolidation_llm: str = "ollama/qwen2.5-coder:7b"


class VectorStoreConfig(_Permissive):
    type: Literal["qdrant", "postgres", "sqlite", "memory"] = "memory"
    config: Dict[str, Any] = Field(default_factory=dict)
    collection: Optional[str] = None


class DatabaseConfig(_Permissive):
    type: Literal["postgres", "sqlite", "memory"] = "memory"
    url: Optional[str] = None


class CacheConfig(_Permissive):
    type: Literal["redis", "memory"] = "memory"
    ttl_seconds: int = 3600


class StorageConfig(_Permissive):
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)


class MemorySettings(_Permissive):
    decay_enabled: bool = True
    consolidation_interval: int = 10
    max_active_memories: int = 50
    episodic_retention_days: int = 30
    min_confidence_threshold: float = 0.3


class AsyncSettings(_Permissive):
    enabled: bool = False
    critical_queue_size: int = 1000
    high_queue_size: int = 500
    medium_queue_size: int = 100
    low_queue_size: int = 50
    background_queue_size: int = 10
    salience_threshold: float = 0.7


class AuthConfig(_Permissive):
    type: Literal["none", "api_key", "jwt"] = "none"
    secret_env: str = "NEUROMEM_AUTH_SECRET"


class UISettings(_Permissive):
    port: int = 7777
    host: str = "127.0.0.1"


class NeuroMemDoc(_Permissive):
    """The body under the top-level ``neuromem:`` key."""

    mode: Literal["single", "service"] = "single"
    setup_complete: bool = False
    auth: AuthConfig = Field(default_factory=AuthConfig)
    ui: UISettings = Field(default_factory=UISettings)
    model: ModelConfig = Field(default_factory=ModelConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    async_: AsyncSettings = Field(default_factory=AsyncSettings, alias="async")

    @field_validator("mode")
    @classmethod
    def _service_requires_persistent_db(cls, v: str, info: Any) -> str:
        # Defensive cross-field check is done in ConfigService.validate_full
        # because pydantic field validators don't see siblings reliably here.
        return v


class NeuroMemRoot(_Permissive):
    """Top-level wrapper: ``{neuromem: {...}}``."""

    neuromem: NeuroMemDoc = Field(default_factory=NeuroMemDoc)


class ConfigError(ValueError):
    """Raised on schema or cross-field validation failures."""


class ConfigService:
    """Load / save / validate ``neuromem.yaml`` through the Pydantic schema.

    Usage::

        cfg = ConfigService("neuromem.yaml").load()
        cfg.mode  # 'single' | 'service'
        cfg.storage.vector_store.type

        ConfigService("neuromem.yaml").save(cfg)
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> NeuroMemDoc:
        if not self.path.exists():
            raise FileNotFoundError(f"Config not found: {self.path}")
        with self.path.open("r") as f:
            raw = yaml.safe_load(f) or {}
        return self._parse(raw)

    def load_or_default(self) -> NeuroMemDoc:
        if self.path.exists():
            return self.load()
        return NeuroMemDoc()

    def save(self, doc: NeuroMemDoc) -> None:
        self.validate_full(doc)
        payload = {"neuromem": doc.model_dump(mode="json", by_alias=True, exclude_none=False)}
        with self.path.open("w") as f:
            yaml.safe_dump(payload, f, default_flow_style=False, sort_keys=False)

    def update(self, patch: Dict[str, Any]) -> NeuroMemDoc:
        """Merge ``patch`` into the current doc and persist."""
        current = self.load_or_default().model_dump(mode="json", by_alias=True)
        merged = _deep_merge(current, patch)
        doc = self._parse({"neuromem": merged})
        self.save(doc)
        return doc

    @staticmethod
    def validate_full(doc: NeuroMemDoc) -> None:
        """Cross-field invariants that single-field validators can't see."""
        if doc.mode == "service":
            if doc.storage.database.type == "memory":
                raise ConfigError(
                    "mode=service requires storage.database.type to be 'postgres' "
                    "or 'sqlite' (in-memory user store does not persist across restarts)."
                )
            if doc.auth.type == "none":
                raise ConfigError("mode=service requires auth.type to be 'api_key' or 'jwt'.")

    @staticmethod
    def _parse(raw: Dict[str, Any]) -> NeuroMemDoc:
        try:
            root = NeuroMemRoot.model_validate(raw)
        except Exception as exc:
            raise ConfigError(f"Invalid neuromem.yaml: {exc}") from exc
        ConfigService.validate_full(root.neuromem)
        return root.neuromem


def _deep_merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in patch.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


__all__ = [
    "ConfigError",
    "ConfigService",
    "NeuroMemDoc",
    "NeuroMemRoot",
    "ModelConfig",
    "StorageConfig",
    "VectorStoreConfig",
    "DatabaseConfig",
    "CacheConfig",
    "MemorySettings",
    "AsyncSettings",
    "AuthConfig",
    "UISettings",
]
