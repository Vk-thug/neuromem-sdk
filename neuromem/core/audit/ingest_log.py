"""
Knowledge-base ingest audit log — same shape as ``RetrievalLog`` but
tracks file-upload jobs from start to written-chunk completion.

An ``IngestJob`` records the source file, the parser used, per-stage
progress (parse / embed / write / link), per-chunk telemetry, and any
errors. Subscribers wire into the UI's SSE stream so an upload bar
updates live as Docling streams chunks.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Callable, List, Optional


@dataclass
class IngestStage:
    """One stage event within an ingest job (one chunk parsed,
    embedded, written, etc.)."""

    name: str
    """``parse_chunk`` | ``embed_chunk`` | ``write_chunk`` | ``link_chunk`` | ``error``"""
    elapsed_ms: float
    chunk_index: Optional[int] = None
    notes: dict = field(default_factory=dict)


@dataclass
class IngestJob:
    id: str
    user_id: str
    source_path: str
    source_id: str
    parser_name: str
    started_at: float
    finished_at: Optional[float] = None
    elapsed_ms: Optional[float] = None
    status: str = "running"  # "running" | "completed" | "errored" | "cancelled"
    error: Optional[str] = None
    parsed_chunks: int = 0
    written_chunks: int = 0
    written_memory_ids: List[str] = field(default_factory=list)
    written_verbatim_chunk_ids: List[str] = field(default_factory=list)
    stages: List[IngestStage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class IngestLog:
    """Thread-safe ring-buffer of ``IngestJob`` records.

    Mirrors :class:`RetrievalLog` semantics: ``begin()`` to start,
    ``add_stage()`` per stage, ``finish()`` (or ``error()``) to close.
    Subscribers fire on every state transition so the UI sees a job
    progress smoothly rather than only on completion.
    """

    def __init__(self, capacity: int = 200) -> None:
        self._capacity = capacity
        self._buf: deque[IngestJob] = deque(maxlen=capacity)
        self._lock = threading.RLock()
        self._enabled = False
        self._subscribers: List[Callable[[IngestJob], None]] = []
        self._index: dict[str, IngestJob] = {}

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

    def begin(
        self,
        *,
        user_id: str,
        source_path: str,
        source_id: str,
        parser_name: str,
    ) -> Optional[IngestJob]:
        if not self._enabled:
            return None
        job = IngestJob(
            id=uuid.uuid4().hex,
            user_id=user_id,
            source_path=source_path,
            source_id=source_id,
            parser_name=parser_name,
            started_at=time.time(),
        )
        with self._lock:
            self._buf.append(job)
            self._index[job.id] = job
            if len(self._index) > self._capacity * 2:
                live_ids = {j.id for j in self._buf}
                self._index = {k: v for k, v in self._index.items() if k in live_ids}
        self._notify(job)
        return job

    def add_stage(self, job: Optional[IngestJob], stage: IngestStage) -> None:
        if job is None:
            return
        with self._lock:
            job.stages.append(stage)
            if stage.name == "parse_chunk":
                job.parsed_chunks += 1
            elif stage.name == "write_chunk":
                job.written_chunks += 1
        self._notify(job)

    def record_write(
        self,
        job: Optional[IngestJob],
        *,
        memory_id: Optional[str] = None,
        verbatim_chunk_id: Optional[str] = None,
    ) -> None:
        if job is None:
            return
        with self._lock:
            if memory_id:
                job.written_memory_ids.append(memory_id)
            if verbatim_chunk_id:
                job.written_verbatim_chunk_ids.append(verbatim_chunk_id)

    def finish(
        self,
        job: Optional[IngestJob],
        *,
        status: str = "completed",
    ) -> None:
        if job is None:
            return
        now = time.time()
        with self._lock:
            job.finished_at = now
            job.elapsed_ms = (now - job.started_at) * 1000.0
            job.status = status
        self._notify(job)

    def error(self, job: Optional[IngestJob], exc: BaseException) -> None:
        if job is None:
            return
        now = time.time()
        with self._lock:
            job.finished_at = now
            job.elapsed_ms = (now - job.started_at) * 1000.0
            job.status = "errored"
            job.error = f"{type(exc).__name__}: {exc}"
        self._notify(job)

    def cancel(self, job_id: str) -> bool:
        """Mark a job as cancelled. Cooperative — the ingester checks
        ``job.status == 'running'`` between chunks and exits cleanly."""
        with self._lock:
            job = self._index.get(job_id)
            if job is None or job.status != "running":
                return False
            job.status = "cancelled"
            job.finished_at = time.time()
            job.elapsed_ms = (job.finished_at - job.started_at) * 1000.0
        self._notify(job)
        return True

    # -- read side ----------------------------------------------------

    def list(self, limit: int = 100) -> List[IngestJob]:
        with self._lock:
            return list(reversed(list(self._buf)))[:limit]

    def get(self, job_id: str) -> Optional[IngestJob]:
        with self._lock:
            return self._index.get(job_id)

    def subscribe(self, callback: Callable[[IngestJob], None]) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(callback)

        def _unsubscribe() -> None:
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return _unsubscribe

    # -- internals ----------------------------------------------------

    def _notify(self, job: IngestJob) -> None:
        with self._lock:
            subs = list(self._subscribers)
        for sub in subs:
            try:
                sub(job)
            except Exception:  # pragma: no cover
                pass


default_log = IngestLog()
