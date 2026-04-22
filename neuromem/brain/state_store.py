"""
Brain State persistence via existing storage backend.

Stores BrainState as a JSON blob inside a special MemoryItem with
id ``__brain_state__{user_id}`` and memory_type SEMANTIC.
No new tables or collections required.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from neuromem.brain.types import BrainState
from neuromem.core.types import MemoryItem, MemoryType

logger = logging.getLogger(__name__)

BRAIN_STATE_ID_PREFIX = "__brain_state__"


def _brain_state_id(user_id: str) -> str:
    return f"{BRAIN_STATE_ID_PREFIX}{user_id}"


class BrainStateStore:
    """Persist BrainState using the existing MemoryBackend.

    Parameters
    ----------
    backend:
        Any MemoryBackend implementation (memory, sqlite, postgres, qdrant).
    """

    def __init__(self, backend) -> None:
        self._backend = backend

    def load(self, user_id: str) -> BrainState:
        """Load BrainState from storage, or return a fresh default."""
        state_id = _brain_state_id(user_id)
        try:
            item = self._backend.get_by_id(state_id)
            if item is not None:
                data = json.loads(item.content)
                return BrainState.from_dict(data)
        except Exception:
            logger.debug("No existing brain state for user %s, creating fresh", user_id)
        return BrainState(user_id=user_id)

    def save(self, state: BrainState) -> None:
        """Persist BrainState to storage."""
        state_id = _brain_state_id(state.user_id)
        now = datetime.now(timezone.utc)
        item = MemoryItem(
            id=state_id,
            user_id=state.user_id,
            content=json.dumps(state.to_dict()),
            embedding=[],  # No embedding needed for state storage
            memory_type=MemoryType.SEMANTIC,
            salience=0.0,  # Internal — never returned in retrieval
            confidence=1.0,
            created_at=now,
            last_accessed=now,
            decay_rate=0.0,  # Never decays
            reinforcement=0,
            inferred=True,
            editable=False,
            tags=["__internal__", "__brain_state__"],
            metadata={"internal": True, "brain_state": True},
        )
        try:
            self._backend.upsert(item)
        except Exception:
            logger.warning(
                "Failed to persist brain state for user %s", state.user_id, exc_info=True
            )
