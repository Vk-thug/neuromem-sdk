"""
User lifecycle management for NeuroMem SDK.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, Any


class User:
    """
    Represents a user in the NeuroMem system.

    Attributes:
        id: System-generated unique user ID
        external_id: External identifier (e.g., from auth system)
        metadata: Additional user metadata
        created_at: When the user was created
    """

    def __init__(
        self,
        user_id: str,
        external_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
    ):
        self.id = user_id
        self.external_id = external_id
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.now(timezone.utc)

    def to_dict(self):
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "external_id": self.external_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Create from dictionary."""
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
    """
    Manages user lifecycle operations.

    This is a simple in-memory implementation. In production, this would
    interface with a database to persist user records.
    """

    _users: Dict[str, User] = {}
    _external_id_index: Dict[str, str] = {}

    @classmethod
    def create(cls, external_id: str, metadata: Optional[Dict[str, Any]] = None) -> User:
        """
        Create a new user.

        Args:
            external_id: External identifier (e.g., from auth system)
            metadata: Additional user metadata (e.g., role, preferences)

        Returns:
            User object with system-generated ID

        Example:
            >>> user = UserManager.create(
            ...     external_id="auth_123",
            ...     metadata={"role": "developer"}
            ... )
            >>> user_id = user.id
        """
        # Check if user already exists
        if external_id in cls._external_id_index:
            existing_user_id = cls._external_id_index[external_id]
            return cls._users[existing_user_id]

        # Create new user
        user_id = str(uuid.uuid4())
        user = User(user_id=user_id, external_id=external_id, metadata=metadata)

        cls._users[user_id] = user
        cls._external_id_index[external_id] = user_id

        return user

    @classmethod
    def get(cls, user_id: str) -> Optional[User]:
        """
        Get a user by ID.

        Args:
            user_id: System-generated user ID

        Returns:
            User object or None if not found
        """
        return cls._users.get(user_id)

    @classmethod
    def get_by_external_id(cls, external_id: str) -> Optional[User]:
        """
        Get a user by external ID.

        Args:
            external_id: External identifier

        Returns:
            User object or None if not found
        """
        user_id = cls._external_id_index.get(external_id)
        if user_id:
            return cls._users.get(user_id)
        return None

    @classmethod
    def update_metadata(cls, user_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Update user metadata.

        Args:
            user_id: System-generated user ID
            metadata: New metadata to merge with existing

        Returns:
            True if successful, False if user not found
        """
        user = cls._users.get(user_id)
        if user:
            user.metadata.update(metadata)
            return True
        return False

    @classmethod
    def delete(cls, user_id: str) -> bool:
        """
        Delete a user.

        Args:
            user_id: System-generated user ID

        Returns:
            True if successful, False if user not found
        """
        user = cls._users.get(user_id)
        if user:
            if user.external_id:
                del cls._external_id_index[user.external_id]
            del cls._users[user_id]
            return True
        return False

    @classmethod
    def list_all(cls):
        """
        List all users.

        Returns:
            List of User objects
        """
        return list(cls._users.values())
