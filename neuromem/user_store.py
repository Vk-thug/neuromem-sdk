"""Pluggable backends for :class:`neuromem.user.UserManager`.

v0.4.1 and earlier shipped a single in-memory store on the class itself.
Service mode (v0.4.2+) needs persistence + API-key auth, so the storage
moves behind a :class:`UserStore` protocol with two implementations:

* :class:`InMemoryUserStore` — preserves v0.4.1 behavior (default).
* :class:`SqlUserStore`      — SQLAlchemy-backed (sqlite/postgres).

The classmethods on :class:`UserManager` route to the active backend so
every existing caller (``UserManager.create(...)`` etc.) keeps working.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol


class UserRecord:
    """Lightweight transport record. Distinct from :class:`User` to keep the
    storage layer independent of the public ``User`` class."""

    __slots__ = ("id", "external_id", "metadata", "api_key_hash", "created_at")

    def __init__(
        self,
        id: str,
        external_id: Optional[str],
        metadata: Dict[str, Any],
        api_key_hash: Optional[str],
        created_at: datetime,
    ):
        self.id = id
        self.external_id = external_id
        self.metadata = metadata
        self.api_key_hash = api_key_hash
        self.created_at = created_at


class UserStore(Protocol):
    def create(
        self,
        external_id: Optional[str],
        metadata: Dict[str, Any],
        api_key_hash: Optional[str] = None,
    ) -> UserRecord: ...

    def get(self, user_id: str) -> Optional[UserRecord]: ...

    def get_by_external_id(self, external_id: str) -> Optional[UserRecord]: ...

    def get_by_api_key_hash(self, api_key_hash: str) -> Optional[UserRecord]: ...

    def update_metadata(self, user_id: str, metadata: Dict[str, Any]) -> bool: ...

    def delete(self, user_id: str) -> bool: ...

    def list_all(self) -> List[UserRecord]: ...


class InMemoryUserStore:
    """Preserves v0.4.1 behavior — class-level dict, lost on restart."""

    def __init__(self) -> None:
        self._users: Dict[str, UserRecord] = {}
        self._by_external: Dict[str, str] = {}
        self._by_api_key: Dict[str, str] = {}

    def create(
        self,
        external_id: Optional[str],
        metadata: Dict[str, Any],
        api_key_hash: Optional[str] = None,
    ) -> UserRecord:
        if external_id and external_id in self._by_external:
            return self._users[self._by_external[external_id]]
        import uuid

        user_id = str(uuid.uuid4())
        rec = UserRecord(
            id=user_id,
            external_id=external_id,
            metadata=dict(metadata or {}),
            api_key_hash=api_key_hash,
            created_at=datetime.now(timezone.utc),
        )
        self._users[user_id] = rec
        if external_id:
            self._by_external[external_id] = user_id
        if api_key_hash:
            self._by_api_key[api_key_hash] = user_id
        return rec

    def get(self, user_id: str) -> Optional[UserRecord]:
        return self._users.get(user_id)

    def get_by_external_id(self, external_id: str) -> Optional[UserRecord]:
        uid = self._by_external.get(external_id)
        return self._users.get(uid) if uid else None

    def get_by_api_key_hash(self, api_key_hash: str) -> Optional[UserRecord]:
        uid = self._by_api_key.get(api_key_hash)
        return self._users.get(uid) if uid else None

    def update_metadata(self, user_id: str, metadata: Dict[str, Any]) -> bool:
        rec = self._users.get(user_id)
        if not rec:
            return False
        rec.metadata.update(metadata)
        return True

    def delete(self, user_id: str) -> bool:
        rec = self._users.pop(user_id, None)
        if not rec:
            return False
        if rec.external_id:
            self._by_external.pop(rec.external_id, None)
        if rec.api_key_hash:
            self._by_api_key.pop(rec.api_key_hash, None)
        return True

    def list_all(self) -> List[UserRecord]:
        return list(self._users.values())


class SqlUserStore:
    """SQLAlchemy-backed user store for service mode.

    Auto-creates the ``users`` table on first connect (no Alembic in
    v0.4.2 — added in v0.5 when the second migration arrives).
    Supports sqlite and postgres URLs.
    """

    def __init__(self, url: str):
        try:
            from sqlalchemy import (
                Column,
                DateTime,
                MetaData,
                String,
                Table,
                create_engine,
            )
            from sqlalchemy.dialects.postgresql import JSONB
            from sqlalchemy.types import JSON
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "SqlUserStore requires sqlalchemy. Install with "
                "`pip install 'neuromem-sdk[ui]'`."
            ) from exc

        self._engine = create_engine(url, future=True)
        meta = MetaData()
        json_type = JSONB if url.startswith("postgresql") else JSON
        self._table = Table(
            "neuromem_users",
            meta,
            Column("id", String(64), primary_key=True),
            Column("external_id", String(255), unique=True, nullable=True),
            Column("api_key_hash", String(255), unique=True, nullable=True),
            Column("metadata_json", json_type, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        meta.create_all(self._engine)

    def _row_to_record(self, row: Any) -> UserRecord:
        return UserRecord(
            id=row.id,
            external_id=row.external_id,
            metadata=row.metadata_json or {},
            api_key_hash=row.api_key_hash,
            created_at=row.created_at,
        )

    def create(
        self,
        external_id: Optional[str],
        metadata: Dict[str, Any],
        api_key_hash: Optional[str] = None,
    ) -> UserRecord:
        from sqlalchemy import insert, select
        import uuid

        with self._engine.begin() as conn:
            if external_id:
                existing = conn.execute(
                    select(self._table).where(self._table.c.external_id == external_id)
                ).first()
                if existing is not None:
                    return self._row_to_record(existing)

            user_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            conn.execute(
                insert(self._table).values(
                    id=user_id,
                    external_id=external_id,
                    api_key_hash=api_key_hash,
                    metadata_json=dict(metadata or {}),
                    created_at=now,
                )
            )
            return UserRecord(
                id=user_id,
                external_id=external_id,
                metadata=dict(metadata or {}),
                api_key_hash=api_key_hash,
                created_at=now,
            )

    def get(self, user_id: str) -> Optional[UserRecord]:
        from sqlalchemy import select

        with self._engine.connect() as conn:
            row = conn.execute(select(self._table).where(self._table.c.id == user_id)).first()
            return self._row_to_record(row) if row else None

    def get_by_external_id(self, external_id: str) -> Optional[UserRecord]:
        from sqlalchemy import select

        with self._engine.connect() as conn:
            row = conn.execute(
                select(self._table).where(self._table.c.external_id == external_id)
            ).first()
            return self._row_to_record(row) if row else None

    def get_by_api_key_hash(self, api_key_hash: str) -> Optional[UserRecord]:
        from sqlalchemy import select

        with self._engine.connect() as conn:
            row = conn.execute(
                select(self._table).where(self._table.c.api_key_hash == api_key_hash)
            ).first()
            return self._row_to_record(row) if row else None

    def update_metadata(self, user_id: str, metadata: Dict[str, Any]) -> bool:
        from sqlalchemy import select, update

        with self._engine.begin() as conn:
            row = conn.execute(select(self._table).where(self._table.c.id == user_id)).first()
            if not row:
                return False
            merged = {**(row.metadata_json or {}), **metadata}
            conn.execute(
                update(self._table).where(self._table.c.id == user_id).values(metadata_json=merged)
            )
            return True

    def delete(self, user_id: str) -> bool:
        from sqlalchemy import delete

        with self._engine.begin() as conn:
            result = conn.execute(delete(self._table).where(self._table.c.id == user_id))
            return result.rowcount > 0

    def list_all(self) -> List[UserRecord]:
        from sqlalchemy import select

        with self._engine.connect() as conn:
            rows = conn.execute(select(self._table)).all()
            return [self._row_to_record(r) for r in rows]


def _bcrypt():
    try:
        import bcrypt as _b

        return _b
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "API-key hashing requires bcrypt. Install with " "`pip install 'neuromem-sdk[ui]'`."
        ) from exc


def hash_api_key(plain: str) -> str:
    """Bcrypt hash an API key. Plain key is unrecoverable after this."""
    b = _bcrypt()
    return b.hashpw(plain.encode("utf-8"), b.gensalt(rounds=12)).decode("utf-8")


def verify_api_key(plain: str, hashed: str) -> bool:
    b = _bcrypt()
    try:
        return b.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def generate_api_key() -> str:
    """Return a fresh URL-safe API key (32 bytes, ~43 chars)."""
    return f"nm_{secrets.token_urlsafe(32)}"


__all__ = [
    "UserRecord",
    "UserStore",
    "InMemoryUserStore",
    "SqlUserStore",
    "hash_api_key",
    "verify_api_key",
    "generate_api_key",
]
