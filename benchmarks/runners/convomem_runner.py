"""
ConvoMem benchmark runner.

Evaluates retrieval recall on the Salesforce ConvoMem dataset.
Per-message indexing, recall measured by evidence text matching.

6 categories, recall metric only (no NDCG — evidence is text-based, not ID-based).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Optional

from benchmarks.adapters.base import MemorySystemAdapter
from benchmarks.datasets.convomem_loader import (
    CATEGORIES,
    ConvoMemEntry,
    load_convomem,
)
from benchmarks.evaluators.metrics import RetrievalBenchmarkMetrics

K_VALUES = (1, 3, 5, 10, 20)


@dataclass
class ConvoMemConfig:
    """Configuration for a ConvoMem benchmark run."""

    max_per_category: Optional[int] = None
    categories: Optional[tuple[str, ...]] = None
    search_k: int = 20
    k_values: tuple[int, ...] = K_VALUES
    verbose: bool = False


def _evidence_match(evidence_text: str, retrieved_text: str) -> bool:
    """Check if evidence text matches a retrieved document (substring match)."""
    ev = evidence_text.strip().lower()
    ret = retrieved_text.strip().lower()
    if not ev:
        return False
    return ev in ret or ret in ev


def _compute_recall(
    evidence_texts: tuple[str, ...],
    retrieved_docs: list[str],
) -> float:
    """Fraction of evidence texts found in retrieved documents."""
    if not evidence_texts:
        return 1.0

    found = 0
    for ev in evidence_texts:
        for doc in retrieved_docs:
            if _evidence_match(ev, doc):
                found += 1
                break

    return found / len(evidence_texts)


def _ingest_conversations(
    adapter: MemorySystemAdapter,
    entry: ConvoMemEntry,
    user_id: str,
    metrics: RetrievalBenchmarkMetrics,
) -> int:
    """Ingest all messages from all conversations for one entry."""
    msg_count = 0
    for conv in entry.conversations:
        for msg in conv:
            if not msg.text.strip():
                continue

            t0 = time.perf_counter()
            adapter.add_memory(
                user_id=user_id,
                content=msg.text,
                metadata={"speaker": msg.speaker},
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            metrics.latencies_store_ms.append(elapsed_ms)
            msg_count += 1

    return msg_count


def run_convomem_benchmark(
    adapter: MemorySystemAdapter,
    adapter_config: dict,
    run_config: Optional[ConvoMemConfig] = None,
) -> tuple[RetrievalBenchmarkMetrics, list[dict]]:
    """
    Run the ConvoMem benchmark on a memory system.

    Each entry gets a fresh memory store with its conversation messages.

    Args:
        adapter: Memory system adapter.
        adapter_config: Configuration dict for the adapter.
        run_config: Benchmark configuration.

    Returns:
        (metrics, detailed_results) tuple.
    """
    config = run_config or ConvoMemConfig()

    print("\nLoading ConvoMem dataset...")
    entries = load_convomem(
        max_per_category=config.max_per_category,
        categories=config.categories,
    )
    print(f"Loaded {len(entries)} entries")

    print(f"\nInitializing {adapter.name}...")
    adapter.setup(adapter_config)

    metrics = RetrievalBenchmarkMetrics(
        system_name=adapter.name,
        benchmark_name="ConvoMem",
    )
    all_results: list[dict] = []

    for idx, entry in enumerate(entries):
        user_id = str(uuid.uuid4())

        if config.verbose or (idx + 1) % 100 == 0 or idx == 0:
            print(f"  [{idx + 1}/{len(entries)}] {entry.category}")

        # Ingest all messages
        msg_count = _ingest_conversations(adapter, entry, user_id, metrics)

        # Search
        t0 = time.perf_counter()
        results = adapter.search(
            user_id=user_id,
            query=entry.question,
            k=config.search_k,
        )
        search_ms = (time.perf_counter() - t0) * 1000
        metrics.latencies_search_ms.append(search_ms)

        # Compute recall at various k
        retrieved_docs = [r.content for r in results]

        # For RetrievalBenchmarkMetrics we use text-based IDs
        # Map each retrieved doc to an index for the metrics system
        retrieved_ids: list[str] = []
        for i, doc in enumerate(retrieved_docs):
            for j, ev in enumerate(entry.evidence_texts):
                if _evidence_match(ev, doc):
                    retrieved_ids.append(f"ev_{j}")
                    break
            else:
                retrieved_ids.append(f"non_{i}")

        relevant_ids = {f"ev_{j}" for j in range(len(entry.evidence_texts))}

        metrics.add_result(
            retrieved_ids=retrieved_ids,
            relevant_ids=relevant_ids,
            k_values=config.k_values,
            category=entry.category,
        )

        # Compute simple recall for the detailed result
        recall = _compute_recall(entry.evidence_texts, retrieved_docs)

        result = {
            "entry_id": entry.entry_id,
            "category": entry.category,
            "question": entry.question,
            "recall": round(recall, 4),
            "num_messages": msg_count,
            "num_evidence": len(entry.evidence_texts),
            "search_latency_ms": round(search_ms, 1),
        }

        if config.verbose:
            symbol = "+" if recall >= 0.5 else "-"
            print(f"    [{symbol}] recall={recall:.2f} Q: {entry.question[:50]}...")

        all_results.append(result)

        adapter.clear(user_id)

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"ConvoMem Results -- {adapter.name}")
    print(f"{'=' * 60}")
    print(f"Total entries: {metrics.total_questions}")

    for k in config.k_values:
        print(f"  R@{k}: {metrics.avg_recall_any(k) * 100:.1f}%")

    print("\nBy category (R@5):")
    for cat in CATEGORIES:
        r5 = metrics.category_avg_recall(cat, 5)
        if r5 > 0 or metrics.category_recall.get(cat):
            print(f"  {cat}: {r5 * 100:.1f}%")

    # Overall recall (fraction-based, from detailed results)
    if all_results:
        avg_recall = sum(r["recall"] for r in all_results) / len(all_results)
        print(f"\nOverall evidence recall: {avg_recall * 100:.1f}%")

    return metrics, all_results
