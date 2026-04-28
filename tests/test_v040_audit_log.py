"""
Tests for v0.4.0 audit log infrastructure (RetrievalLog + ObservationLog).
"""

from __future__ import annotations

import threading
from typing import List

import pytest

from neuromem.core.audit import (
    ObservationEvent,
    ObservationLog,
    RetrievalLog,
    RetrievalRun,
    RetrievalStage,
)


class TestRetrievalLogDisabled:
    def test_disabled_by_default(self):
        log = RetrievalLog()
        assert log.enabled is False

    def test_begin_returns_none_when_disabled(self):
        log = RetrievalLog()
        run = log.begin(user_id="u1", query="q", task_type="chat", k=5)
        assert run is None

    def test_zero_overhead_path_no_runs_recorded(self):
        log = RetrievalLog()
        for _ in range(100):
            r = log.begin(user_id="u1", query="q", task_type="chat", k=5)
            log.add_stage(r, RetrievalStage(name="vector_search", elapsed_ms=1.0, candidate_count=10))
            log.finish(r, [])
        assert log.list() == []


class TestRetrievalLogEnabled:
    def setup_method(self):
        self.log = RetrievalLog(capacity=10)
        self.log.enable()

    def test_full_lifecycle_run(self):
        run = self.log.begin(user_id="u1", query="hi", task_type="chat", k=5)
        assert run is not None
        assert run.status == "running"
        self.log.add_stage(
            run, RetrievalStage(name="vector_search", elapsed_ms=2.1, candidate_count=30)
        )
        self.log.add_stage(
            run, RetrievalStage(name="cross_encoder", elapsed_ms=12.5, candidate_count=8)
        )
        self.log.finish(run, [{"id": "m1", "score": 0.9}], confidence=0.8)
        assert run.status == "completed"
        assert len(run.stages) == 2
        assert run.elapsed_ms is not None and run.elapsed_ms >= 0
        assert run.confidence == 0.8

    def test_capacity_eviction(self):
        for i in range(15):
            r = self.log.begin(user_id="u", query=f"q{i}", task_type="chat", k=1)
            self.log.finish(r, [])
        # Capacity=10 → only the last 10 survive.
        runs = self.log.list(limit=100)
        assert len(runs) == 10
        # Most-recent first ordering.
        assert runs[0].query == "q14"
        assert runs[-1].query == "q5"

    def test_get_by_id(self):
        r = self.log.begin(user_id="u", query="x", task_type="chat", k=1)
        self.log.finish(r, [])
        fetched = self.log.get(r.id)
        assert fetched is r

    def test_subscribers_receive_completed_run(self):
        seen: List[RetrievalRun] = []
        unsubscribe = self.log.subscribe(lambda run: seen.append(run))
        r = self.log.begin(user_id="u", query="x", task_type="chat", k=1)
        self.log.finish(r, [])
        assert len(seen) == 1
        assert seen[0] is r
        unsubscribe()

        r2 = self.log.begin(user_id="u", query="y", task_type="chat", k=1)
        self.log.finish(r2, [])
        # After unsubscribe, no new events.
        assert len(seen) == 1

    def test_error_marks_status(self):
        r = self.log.begin(user_id="u", query="x", task_type="chat", k=1)
        self.log.error(r, RuntimeError("bad"))
        assert r.status == "errored"
        assert r.error and "bad" in r.error

    def test_thread_safety_basic(self):
        """Concurrent writers should not corrupt the buffer."""
        def worker(n: int) -> None:
            for i in range(n):
                r = self.log.begin(user_id=f"t{i}", query="q", task_type="chat", k=1)
                self.log.finish(r, [])

        threads = [threading.Thread(target=worker, args=(50,)) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # 4 × 50 = 200 begins, capacity=10 → 10 survive, no exceptions.
        assert len(self.log.list(100)) == 10


class TestObservationLog:
    def setup_method(self):
        self.log = ObservationLog(capacity=5)
        self.log.enable()

    def test_record_and_list(self):
        e = self.log.record(
            user_id="u",
            user_text="hello",
            assistant_text="hi",
            salience=0.7,
            emotional_weight=0.2,
            tags=["greeting"],
            entities=[],
            written_memory_ids=["m1"],
        )
        assert e is not None and e.id
        events = self.log.list()
        assert len(events) == 1
        assert events[0].user_text == "hello"
        assert events[0].salience == 0.7

    def test_disabled_record_returns_none(self):
        log = ObservationLog()
        assert log.record(user_id="u", user_text="x", assistant_text="y") is None
        assert log.list() == []

    def test_capacity_eviction(self):
        for i in range(8):
            self.log.record(user_id="u", user_text=f"t{i}", assistant_text="a")
        events = self.log.list(100)
        assert len(events) == 5  # capacity
        assert events[0].user_text == "t7"

    def test_subscriber_callback_fires(self):
        seen: List[ObservationEvent] = []
        unsubscribe = self.log.subscribe(lambda e: seen.append(e))
        self.log.record(user_id="u", user_text="x", assistant_text="y")
        assert len(seen) == 1
        unsubscribe()
        self.log.record(user_id="u", user_text="x2", assistant_text="y2")
        assert len(seen) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
