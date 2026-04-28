"""
Observation audit log — captures every ``MemoryController.observe()`` call
as an ``ObservationEvent`` for the UI's live feed.

An ``ObservationEvent`` records the inputs (user / assistant text), the
derived signals (template, tags, salience, emotional weight, flashbulb
flag, extracted entities, sparse code from DG), and which memory IDs were
written. The UI subscribes via SSE so a watcher sees the brain "think" in
real time as the agent observes turns.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Callable, List, Optional


@dataclass
class ObservationEvent:
    id: str
    user_id: str
    timestamp: float  # epoch seconds
    user_text: str
    assistant_text: str
    template: Optional[str] = None
    salience: Optional[float] = None
    emotional_weight: Optional[float] = None
    arousal: Optional[float] = None
    valence: Optional[float] = None
    flashbulb: bool = False
    tags: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    written_memory_ids: List[str] = field(default_factory=list)
    written_verbatim_chunk_ids: List[str] = field(default_factory=list)
    elapsed_ms: Optional[float] = None
    notes: dict = field(default_factory=dict)
    """Free-form: brain.region tags ('hippocampus_ingest', 'amygdala_flashbulb'),
    consolidation triggered, etc."""

    def to_dict(self) -> dict:
        return asdict(self)


class ObservationLog:
    """Thread-safe ring-buffer of ``ObservationEvent`` records."""

    def __init__(self, capacity: int = 1000) -> None:
        self._capacity = capacity
        self._buf: deque[ObservationEvent] = deque(maxlen=capacity)
        self._lock = threading.RLock()
        self._enabled = False
        self._subscribers: List[Callable[[ObservationEvent], None]] = []

    # -- lifecycle ----------------------------------------------------

    def enable(self) -> None:
        with self._lock:
            self._enabled = True

    def disable(self) -> None:
        with self._lock:
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    # -- write side ---------------------------------------------------

    def record(
        self,
        *,
        user_id: str,
        user_text: str,
        assistant_text: str,
        template: Optional[str] = None,
        salience: Optional[float] = None,
        emotional_weight: Optional[float] = None,
        arousal: Optional[float] = None,
        valence: Optional[float] = None,
        flashbulb: bool = False,
        tags: Optional[List[str]] = None,
        entities: Optional[List[str]] = None,
        written_memory_ids: Optional[List[str]] = None,
        written_verbatim_chunk_ids: Optional[List[str]] = None,
        elapsed_ms: Optional[float] = None,
        notes: Optional[dict] = None,
    ) -> Optional[ObservationEvent]:
        """Record an observation event. Returns the event, or ``None`` when
        audit is disabled."""
        if not self._enabled:
            return None
        event = ObservationEvent(
            id=uuid.uuid4().hex,
            user_id=user_id,
            timestamp=time.time(),
            user_text=user_text,
            assistant_text=assistant_text,
            template=template,
            salience=salience,
            emotional_weight=emotional_weight,
            arousal=arousal,
            valence=valence,
            flashbulb=flashbulb,
            tags=list(tags or []),
            entities=list(entities or []),
            written_memory_ids=list(written_memory_ids or []),
            written_verbatim_chunk_ids=list(written_verbatim_chunk_ids or []),
            elapsed_ms=elapsed_ms,
            notes=dict(notes or {}),
        )
        with self._lock:
            self._buf.append(event)
            subs = list(self._subscribers)
        for sub in subs:
            try:
                sub(event)
            except Exception:  # pragma: no cover
                pass
        return event

    # -- read side ----------------------------------------------------

    def list(self, limit: int = 100) -> List[ObservationEvent]:
        with self._lock:
            return list(reversed(list(self._buf)))[:limit]

    def subscribe(self, callback: Callable[[ObservationEvent], None]) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(callback)

        def _unsubscribe() -> None:
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return _unsubscribe


default_log = ObservationLog()
