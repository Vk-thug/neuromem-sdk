#!/usr/bin/env python3
"""
NeuroMem Benchmark Suite — CLI Entry Point

Compare NeuroMem against Mem0, Zep, LangMem, and MemPalace on industry benchmarks.

Usage:
    # Quick LoCoMo test (1 conversation, no LLM judge)
    python -m benchmarks.run_benchmark --quick

    # Full LoCoMo benchmark with NeuroMem only
    python -m benchmarks.run_benchmark --systems neuromem

    # Head-to-head: NeuroMem vs MemPalace on LongMemEval
    python -m benchmarks.run_benchmark \
        --benchmark longmemeval \
        --systems neuromem mempalace

    # Run all benchmarks
    python -m benchmarks.run_benchmark \
        --benchmark all \
        --systems neuromem mempalace

    # ConvoMem benchmark (downloads from HuggingFace)
    python -m benchmarks.run_benchmark --benchmark convomem --systems neuromem

    # MemBench benchmark (requires local data)
    python -m benchmarks.run_benchmark \
        --benchmark membench \
        --systems neuromem \
        --membench-dir data/FirstAgent

    # Full LoCoMo benchmark with all options
    python -m benchmarks.run_benchmark \
        --systems neuromem mem0 \
        --conversations 5 \
        --categories 1 2 4 \
        --backend qdrant \
        --judge-model qwen2.5-coder:7b \
        --verbose

    # Latency benchmark only
    python -m benchmarks.run_benchmark --latency --systems neuromem mem0

    # Use OpenAI instead of Ollama
    python -m benchmarks.run_benchmark \
        --systems neuromem \
        --embedding-provider openai \
        --embedding-model text-embedding-3-small \
        --answer-provider openai \
        --answer-model gpt-4o-mini
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Load .env from the repo root so OPENAI_API_KEY etc. are available
# to all adapters and to NeuroMem's internal embedding utilities.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

from benchmarks.adapters.base import MemorySystemAdapter
from benchmarks.datasets.locomo_loader import CATEGORY_NAMES, print_dataset_stats, load_locomo
from benchmarks.evaluators.metrics import BenchmarkMetrics, RetrievalBenchmarkMetrics
from benchmarks.runners.locomo_runner import RunConfig, run_locomo_benchmark
from benchmarks.runners.latency_runner import run_latency_benchmark

AVAILABLE_SYSTEMS = ("neuromem", "mem0", "langmem", "zep", "mempalace")
AVAILABLE_BENCHMARKS = ("locomo", "longmemeval", "convomem", "membench", "all")

RESULTS_DIR = Path(__file__).parent / "results"


def _get_adapter(name: str) -> MemorySystemAdapter:
    """Load a memory system adapter by name."""
    if name == "neuromem":
        from benchmarks.adapters.neuromem_adapter import NeuroMemAdapter
        return NeuroMemAdapter()
    elif name == "mem0":
        from benchmarks.adapters.mem0_adapter import Mem0Adapter
        return Mem0Adapter()
    elif name == "langmem":
        from benchmarks.adapters.langmem_adapter import LangMemAdapter
        return LangMemAdapter()
    elif name == "zep":
        from benchmarks.adapters.zep_adapter import ZepAdapter
        return ZepAdapter()
    elif name == "mempalace":
        from benchmarks.adapters.mempalace_adapter import MemPalaceAdapter
        return MemPalaceAdapter()
    else:
        raise ValueError(
            f"Unknown system: {name}. Available: {', '.join(AVAILABLE_SYSTEMS)}"
        )


def _build_adapter_config(args: argparse.Namespace) -> dict:
    """Build adapter configuration from CLI args."""
    import os

    # Determine vector size based on embedding provider/model
    if args.embedding_provider == "sentence-transformers":
        # all-MiniLM-L6-v2 = 384, all-mpnet-base-v2 = 768, etc.
        st_dims = {
            "all-MiniLM-L6-v2": 384,
            "all-MiniLM-L12-v2": 384,
            "all-mpnet-base-v2": 768,
            "multi-qa-MiniLM-L6-cos-v1": 384,
            "multi-qa-mpnet-base-dot-v1": 768,
            "BAAI/bge-small-en-v1.5": 384,
            "BAAI/bge-base-en-v1.5": 768,
            "BAAI/bge-large-en-v1.5": 1024,
        }
        vector_size = st_dims.get(args.embedding_model, 384)
    elif args.embedding_provider == "ollama":
        vector_size = 768
    else:  # openai
        vector_size = 1536

    return {
        "backend": args.backend,
        "qdrant_host": args.qdrant_host,
        "qdrant_port": args.qdrant_port,
        "collection_name": "bench_" + str(int(time.time())),
        "embedding_model": args.embedding_model,
        "embedding_provider": args.embedding_provider,
        "vector_size": vector_size,
        "ollama_base_url": args.ollama_base_url,
        "llm_provider": args.answer_provider,
        "llm_model": args.answer_model,
        "zep_api_key": os.environ.get("ZEP_API_KEY", ""),
        "use_hyde": getattr(args, "hyde", False),
        "hyde_model": getattr(args, "hyde_model", "qwen2.5-coder:7b"),
        "use_llm_rerank": getattr(args, "llm_rerank", False),
        "verbatim_only": getattr(args, "verbatim_only", False),
        "bm25_blend": getattr(args, "bm25_blend", 0.5),
        "ce_blend": getattr(args, "ce_blend", 0.9),
    }


def _print_comparison_table(all_metrics: list[BenchmarkMetrics]) -> None:
    """Print a formatted comparison table."""
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()

        # Main metrics table
        table = Table(title="LoCoMo Benchmark Results", show_lines=True)
        table.add_column("Metric", style="bold")
        for m in all_metrics:
            table.add_column(m.system_name, justify="right")

        rows = [
            ("Total Questions", [str(m.total_questions) for m in all_metrics]),
            ("Exact Match %", [f"{m.em_score * 100:.1f}%" for m in all_metrics]),
            ("Avg F1 %", [f"{m.avg_f1 * 100:.1f}%" for m in all_metrics]),
            ("Avg Containment %", [f"{m.avg_containment * 100:.1f}%" for m in all_metrics]),
            ("Retrieval Hit Rate %", [f"{m.retrieval_hit_rate * 100:.1f}%" for m in all_metrics]),
            ("Avg Judge Score (1-5)", [f"{m.avg_judge_score:.2f}" for m in all_metrics]),
            ("Avg Store Latency (ms)", [f"{m.avg_store_latency_ms:.1f}" for m in all_metrics]),
            ("P95 Store Latency (ms)", [f"{m.p95_store_latency_ms:.1f}" for m in all_metrics]),
            ("Avg Search Latency (ms)", [f"{m.avg_search_latency_ms:.1f}" for m in all_metrics]),
            ("P95 Search Latency (ms)", [f"{m.p95_search_latency_ms:.1f}" for m in all_metrics]),
        ]

        for label, values in rows:
            table.add_row(label, *values)

        console.print(table)

        # Per-category table
        all_cats = set()
        for m in all_metrics:
            all_cats.update(m.category_scores.keys())

        if all_cats:
            cat_table = Table(title="F1 by Question Category", show_lines=True)
            cat_table.add_column("Category", style="bold")
            for m in all_metrics:
                cat_table.add_column(m.system_name, justify="right")

            for cat in sorted(all_cats):
                name = CATEGORY_NAMES.get(cat, f"cat-{cat}")
                values = [f"{m.category_avg_f1(cat) * 100:.1f}%" for m in all_metrics]
                cat_table.add_row(f"{cat}. {name}", *values)

            console.print(cat_table)

    except ImportError:
        # Fallback: plain text table
        _print_plain_table(all_metrics)


def _print_plain_table(all_metrics: list[BenchmarkMetrics]) -> None:
    """Fallback plain text table when rich is not available."""
    header = f"{'Metric':<30}"
    for m in all_metrics:
        header += f" | {m.system_name:>20}"
    print("\n" + "=" * len(header))
    print("LoCoMo Benchmark Results")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    rows = [
        ("Total Questions", [str(m.total_questions) for m in all_metrics]),
        ("Exact Match %", [f"{m.em_score * 100:.1f}%" for m in all_metrics]),
        ("Avg F1 %", [f"{m.avg_f1 * 100:.1f}%" for m in all_metrics]),
        ("Retrieval Hit Rate %", [f"{m.retrieval_hit_rate * 100:.1f}%" for m in all_metrics]),
        ("Avg Judge (1-5)", [f"{m.avg_judge_score:.2f}" for m in all_metrics]),
        ("Avg Search Latency ms", [f"{m.avg_search_latency_ms:.1f}" for m in all_metrics]),
        ("P95 Search Latency ms", [f"{m.p95_search_latency_ms:.1f}" for m in all_metrics]),
    ]

    for label, values in rows:
        row = f"{label:<30}"
        for v in values:
            row += f" | {v:>20}"
        print(row)

    print("=" * len(header))


def _print_retrieval_table(all_metrics: list[RetrievalBenchmarkMetrics]) -> None:
    """Print a formatted table for retrieval benchmarks."""
    if not all_metrics:
        return

    benchmark_name = all_metrics[0].benchmark_name

    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()

        table = Table(title=f"{benchmark_name} Benchmark Results", show_lines=True)
        table.add_column("Metric", style="bold")
        for m in all_metrics:
            table.add_column(m.system_name, justify="right")

        table.add_row(
            "Total Questions",
            *[str(m.total_questions) for m in all_metrics],
        )

        # R@k rows
        k_values = sorted(all_metrics[0].recall_any_at_k.keys())
        for k in k_values:
            table.add_row(
                f"R@{k}",
                *[f"{m.avg_recall_any(k) * 100:.1f}%" for m in all_metrics],
            )

        # NDCG@k for key values
        for k in [5, 10]:
            if k in k_values:
                table.add_row(
                    f"NDCG@{k}",
                    *[f"{m.avg_ndcg(k) * 100:.1f}%" for m in all_metrics],
                )

        table.add_row(
            "Avg Search Latency (ms)",
            *[f"{m.avg_search_latency_ms:.1f}" for m in all_metrics],
        )

        console.print(table)

        # Per-category table
        all_cats: set[str] = set()
        for m in all_metrics:
            all_cats.update(m.category_recall.keys())

        if all_cats:
            cat_table = Table(title=f"{benchmark_name} R@5 by Category", show_lines=True)
            cat_table.add_column("Category", style="bold")
            for m in all_metrics:
                cat_table.add_column(m.system_name, justify="right")

            for cat in sorted(all_cats):
                values = [f"{m.category_avg_recall(cat, 5) * 100:.1f}%" for m in all_metrics]
                cat_table.add_row(cat, *values)

            console.print(cat_table)

    except ImportError:
        # Plain text fallback
        print(f"\n{'=' * 60}")
        print(f"{benchmark_name} Benchmark Results")
        print(f"{'=' * 60}")
        for m in all_metrics:
            print(f"\n{m.system_name}:")
            print(f"  Total: {m.total_questions}")
            for k in sorted(m.recall_any_at_k.keys()):
                print(f"  R@{k}: {m.avg_recall_any(k) * 100:.1f}%")
            print(f"  Avg search: {m.avg_search_latency_ms:.1f}ms")


def _save_results(
    all_metrics: list,
    all_detailed: dict[str, list[dict]],
    args: argparse.Namespace,
    benchmark_name: str = "locomo",
) -> Path:
    """Save results to JSON."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = RESULTS_DIR / f"{benchmark_name}_{timestamp}.json"

    config_dict: dict = {
        "systems": args.systems,
        "benchmark": getattr(args, "benchmark", "locomo"),
    }

    # Add LoCoMo-specific config if available
    if hasattr(args, "backend"):
        config_dict["backend"] = args.backend
    if hasattr(args, "embedding_model"):
        config_dict["embedding_model"] = args.embedding_model
        config_dict["embedding_provider"] = args.embedding_provider
    if hasattr(args, "search_k"):
        config_dict["search_k"] = args.search_k
    if getattr(args, "verbatim_only", False):
        config_dict["verbatim_only"] = True
        config_dict["bm25_blend"] = args.bm25_blend
        config_dict["ce_blend"] = args.ce_blend
    if getattr(args, "hyde", False):
        config_dict["use_hyde"] = True

    output = {
        "timestamp": datetime.now().isoformat(),
        "benchmark": benchmark_name,
        "config": config_dict,
        "summary": [m.to_dict() for m in all_metrics],
        "detailed": all_detailed,
    }

    output_file.write_text(json.dumps(output, indent=2, default=str))
    print(f"\nResults saved to: {output_file}")
    return output_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="NeuroMem Benchmark Suite — LoCoMo + Latency",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Systems
    parser.add_argument(
        "--systems",
        nargs="+",
        default=["neuromem"],
        choices=list(AVAILABLE_SYSTEMS),
        help="Memory systems to benchmark (default: neuromem)",
    )

    # Benchmark selection
    parser.add_argument(
        "--benchmark",
        choices=list(AVAILABLE_BENCHMARKS),
        default="locomo",
        help="Benchmark to run: locomo, longmemeval, convomem, membench, all (default: locomo)",
    )

    # Dataset
    parser.add_argument(
        "--conversations",
        type=int,
        default=None,
        help="Max conversations to use (default: all 10)",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        type=int,
        default=None,
        help="QA categories to include: 1=single-hop 2=temporal 3=open-ended 4=multi-hop 5=adversarial",
    )
    parser.add_argument(
        "--max-qa",
        type=int,
        default=None,
        help="Max QA pairs per conversation",
    )
    parser.add_argument(
        "--ingestion-mode",
        choices=["turns", "observations", "summaries"],
        default="observations",
        help="How to ingest conversations (default: observations)",
    )
    parser.add_argument(
        "--search-k",
        type=int,
        default=10,
        help="Number of memories to retrieve per query (default: 10)",
    )

    # Infrastructure
    parser.add_argument(
        "--backend",
        choices=["memory", "qdrant"],
        default="memory",
        help="Storage backend (default: memory)",
    )
    parser.add_argument("--qdrant-host", default="localhost")
    parser.add_argument("--qdrant-port", type=int, default=6333)

    # HyDE
    parser.add_argument(
        "--hyde",
        action="store_true",
        help="Enable HyDE (Hypothetical Document Embeddings) for query transformation",
    )
    parser.add_argument(
        "--hyde-model",
        default="qwen2.5-coder:7b",
        help="LLM model for HyDE generation (default: qwen2.5-coder:7b)",
    )

    # LLM-based final re-ranking
    parser.add_argument(
        "--llm-rerank",
        action="store_true",
        help="Enable LLM-based re-ranking of top-5 candidates (slower, more accurate)",
    )

    # Verbatim-only retrieval (MemBench / exact-fact benchmarks)
    parser.add_argument(
        "--verbatim-only",
        action="store_true",
        help=(
            "Skip cognitive pipeline; retrieve from verbatim store with "
            "BM25 + cross-encoder only. Recommended for MemBench."
        ),
    )
    parser.add_argument(
        "--bm25-blend",
        type=float,
        default=0.5,
        help="BM25 weight in verbatim-only mode (0.0-1.0, default: 0.5)",
    )
    parser.add_argument(
        "--ce-blend",
        type=float,
        default=0.9,
        help="Cross-encoder weight in verbatim-only mode (0.0-1.0, default: 0.9)",
    )

    # Embeddings
    parser.add_argument(
        "--embedding-provider",
        choices=["ollama", "openai", "sentence-transformers"],
        default="ollama",
        help="Embedding provider (default: ollama)",
    )
    parser.add_argument(
        "--embedding-model",
        default="nomic-embed-text",
        help="Embedding model (default: nomic-embed-text)",
    )
    parser.add_argument(
        "--ollama-base-url",
        default="http://localhost:11434",
    )

    # Answer generation
    parser.add_argument(
        "--answer-provider",
        choices=["ollama", "openai", "litellm"],
        default="ollama",
    )
    parser.add_argument(
        "--answer-model",
        default="qwen2.5-coder:7b",
        help="LLM for generating answers from context (default: qwen2.5-coder:7b)",
    )

    # Evaluation
    parser.add_argument("--no-judge", action="store_true", help="Disable LLM judge")
    parser.add_argument(
        "--judge-model",
        default="qwen2.5-coder:7b",
        help="LLM for judge evaluation",
    )
    parser.add_argument(
        "--judge-provider",
        choices=["ollama", "openai", "litellm"],
        default="ollama",
    )

    # Benchmark-specific
    parser.add_argument(
        "--membench-dir",
        default="data/FirstAgent",
        help="Path to MemBench FirstAgent/ data directory (default: data/FirstAgent)",
    )
    parser.add_argument(
        "--max-questions",
        type=int,
        default=None,
        help="Max questions for retrieval benchmarks (LongMemEval, ConvoMem, MemBench)",
    )
    parser.add_argument(
        "--convomem-categories",
        nargs="+",
        default=None,
        help="ConvoMem categories to include",
    )

    # Modes
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick test: limited questions, no judge",
    )
    parser.add_argument(
        "--latency",
        action="store_true",
        help="Run latency benchmark instead of LoCoMo",
    )
    parser.add_argument("--verbose", "-v", action="store_true")

    # Output
    parser.add_argument(
        "--dataset-stats",
        action="store_true",
        help="Print dataset statistics and exit",
    )

    args = parser.parse_args()

    # Quick mode overrides
    if args.quick:
        args.conversations = 1
        args.categories = [1, 4]
        args.no_judge = True
        args.max_qa = 20
        if args.max_questions is None:
            args.max_questions = 20

    # Dataset stats mode
    if args.dataset_stats:
        conversations = load_locomo()
        print_dataset_stats(conversations)
        return

    print("=" * 60)
    print("NeuroMem Benchmark Suite")
    print("=" * 60)
    print(f"Systems: {', '.join(args.systems)}")
    print(f"Benchmark: {args.benchmark}")
    print(f"Backend: {args.backend}")
    print(f"Embeddings: {args.embedding_provider}/{args.embedding_model}")
    if args.latency:
        print("Mode: Latency benchmark")
    elif args.benchmark == "locomo":
        print(f"Answer LLM: {args.answer_provider}/{args.answer_model}")
        print(f"Ingestion: {args.ingestion_mode}")
        print(f"Conversations: {args.conversations or 'all 10'}")
        print(f"Categories: {args.categories or 'all 5'}")
        print(f"LLM Judge: {'disabled' if args.no_judge else args.judge_model}")
    else:
        print(f"Max questions: {args.max_questions or 'all'}")
    print("=" * 60)

    # Latency benchmark
    if args.latency:
        latency_results = []
        for system_name in args.systems:
            print(f"\n{'=' * 40}")
            print(f"Latency Benchmark: {system_name}")
            print(f"{'=' * 40}")

            adapter = _get_adapter(system_name)
            adapter_config = _build_adapter_config(args)
            result = run_latency_benchmark(adapter, adapter_config)
            latency_results.append(result)

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = RESULTS_DIR / f"latency_{timestamp}.json"
        output_file.write_text(json.dumps(
            [r.to_dict() for r in latency_results], indent=2
        ))
        print(f"\nLatency results saved to: {output_file}")
        return

    # Determine which benchmarks to run
    if args.benchmark == "all":
        benchmarks_to_run = ["locomo", "longmemeval", "convomem", "membench"]
    else:
        benchmarks_to_run = [args.benchmark]

    for bench_name in benchmarks_to_run:
        if bench_name == "locomo":
            _run_locomo(args)
        elif bench_name == "longmemeval":
            _run_longmemeval(args)
        elif bench_name == "convomem":
            _run_convomem(args)
        elif bench_name == "membench":
            _run_membench(args)


def _run_locomo(args: argparse.Namespace) -> None:
    """Run the LoCoMo QA benchmark."""
    all_metrics: list[BenchmarkMetrics] = []
    all_detailed: dict[str, list[dict]] = {}

    for system_name in args.systems:
        print(f"\n{'#' * 60}")
        print(f"# LoCoMo: {system_name}")
        print(f"{'#' * 60}")

        adapter = _get_adapter(system_name)
        adapter_config = _build_adapter_config(args)

        run_config = RunConfig(
            max_conversations=args.conversations,
            categories=args.categories,
            max_qa_per_conversation=args.max_qa,
            ingestion_mode=args.ingestion_mode,
            search_k=args.search_k,
            answer_llm=args.answer_model,
            answer_provider=args.answer_provider,
            ollama_base_url=args.ollama_base_url,
            use_llm_judge=not args.no_judge,
            judge_model=args.judge_model,
            judge_provider=args.judge_provider,
            verbose=args.verbose,
        )

        t0 = time.perf_counter()
        metrics, detailed = run_locomo_benchmark(adapter, adapter_config, run_config)
        elapsed = time.perf_counter() - t0

        print(f"\n{system_name} completed in {elapsed:.1f}s")

        all_metrics.append(metrics)
        all_detailed[system_name] = detailed
        adapter.teardown()

    _print_comparison_table(all_metrics)
    _save_results(all_metrics, all_detailed, args, benchmark_name="locomo")


def _run_longmemeval(args: argparse.Namespace) -> None:
    """Run the LongMemEval retrieval benchmark."""
    from benchmarks.runners.longmemeval_runner import (
        LongMemEvalConfig,
        run_longmemeval_benchmark,
    )

    all_metrics: list[RetrievalBenchmarkMetrics] = []
    all_detailed: dict[str, list[dict]] = {}

    for system_name in args.systems:
        print(f"\n{'#' * 60}")
        print(f"# LongMemEval: {system_name}")
        print(f"{'#' * 60}")

        adapter = _get_adapter(system_name)
        adapter_config = _build_adapter_config(args)

        run_config = LongMemEvalConfig(
            max_questions=args.max_questions,
            search_k=args.search_k,
            verbose=args.verbose,
        )

        t0 = time.perf_counter()
        metrics, detailed = run_longmemeval_benchmark(
            adapter, adapter_config, run_config
        )
        elapsed = time.perf_counter() - t0

        print(f"\n{system_name} completed in {elapsed:.1f}s")

        all_metrics.append(metrics)
        all_detailed[system_name] = detailed
        adapter.teardown()

    _print_retrieval_table(all_metrics)
    _save_results(all_metrics, all_detailed, args, benchmark_name="longmemeval")


def _run_convomem(args: argparse.Namespace) -> None:
    """Run the ConvoMem retrieval benchmark."""
    from benchmarks.runners.convomem_runner import (
        ConvoMemConfig,
        run_convomem_benchmark,
    )

    all_metrics: list[RetrievalBenchmarkMetrics] = []
    all_detailed: dict[str, list[dict]] = {}

    for system_name in args.systems:
        print(f"\n{'#' * 60}")
        print(f"# ConvoMem: {system_name}")
        print(f"{'#' * 60}")

        adapter = _get_adapter(system_name)
        adapter_config = _build_adapter_config(args)

        cats = tuple(args.convomem_categories) if args.convomem_categories else None

        run_config = ConvoMemConfig(
            max_per_category=args.max_questions,
            categories=cats,
            search_k=args.search_k,
            verbose=args.verbose,
        )

        t0 = time.perf_counter()
        metrics, detailed = run_convomem_benchmark(
            adapter, adapter_config, run_config
        )
        elapsed = time.perf_counter() - t0

        print(f"\n{system_name} completed in {elapsed:.1f}s")

        all_metrics.append(metrics)
        all_detailed[system_name] = detailed
        adapter.teardown()

    _print_retrieval_table(all_metrics)
    _save_results(all_metrics, all_detailed, args, benchmark_name="convomem")


def _run_membench(args: argparse.Namespace) -> None:
    """Run the MemBench retrieval benchmark."""
    from benchmarks.runners.membench_runner import (
        MemBenchConfig,
        run_membench_benchmark,
    )

    all_metrics: list[RetrievalBenchmarkMetrics] = []
    all_detailed: dict[str, list[dict]] = {}

    for system_name in args.systems:
        print(f"\n{'#' * 60}")
        print(f"# MemBench: {system_name}")
        print(f"{'#' * 60}")

        adapter = _get_adapter(system_name)
        adapter_config = _build_adapter_config(args)

        run_config = MemBenchConfig(
            data_dir=args.membench_dir,
            max_per_task=args.max_questions,
            search_k=args.search_k,
            verbose=args.verbose,
        )

        t0 = time.perf_counter()
        metrics, detailed = run_membench_benchmark(
            adapter, adapter_config, run_config
        )
        elapsed = time.perf_counter() - t0

        print(f"\n{system_name} completed in {elapsed:.1f}s")

        all_metrics.append(metrics)
        all_detailed[system_name] = detailed
        adapter.teardown()

    _print_retrieval_table(all_metrics)
    _save_results(all_metrics, all_detailed, args, benchmark_name="membench")


if __name__ == "__main__":
    main()
