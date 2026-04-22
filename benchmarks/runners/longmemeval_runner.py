"""
LongMemEval benchmark runner.

Each question has a haystack of sessions; the system must retrieve the
correct session(s) containing the answer.

Metrics: R@k (any/all), NDCG@k, per-question-type breakdown.
No LLM answer generation required — pure retrieval benchmark.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Optional

from benchmarks.adapters.base import MemorySystemAdapter
from benchmarks.datasets.longmemeval_loader import (
    QUESTION_TYPES,
    LongMemEvalEntry,
    load_longmemeval,
)
from benchmarks.evaluators.metrics import RetrievalBenchmarkMetrics

K_VALUES = (1, 3, 5, 10, 30, 50)


@dataclass
class LongMemEvalConfig:
    """Configuration for a LongMemEval benchmark run."""

    max_questions: Optional[int] = None
    question_types: Optional[set[str]] = None
    search_k: int = 50
    k_values: tuple[int, ...] = K_VALUES
    verbose: bool = False


def _build_session_doc(session_turns: tuple[dict, ...], user_only: bool = True) -> str:
    """Build a single document from session turns."""
    parts: list[str] = []
    for turn in session_turns:
        role = turn.get("role", "")
        content = turn.get("content", "")
        if user_only and role != "user":
            continue
        if content.strip():
            parts.append(content.strip())
    return "\n".join(parts)


def _ingest_haystack(
    adapter: MemorySystemAdapter,
    entry: LongMemEvalEntry,
    user_id: str,
    metrics: RetrievalBenchmarkMetrics,
) -> dict[str, str]:
    """
    Ingest all haystack sessions for one question.

    Returns mapping of memory_id -> session_id for result resolution.
    """
    memory_to_session: dict[str, str] = {}

    for session in entry.haystack_sessions:
        doc_text = _build_session_doc(session.turns, user_only=True)
        if not doc_text.strip():
            doc_text = _build_session_doc(session.turns, user_only=False)
        if not doc_text.strip():
            continue

        metadata = {
            "corpus_id": session.session_id,
            "timestamp": session.date,
        }

        t0 = time.perf_counter()
        mem_id = adapter.add_memory(
            user_id=user_id,
            content=doc_text,
            metadata=metadata,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        metrics.latencies_store_ms.append(elapsed_ms)

        memory_to_session[mem_id] = session.session_id

    return memory_to_session


def _resolve_session_ids(
    results: list,
    memory_to_session: dict[str, str],
) -> list[str]:
    """Resolve search results to deduplicated session IDs."""
    retrieved: list[str] = []
    seen: set[str] = set()
    for r in results:
        sid = r.metadata.get("corpus_id", "")
        if not sid:
            sid = memory_to_session.get(r.memory_id, "")
        if sid and sid not in seen:
            retrieved.append(sid)
            seen.add(sid)
    return retrieved


def _evaluate_question(
    adapter: MemorySystemAdapter,
    entry: LongMemEvalEntry,
    user_id: str,
    config: LongMemEvalConfig,
    metrics: RetrievalBenchmarkMetrics,
    memory_to_session: dict[str, str],
) -> dict:
    """Run retrieval for a single question and record metrics."""
    t0 = time.perf_counter()
    results = adapter.search(
        user_id=user_id,
        query=entry.question,
        k=config.search_k,
    )
    search_ms = (time.perf_counter() - t0) * 1000
    metrics.latencies_search_ms.append(search_ms)

    retrieved_session_ids = _resolve_session_ids(results, memory_to_session)

    metrics.add_result(
        retrieved_ids=retrieved_session_ids,
        relevant_ids=entry.answer_session_ids,
        k_values=config.k_values,
        category=entry.question_type,
    )

    hit_at_5 = bool(set(retrieved_session_ids[:5]) & entry.answer_session_ids)

    result = {
        "question_id": entry.question_id,
        "question": entry.question,
        "question_type": entry.question_type,
        "answer": entry.answer,
        "answer_session_ids": sorted(entry.answer_session_ids),
        "retrieved_session_ids": retrieved_session_ids[:10],
        "hit_at_5": hit_at_5,
        "num_haystack_sessions": len(entry.haystack_sessions),
        "search_latency_ms": round(search_ms, 1),
    }

    if config.verbose:
        symbol = "+" if hit_at_5 else "-"
        print(
            f"  [{symbol}] ({entry.question_type}) "
            f"Q: {entry.question[:60]}..."
        )

    return result


def run_longmemeval_benchmark(
    adapter: MemorySystemAdapter,
    adapter_config: dict,
    run_config: Optional[LongMemEvalConfig] = None,
) -> tuple[RetrievalBenchmarkMetrics, list[dict]]:
    """
    Run the LongMemEval benchmark on a memory system.

    Each question gets a fresh memory store with its own haystack.

    Args:
        adapter: Memory system adapter (NeuroMem, MemPalace, etc.)
        adapter_config: Configuration dict for the adapter.
        run_config: Benchmark configuration.

    Returns:
        (metrics, detailed_results) tuple.
    """
    config = run_config or LongMemEvalConfig()

    print("\nLoading LongMemEval dataset...")
    entries = load_longmemeval(
        max_questions=config.max_questions,
        question_types=config.question_types,
    )
    print(f"Loaded {len(entries)} questions")

    print(f"\nInitializing {adapter.name}...")
    adapter.setup(adapter_config)

    metrics = RetrievalBenchmarkMetrics(
        system_name=adapter.name,
        benchmark_name="LongMemEval",
    )
    all_results: list[dict] = []

    for idx, entry in enumerate(entries):
        user_id = str(uuid.uuid4())

        if config.verbose or (idx + 1) % 50 == 0 or idx == 0:
            print(
                f"\n[{idx + 1}/{len(entries)}] {entry.question_type}: "
                f"{len(entry.haystack_sessions)} sessions"
            )

        # Fresh index per question
        memory_to_session = _ingest_haystack(adapter, entry, user_id, metrics)

        result = _evaluate_question(
            adapter, entry, user_id, config, metrics, memory_to_session
        )
        all_results.append(result)

        adapter.clear(user_id)

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"LongMemEval Results -- {adapter.name}")
    print(f"{'=' * 60}")
    print(f"Total questions: {metrics.total_questions}")
    for k in config.k_values:
        r_any = metrics.avg_recall_any(k)
        r_all = metrics.avg_recall_all(k)
        ndcg = metrics.avg_ndcg(k)
        print(
            f"  R@{k}: {r_any * 100:.1f}%  "
            f"R_all@{k}: {r_all * 100:.1f}%  "
            f"NDCG@{k}: {ndcg * 100:.1f}%"
        )

    print("\nBy question type (R@5):")
    for qtype in sorted(QUESTION_TYPES):
        r5 = metrics.category_avg_recall(qtype, 5)
        if r5 > 0 or metrics.category_recall.get(qtype):
            print(f"  {qtype}: {r5 * 100:.1f}%")

    return metrics, all_results
