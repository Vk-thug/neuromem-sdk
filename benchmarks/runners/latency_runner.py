"""
Latency benchmark runner.

Measures P50/P95/P99 latency for store and search operations
across memory systems under various load conditions.
"""

import statistics
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from benchmarks.adapters.base import MemorySystemAdapter


@dataclass(frozen=True)
class LatencyResult:
    """Latency statistics for a single operation type."""

    operation: str
    count: int
    avg_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float


@dataclass
class LatencyBenchmarkResult:
    """Full latency benchmark result for a memory system."""

    system_name: str
    store_results: Optional[LatencyResult] = None
    search_results: Optional[LatencyResult] = None
    search_after_100: Optional[LatencyResult] = None
    search_after_1000: Optional[LatencyResult] = None

    def to_dict(self) -> dict:
        d: dict = {"system": self.system_name}
        for name, result in [
            ("store", self.store_results),
            ("search", self.search_results),
            ("search_after_100", self.search_after_100),
            ("search_after_1000", self.search_after_1000),
        ]:
            if result:
                d[name] = {
                    "count": result.count,
                    "avg_ms": round(result.avg_ms, 2),
                    "p50_ms": round(result.p50_ms, 2),
                    "p95_ms": round(result.p95_ms, 2),
                    "p99_ms": round(result.p99_ms, 2),
                    "min_ms": round(result.min_ms, 2),
                    "max_ms": round(result.max_ms, 2),
                }
        return d


def _compute_latency_stats(
    operation: str, latencies_ms: list[float]
) -> LatencyResult:
    """Compute percentile statistics from latency measurements."""
    if not latencies_ms:
        return LatencyResult(
            operation=operation,
            count=0,
            avg_ms=0,
            p50_ms=0,
            p95_ms=0,
            p99_ms=0,
            min_ms=0,
            max_ms=0,
        )

    sorted_l = sorted(latencies_ms)
    n = len(sorted_l)

    return LatencyResult(
        operation=operation,
        count=n,
        avg_ms=statistics.mean(sorted_l),
        p50_ms=statistics.median(sorted_l),
        p95_ms=sorted_l[int(n * 0.95)] if n > 1 else sorted_l[0],
        p99_ms=sorted_l[int(n * 0.99)] if n > 1 else sorted_l[0],
        min_ms=sorted_l[0],
        max_ms=sorted_l[-1],
    )


# Sample data for generating realistic memories
SAMPLE_MEMORIES = [
    "I started learning Python about 3 years ago when I joined the data science team.",
    "My favorite framework is FastAPI because of its type safety and auto-generated docs.",
    "We use PostgreSQL as our primary database, with Redis for caching.",
    "Our team has 8 people - 4 backend, 2 frontend, 1 DevOps, and 1 ML engineer.",
    "I prefer dark mode in all my editors. Currently using VS Code with the Dracula theme.",
    "We deploy our microservices on Kubernetes, running on AWS EKS.",
    "Our CI/CD pipeline uses GitHub Actions with about 15 minute build times.",
    "I've been experimenting with Rust for our performance-critical data pipeline.",
    "Our sprint cycle is 2 weeks with standups every morning at 9:30 AM.",
    "The biggest technical debt in our codebase is the legacy authentication module.",
    "I think we should migrate from REST to GraphQL for our mobile API.",
    "Last quarter we reduced our cloud costs by 40% by optimizing our Lambda functions.",
    "My colleague Sarah is the expert on our recommendation engine.",
    "We use Grafana and Prometheus for monitoring, with PagerDuty for alerts.",
    "I have a background in electrical engineering before switching to software.",
    "Our main product serves about 50,000 daily active users.",
    "We're planning to open-source our internal testing framework next month.",
    "I recently completed the AWS Solutions Architect certification.",
    "The most challenging bug I fixed was a race condition in our payment processing system.",
    "I prefer composition over inheritance and functional programming patterns.",
]

SEARCH_QUERIES = [
    "What programming languages does the user know?",
    "What database does the team use?",
    "How big is the team?",
    "What editor and theme does the user prefer?",
    "What cloud infrastructure do they use?",
    "What is the biggest technical debt?",
    "Who is the recommendation engine expert?",
    "What monitoring tools do they use?",
    "What is the user's educational background?",
    "How many daily active users does the product have?",
]


def run_latency_benchmark(
    adapter: MemorySystemAdapter,
    adapter_config: dict,
    num_stores: int = 100,
    num_searches: int = 50,
    warmup: int = 5,
) -> LatencyBenchmarkResult:
    """
    Run latency benchmarks on a memory system.

    Args:
        adapter: Memory system adapter
        adapter_config: Configuration for the adapter
        num_stores: Number of store operations to measure
        num_searches: Number of search operations to measure
        warmup: Number of warmup operations before measuring

    Returns:
        LatencyBenchmarkResult with P50/P95/P99 stats
    """
    adapter.setup(adapter_config)
    user_id = str(uuid.uuid4())

    result = LatencyBenchmarkResult(system_name=adapter.name)

    # ── Store latency ──
    print(f"  Measuring store latency ({num_stores} ops, {warmup} warmup)...")
    store_latencies: list[float] = []

    for i in range(num_stores + warmup):
        content = SAMPLE_MEMORIES[i % len(SAMPLE_MEMORIES)]
        # Add variation to avoid dedup
        content_varied = f"{content} (iteration {i})"

        t0 = time.perf_counter()
        adapter.add_memory(user_id=user_id, content=content_varied)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        if i >= warmup:
            store_latencies.append(elapsed_ms)

    result.store_results = _compute_latency_stats("store", store_latencies)
    print(
        f"    Store: avg={result.store_results.avg_ms:.1f}ms "
        f"p50={result.store_results.p50_ms:.1f}ms "
        f"p95={result.store_results.p95_ms:.1f}ms"
    )

    # ── Search latency (after ~100 memories) ──
    mem_count = adapter.memory_count(user_id)
    print(f"  Measuring search latency after {mem_count} memories ({num_searches} queries)...")
    search_latencies: list[float] = []

    for i in range(num_searches + warmup):
        query = SEARCH_QUERIES[i % len(SEARCH_QUERIES)]

        t0 = time.perf_counter()
        adapter.search(user_id=user_id, query=query, k=5)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        if i >= warmup:
            search_latencies.append(elapsed_ms)

    result.search_after_100 = _compute_latency_stats(
        f"search_after_{mem_count}", search_latencies
    )
    print(
        f"    Search: avg={result.search_after_100.avg_ms:.1f}ms "
        f"p50={result.search_after_100.p50_ms:.1f}ms "
        f"p95={result.search_after_100.p95_ms:.1f}ms"
    )

    # ── Scale to 1000 memories ──
    current = mem_count
    target = 1000
    if current < target:
        print(f"  Scaling to {target} memories...")
        for i in range(current, target):
            content = SAMPLE_MEMORIES[i % len(SAMPLE_MEMORIES)]
            adapter.add_memory(
                user_id=user_id, content=f"{content} (scale {i})"
            )

    mem_count_1k = adapter.memory_count(user_id)
    print(f"  Measuring search latency after {mem_count_1k} memories...")
    search_latencies_1k: list[float] = []

    for i in range(num_searches + warmup):
        query = SEARCH_QUERIES[i % len(SEARCH_QUERIES)]

        t0 = time.perf_counter()
        adapter.search(user_id=user_id, query=query, k=5)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        if i >= warmup:
            search_latencies_1k.append(elapsed_ms)

    result.search_after_1000 = _compute_latency_stats(
        f"search_after_{mem_count_1k}", search_latencies_1k
    )
    print(
        f"    Search@1k: avg={result.search_after_1000.avg_ms:.1f}ms "
        f"p50={result.search_after_1000.p50_ms:.1f}ms "
        f"p95={result.search_after_1000.p95_ms:.1f}ms"
    )

    # Clean up
    adapter.clear(user_id)
    adapter.teardown()

    return result
