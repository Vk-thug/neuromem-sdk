"""
Retrieval audit log — captures every ``MemoryController.retrieve()`` call as
a structured ``RetrievalRun`` for the UI's Inngest-style run inspector.

A ``RetrievalRun`` is composed of ``RetrievalStage`` records — one per
pipeline step (vector search, hybrid boosts, BM25 blend, cross-encoder
rerank, LLM rerank, conflict resolution, brain gating). Each stage records
the candidates it saw and the score it produced, so the UI can render the
end-to-end cause-and-effect chain for any single retrieval.

Thread-safe ring buffer (`collections.deque(maxlen=...)`) — bounded memory.
Default cap 1000 runs (~few MB given typical k=8). Subscribers register
``on_run`` callbacks for SSE streaming to the UI.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Callable, Iterable, List, Optional


@dataclass
class RetrievalStage:
    """A single stage within a retrieval run.

    ``name`` is one of: ``vector_search``, ``hybrid_boosts``, ``bm25_blend``,
    ``cross_encoder``, ``llm_rerank``, ``conflict_resolution``,
    ``brain_gating``, ``graph_expansion``, ``keyword_fallback``,
    ``multihop_decomposition``, ``rrf_merge``.
    """

    name: str
    elapsed_ms: float
    candidate_count: int
    top_candidates: List[dict] = field(default_factory=list)
    """List of ``{memory_id, score, content_excerpt}`` for the top-K shown
    in the UI. Capped to keep run-payload size bounded."""
    notes: dict = field(default_factory=dict)
    """Stage-specific extras: BM25 blend weight, CE blend, conflict-deprecate
    decision, brain gate score, etc."""


@dataclass
class RetrievalRun:
    """End-to-end record of one ``retrieve()`` call.

    The ``id`` is a ULID-shaped hex; ``status`` reflects whether the
    pipeline ran cleanly or fell through to keyword fallback / errored out.
    """

    id: str
    user_id: str
    query: str
    task_type: str
    k: int
    started_at: float  # epoch seconds
    finished_at: Optional[float] = None
    elapsed_ms: Optional[float] = None
    embedding_dim: Optional[int] = None
    embedding_hash: Optional[str] = None
    status: str = "running"  # "running" | "completed" | "errored" | "fallback"
    error: Optional[str] = None
    stages: List[RetrievalStage] = field(default_factory=list)
    final_results: List[dict] = field(default_factory=list)
    abstained: bool = False
    abstention_reason: Optional[str] = None
    confidence: float = 1.0

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


class RetrievalLog:
    """Thread-safe ring-buffer of ``RetrievalRun`` records.

    Use ``begin()`` to start a new run, then ``add_stage()`` per stage, then
    ``finish()`` (or ``error()``). Subscribers via ``subscribe()`` get a
    callback per run completion — wired to the UI's SSE stream.

    Defaults: capacity 1000, ``enabled`` flag off until ``RetrievalLog.enable()``
    is called (``neuromem ui`` flips it on at process start). Off-by-default
    means the ``observe`` / ``retrieve`` hot path adds zero overhead in
    production until the UI is running.
    """

    def __init__(self, capacity: int = 1000) -> None:
        self._capacity = capacity
        self._buf: deque[RetrievalRun] = deque(maxlen=capacity)
        self._lock = threading.RLock()
        self._enabled = False
        self._subscribers: List[Callable[[RetrievalRun], None]] = []
        self._index: dict[str, RetrievalRun] = {}  # run_id → run

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
        user_id: str,
        query: str,
        task_type: str,
        k: int,
        embedding_dim: Optional[int] = None,
        embedding_hash: Optional[str] = None,
    ) -> Optional[RetrievalRun]:
        """Start a new run. Returns ``None`` when audit is disabled —
        callers must null-check (the controller wraps every audit call so
        the hot path stays branch-cheap)."""
        if not self._enabled:
            return None
        run = RetrievalRun(
            id=uuid.uuid4().hex,
            user_id=user_id,
            query=query,
            task_type=task_type,
            k=k,
            started_at=time.time(),
            embedding_dim=embedding_dim,
            embedding_hash=embedding_hash,
        )
        with self._lock:
            self._buf.append(run)
            self._index[run.id] = run
            # Maintain index size: drop entries whose runs were evicted
            # from the deque. Cheap because deque tracks order.
            if len(self._index) > self._capacity * 2:
                live_ids = {r.id for r in self._buf}
                self._index = {k: v for k, v in self._index.items() if k in live_ids}
        return run

    def add_stage(self, run: Optional[RetrievalRun], stage: RetrievalStage) -> None:
        if run is None:
            return
        with self._lock:
            run.stages.append(stage)

    def finish(
        self,
        run: Optional[RetrievalRun],
        final_results: Iterable[dict],
        *,
        status: str = "completed",
        confidence: float = 1.0,
        abstained: bool = False,
        abstention_reason: Optional[str] = None,
    ) -> None:
        if run is None:
            return
        now = time.time()
        with self._lock:
            run.finished_at = now
            run.elapsed_ms = (now - run.started_at) * 1000.0
            run.status = status
            run.final_results = list(final_results)
            run.confidence = confidence
            run.abstained = abstained
            run.abstention_reason = abstention_reason
            subs = list(self._subscribers)
        # Fire subscribers outside the lock to avoid deadlock in callbacks.
        for sub in subs:
            try:
                sub(run)
            except Exception:  # pragma: no cover - subscriber hygiene
                pass

    def error(self, run: Optional[RetrievalRun], exc: BaseException) -> None:
        if run is None:
            return
        with self._lock:
            run.finished_at = time.time()
            run.elapsed_ms = (run.finished_at - run.started_at) * 1000.0
            run.status = "errored"
            run.error = f"{type(exc).__name__}: {exc}"

    # -- read side ----------------------------------------------------

    def list(self, limit: int = 100) -> List[RetrievalRun]:
        with self._lock:
            # Most-recent first.
            return list(reversed(list(self._buf)))[:limit]

    def get(self, run_id: str) -> Optional[RetrievalRun]:
        with self._lock:
            return self._index.get(run_id)

    def subscribe(self, callback: Callable[[RetrievalRun], None]) -> Callable[[], None]:
        """Register a callback fired on every ``finish()``. Returns an
        unsubscribe function."""
        with self._lock:
            self._subscribers.append(callback)

        def _unsubscribe() -> None:
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return _unsubscribe


# Process-wide singleton. The controller imports this and conditionally
# writes to it. The UI server imports this and reads from it.
default_log = RetrievalLog()
