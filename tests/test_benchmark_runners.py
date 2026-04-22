"""
Tests for new benchmark runners, metrics, loaders, and adapters.

Tests use mock adapters to avoid external dependencies (ChromaDB, HuggingFace).
"""

import pytest

from benchmarks.adapters.base import SearchResult
from benchmarks.evaluators.metrics import (
    RetrievalBenchmarkMetrics,
    ndcg_at_k,
    recall_all_at_k,
    recall_at_k,
    recall_fraction_at_k,
)


# ── Retrieval Metrics ──


class TestRecallAtK:
    def test_hit_at_top(self) -> None:
        assert recall_at_k(["a", "b", "c"], {"a"}, k=1) == 1.0

    def test_hit_at_k(self) -> None:
        assert recall_at_k(["x", "y", "a"], {"a"}, k=3) == 1.0

    def test_miss(self) -> None:
        assert recall_at_k(["x", "y", "z"], {"a"}, k=3) == 0.0

    def test_empty_relevant(self) -> None:
        assert recall_at_k(["a", "b"], set(), k=3) == 1.0

    def test_empty_retrieved(self) -> None:
        assert recall_at_k([], {"a"}, k=3) == 0.0

    def test_k_exceeds_retrieved(self) -> None:
        assert recall_at_k(["a"], {"a"}, k=10) == 1.0


class TestRecallAllAtK:
    def test_all_found(self) -> None:
        assert recall_all_at_k(["a", "b", "c"], {"a", "b"}, k=3) == 1.0

    def test_partial_found(self) -> None:
        assert recall_all_at_k(["a", "x", "y"], {"a", "b"}, k=3) == 0.0

    def test_empty_relevant(self) -> None:
        assert recall_all_at_k(["a"], set(), k=3) == 1.0


class TestRecallFractionAtK:
    def test_all_found(self) -> None:
        assert recall_fraction_at_k(["a", "b", "c"], {"a", "b"}, k=3) == 1.0

    def test_half_found(self) -> None:
        assert recall_fraction_at_k(["a", "x", "y"], {"a", "b"}, k=3) == 0.5

    def test_none_found(self) -> None:
        assert recall_fraction_at_k(["x", "y", "z"], {"a", "b"}, k=3) == 0.0


class TestNDCGAtK:
    def test_perfect_ranking(self) -> None:
        assert ndcg_at_k(["a", "b", "c"], {"a"}, k=3) == 1.0

    def test_worst_ranking(self) -> None:
        result = ndcg_at_k(["x", "y", "a"], {"a"}, k=3)
        assert 0.0 < result < 1.0

    def test_no_relevant(self) -> None:
        assert ndcg_at_k(["x", "y", "z"], {"a"}, k=3) == 0.0

    def test_empty_relevant_set(self) -> None:
        # No relevant items means IDCG=0, should return 0.0
        assert ndcg_at_k(["a", "b"], set(), k=3) == 0.0

    def test_multiple_relevant(self) -> None:
        # Both relevant items at top = perfect NDCG
        assert ndcg_at_k(["a", "b", "x"], {"a", "b"}, k=3) == 1.0


class TestRetrievalBenchmarkMetrics:
    def test_add_result(self) -> None:
        m = RetrievalBenchmarkMetrics(system_name="test", benchmark_name="test")
        m.add_result(["a", "b"], {"a"}, k_values=(1, 5), category="cat1")
        assert m.total_questions == 1
        assert m.avg_recall_any(1) == 1.0
        assert m.avg_recall_any(5) == 1.0

    def test_multiple_results(self) -> None:
        m = RetrievalBenchmarkMetrics(system_name="test", benchmark_name="test")
        m.add_result(["a", "b"], {"a"}, k_values=(1, 5))
        m.add_result(["x", "y"], {"a"}, k_values=(1, 5))
        assert m.total_questions == 2
        assert m.avg_recall_any(1) == 0.5

    def test_category_tracking(self) -> None:
        m = RetrievalBenchmarkMetrics(system_name="test", benchmark_name="test")
        m.add_result(["a"], {"a"}, k_values=(1,), category="temporal")
        m.add_result(["x"], {"a"}, k_values=(1,), category="temporal")
        m.add_result(["a"], {"a"}, k_values=(1,), category="factual")
        assert m.category_avg_recall("temporal", 1) == 0.5
        assert m.category_avg_recall("factual", 1) == 1.0

    def test_to_dict(self) -> None:
        m = RetrievalBenchmarkMetrics(system_name="sys", benchmark_name="bench")
        m.add_result(["a"], {"a"}, k_values=(1, 5), category="cat")
        d = m.to_dict()
        assert d["system"] == "sys"
        assert d["benchmark"] == "bench"
        assert "R@1" in d
        assert "R@5" in d
        assert "NDCG@1" in d
        assert "categories" in d

    def test_latency_tracking(self) -> None:
        m = RetrievalBenchmarkMetrics(system_name="test", benchmark_name="test")
        m.latencies_store_ms.extend([10.0, 20.0, 30.0])
        m.latencies_search_ms.extend([5.0, 15.0])
        assert m.avg_store_latency_ms == 20.0
        assert m.avg_search_latency_ms == 10.0


# ── Dataset Loaders (unit tests, no network) ──


class TestLongMemEvalLoader:
    def test_import(self) -> None:
        from benchmarks.datasets.longmemeval_loader import (
            QUESTION_TYPES,
            HaystackSession,
            LongMemEvalEntry,
        )
        assert len(QUESTION_TYPES) == 6
        # Verify frozen dataclass
        s = HaystackSession(session_id="s1", date="2023-01-01", turns=())
        assert s.session_id == "s1"
        e = LongMemEvalEntry(
            question_id="q1",
            question="test?",
            question_type="multi-session",
            question_date="2023/01/15",
            answer="answer",
            answer_session_ids=frozenset({"s1"}),
            haystack_sessions=(s,),
        )
        assert e.question_type == "multi-session"


class TestConvoMemLoader:
    def test_import(self) -> None:
        from benchmarks.datasets.convomem_loader import (
            CATEGORIES,
            ConvoMemEntry,
            ConvoMemMessage,
        )
        assert len(CATEGORIES) == 6
        msg = ConvoMemMessage(speaker="user", text="hello")
        assert msg.speaker == "user"

    def test_categories(self) -> None:
        from benchmarks.datasets.convomem_loader import CATEGORIES

        assert "user_evidence" in CATEGORIES
        assert "preference_evidence" in CATEGORIES


class TestMemBenchLoader:
    def test_import(self) -> None:
        from benchmarks.datasets.membench_loader import (
            TASK_FILES,
            MemBenchEntry,
            MemBenchQA,
            MemBenchTurn,
        )
        assert len(TASK_FILES) == 11
        turn = MemBenchTurn(
            user_text="hi",
            assistant_text="hello",
            timestamp="2024-01-01",
            session_id=1,
            turn_index=0,
            session_index=0,
            global_index=0,
        )
        assert turn.session_id == 1


# ── MemPalace Adapter ──


def _chromadb_available() -> bool:
    try:
        import chromadb  # noqa: F401
        return True
    except ImportError:
        return False


class TestMemPalaceAdapter:
    def test_import_and_protocol(self) -> None:
        from benchmarks.adapters.mempalace_adapter import MemPalaceAdapter

        adapter = MemPalaceAdapter()
        assert adapter.name == "MemPalace (ChromaDB)"

    @pytest.mark.skipif(
        not _chromadb_available(),
        reason="chromadb not installed",
    )
    def test_basic_operations(self) -> None:
        from benchmarks.adapters.mempalace_adapter import MemPalaceAdapter

        adapter = MemPalaceAdapter()
        adapter.setup({})

        # Add memory
        mid = adapter.add_memory("u1", "The capital of France is Paris")
        assert isinstance(mid, str)
        assert adapter.memory_count("u1") == 1

        # Search
        results = adapter.search("u1", "What is the capital of France?", k=1)
        assert len(results) == 1
        assert "Paris" in results[0].content

        # Clear
        adapter.clear("u1")
        assert adapter.memory_count("u1") == 0

        adapter.teardown()


# ── Runner Logic (with mock adapter) ──


class MockAdapter:
    """Minimal adapter for testing runner logic without external deps."""

    def __init__(self) -> None:
        self._memories: dict[str, list[tuple[str, str, dict]]] = {}

    @property
    def name(self) -> str:
        return "MockAdapter"

    def setup(self, config: dict) -> None:
        pass

    def add_memory(
        self, user_id: str, content: str, metadata: dict | None = None
    ) -> str:
        import uuid

        mid = str(uuid.uuid4())
        self._memories.setdefault(user_id, []).append((mid, content, metadata or {}))
        return mid

    def search(
        self, user_id: str, query: str, k: int = 5
    ) -> list[SearchResult]:
        """Return all stored memories as search results (simple substring match)."""
        memories = self._memories.get(user_id, [])
        results = []
        query_lower = query.lower()
        for mid, content, meta in memories:
            # Simple relevance: count query word overlap
            score = sum(
                1 for w in query_lower.split() if w in content.lower()
            ) / max(len(query_lower.split()), 1)
            results.append(SearchResult(
                content=content,
                score=score,
                memory_id=mid,
                metadata=meta,
            ))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:k]

    def get_all(self, user_id: str) -> list[SearchResult]:
        return [
            SearchResult(content=c, score=1.0, memory_id=mid, metadata=meta)
            for mid, c, meta in self._memories.get(user_id, [])
        ]

    def clear(self, user_id: str) -> None:
        self._memories.pop(user_id, None)

    def teardown(self) -> None:
        self._memories.clear()

    def memory_count(self, user_id: str) -> int:
        return len(self._memories.get(user_id, []))


class TestLongMemEvalRunner:
    def test_build_session_doc(self) -> None:
        from benchmarks.runners.longmemeval_runner import _build_session_doc

        turns = (
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        )
        # User only
        doc = _build_session_doc(turns, user_only=True)
        assert "Hello" in doc
        assert "How are you?" in doc
        assert "Hi there" not in doc

        # All turns
        doc = _build_session_doc(turns, user_only=False)
        assert "Hi there" in doc

    def test_resolve_session_ids(self) -> None:
        from benchmarks.runners.longmemeval_runner import _resolve_session_ids

        results = [
            SearchResult(content="a", score=0.9, memory_id="m1", metadata={"corpus_id": "s1"}),
            SearchResult(content="b", score=0.8, memory_id="m2", metadata={"corpus_id": "s2"}),
            SearchResult(content="c", score=0.7, memory_id="m3", metadata={"corpus_id": "s1"}),
        ]
        resolved = _resolve_session_ids(results, {})
        assert resolved == ["s1", "s2"]  # s1 deduped


class TestConvoMemRunner:
    def test_evidence_match(self) -> None:
        from benchmarks.runners.convomem_runner import _evidence_match

        assert _evidence_match("hello world", "I said hello world today") is True
        assert _evidence_match("hello", "goodbye") is False
        assert _evidence_match("", "anything") is False

    def test_compute_recall(self) -> None:
        from benchmarks.runners.convomem_runner import _compute_recall

        # All evidence found
        assert _compute_recall(
            ("hello world",), ["I said hello world today"]
        ) == 1.0

        # No evidence found
        assert _compute_recall(
            ("hello world",), ["goodbye everyone"]
        ) == 0.0

        # Empty evidence
        assert _compute_recall((), ["anything"]) == 1.0


class TestMemBenchRunner:
    def test_get_target_sids(self) -> None:
        from benchmarks.datasets.membench_loader import MemBenchQA
        from benchmarks.runners.membench_runner import _get_target_sids, MemBenchEntry

        # target_step_id format: [[turn_sid, session_idx], ...]
        # Only the FIRST element is the actual target turn SID.
        entry = MemBenchEntry(
            entry_id="test",
            task_name="simple",
            turns=(),
            qa=MemBenchQA(
                question="test?",
                choices={"A": "a", "B": "b"},
                ground_truth="A",
                target_step_ids=((1, 2), (5,)),
            ),
        )
        sids = _get_target_sids(entry)
        # (1, 2) -> 1 (session_idx 2 is NOT a target sid)
        # (5,) -> 5
        assert sids == {1, 5}

    def test_check_hit(self) -> None:
        from benchmarks.runners.membench_runner import _check_hit

        results = [
            SearchResult(content="a", score=0.9, memory_id="m1", metadata={"sid": 3}),
            SearchResult(content="b", score=0.8, memory_id="m2", metadata={"sid": 5}),
        ]
        assert _check_hit(results, {}, {5}, k=2) is True
        assert _check_hit(results, {}, {99}, k=2) is False
        assert _check_hit(results, {}, {5}, k=1) is False  # sid=5 is at position 2

    def test_extract_real_question_clarify_marker(self) -> None:
        """Concatenated 'clarify is,' marker — no space before real question."""
        from benchmarks.runners.membench_runner import _extract_real_question

        q = (
            "I was thinking about going for a hike this weekend. "
            "Did you see the weather forecast? "
            "What was that restaurant we talked about last week?"
            "Oh, what I truly wanted to clarify is,"
            "What position does someone who has rock climbing as a hobby hold?"
        )
        extracted = _extract_real_question(q)
        assert extracted == (
            "What position does someone who has rock climbing as a hobby hold?"
        )

    def test_extract_real_question_wait_minute_marker(self) -> None:
        """'wait a minute, what I wanted to ask is,' — bare marker + connective."""
        from benchmarks.runners.membench_runner import _extract_real_question

        q = (
            "I wonder if I left the oven on earlier. "
            "I can't recall if I sent that report."
            "Wait a minute, what I wanted to ask is,"
            "What's the name of the person who has a hobby of model making?"
        )
        extracted = _extract_real_question(q)
        assert extracted == (
            "What's the name of the person who has a hobby of model making?"
        )

    def test_extract_real_question_oops_actually_was(self) -> None:
        """'Oops, actually what I wanted to ask was:' — leading colon cleanup."""
        from benchmarks.runners.membench_runner import _extract_real_question

        q = (
            "I spoke to someone about a project. Did I leave the oven on?"
            "Oops, actually what I wanted to ask was: "
            "What is the occupation of the person with the contact number 31009417649?"
        )
        extracted = _extract_real_question(q)
        assert extracted == (
            "What is the occupation of the person with the contact number 31009417649?"
        )

    def test_extract_real_question_no_marker(self) -> None:
        """When no marker is present, return the original."""
        from benchmarks.runners.membench_runner import _extract_real_question

        q = "What is the capital of France?"
        assert _extract_real_question(q) == q
