"""User lifecycle management for NeuroMem SDK.

v0.4.2: ``UserManager`` is now a thin facade over a pluggable
:class:`neuromem.user_store.UserStore`. The default backend remains the
in-memory dict (preserving v0.4.1 behavior), and service mode swaps in
:class:`SqlUserStore` at boot via :meth:`UserManager.configure`.

Existing callers continue to use the classmethod API
(``UserManager.create(...)``, ``UserManager.get(...)``) unchanged.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from neuromem.user_store import (
    InMemoryUserStore,
    UserRecord,
    UserStore,
    generate_api_key,
    hash_api_key,
)


class User:
    """Public user record exposed to SDK consumers.

    Wraps :class:`neuromem.user_store.UserRecord`. Equivalent in shape to
    the v0.4.1 ``User`` class — the only addition is ``api_key_hash``,
    populated when service mode mints a key.
    """

    def __init__(
        self,
        user_id: str,
        external_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        api_key_hash: Optional[str] = None,
    ):
        self.id = user_id
        self.external_id = external_id
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.now(timezone.utc)
        self.api_key_hash = api_key_hash

    @classmethod
    def from_record(cls, rec: UserRecord) -> "User":
        return cls(
            user_id=rec.id,
            external_id=rec.external_id,
            metadata=rec.metadata,
            created_at=rec.created_at,
            api_key_hash=rec.api_key_hash,
        )

    def to_dict(self):
        return {
            "id": self.id,
            "external_id": self.external_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            user_id=data["id"],
            external_id=data.get("external_id"),
            metadata=data.get("metadata", {}),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if isinstance(data.get("created_at"), str)
                else data.get("created_at")
            ),
        )


class UserManager:
    """Facade over a pluggable :class:`UserStore`.

    Default backend is :class:`InMemoryUserStore`. Call
    :meth:`UserManager.configure` at boot to swap to
    :class:`SqlUserStore` for service mode.
    """

    _backend: UserStore = InMemoryUserStore()

    @classmethod
    def configure(cls, backend: UserStore) -> None:
        """Replace the active backend (called once at server startup)."""
        cls._backend = backend

    @classmethod
    def reset(cls) -> None:
        """Reset to a fresh in-memory backend. Test-only convenience."""
        cls._backend = InMemoryUserStore()

    @classmethod
    def create(
        cls,
        external_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> User:
        rec = cls._backend.create(external_id=external_id, metadata=dict(metadata or {}))
        return User.from_record(rec)

    @classmethod
    def create_with_api_key(
        cls,
        external_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> tuple[User, str]:
        """Create a user and mint a one-time API key.

        Returns ``(user, plain_api_key)``. The plaintext key is shown to
        the caller exactly once — only the bcrypt hash is persisted.
        """
        plain = generate_api_key()
        rec = cls._backend.create(
            external_id=external_id,
            metadata=dict(metadata or {}),
            api_key_hash=hash_api_key(plain),
        )
        return User.from_record(rec), plain

    @classmethod
    def get(cls, user_id: str) -> Optional[User]:
        rec = cls._backend.get(user_id)
        return User.from_record(rec) if rec else None

    @classmethod
    def get_by_external_id(cls, external_id: str) -> Optional[User]:
        rec = cls._backend.get_by_external_id(external_id)
        return User.from_record(rec) if rec else None

    @classmethod
    def get_by_api_key(cls, plain_key: str) -> Optional[User]:
        """Look up a user by plaintext API key (bcrypt-verified).

        Note: this iterates active users; for high-volume service mode
        consider an indexed lookup table on a key prefix in v0.5.
        """
        from neuromem.user_store import verify_api_key

        for rec in cls._backend.list_all():
            if rec.api_key_hash and verify_api_key(plain_key, rec.api_key_hash):
                return User.from_record(rec)
        return None

    @classmethod
    def update_metadata(cls, user_id: str, metadata: Dict[str, Any]) -> bool:
        return cls._backend.update_metadata(user_id, metadata)

    @classmethod
    def delete(cls, user_id: str) -> bool:
        return cls._backend.delete(user_id)

    @classmethod
    def list_all(cls) -> List[User]:
        return [User.from_record(r) for r in cls._backend.list_all()]
