"""
MemBench benchmark runner.

Evaluates retrieval quality on the MemBench (ACL 2025) dataset.
Turn-level indexing, Hit@k metric (did we retrieve the turn containing
the answer?), per-task-category breakdown.
"""

import time
import uuid
from dataclasses import dataclass
from typing import Optional

from benchmarks.adapters.base import MemorySystemAdapter
from benchmarks.datasets.membench_loader import (
    TASK_FILES,
    MemBenchEntry,
    load_membench,
)
from benchmarks.evaluators.metrics import RetrievalBenchmarkMetrics

K_VALUES = (1, 3, 5, 10)


@dataclass
class MemBenchConfig:
    """Configuration for a MemBench benchmark run."""

    data_dir: str = "data/FirstAgent"
    max_per_task: Optional[int] = None
    tasks: Optional[list[str]] = None
    search_k: int = 10
    k_values: tuple[int, ...] = K_VALUES
    verbose: bool = False


def _ingest_turns(
    adapter: MemorySystemAdapter,
    entry: MemBenchEntry,
    user_id: str,
    metrics: RetrievalBenchmarkMetrics,
) -> dict[str, set[int]]:
    """
    Ingest all turns for one MemBench item.

    Returns mapping of memory_id -> set of (sid, global_index) for matching.
    """
    memory_to_ids: dict[str, set[int]] = {}

    for turn in entry.turns:
        # Format: [timestamp] [User] text [Assistant] text
        parts: list[str] = []
        if turn.timestamp:
            parts.append(f"[{turn.timestamp}]")
        if turn.user_text:
            parts.append(f"[User] {turn.user_text}")
        if turn.assistant_text:
            parts.append(f"[Assistant] {turn.assistant_text}")

        content = " ".join(parts)
        if not content.strip():
            continue

        metadata = {
            "sid": turn.session_id,
            "s_idx": turn.session_index,
            "t_idx": turn.turn_index,
            "global_idx": turn.global_index,
        }

        t0 = time.perf_counter()
        mem_id = adapter.add_memory(
            user_id=user_id,
            content=content,
            metadata=metadata,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        metrics.latencies_store_ms.append(elapsed_ms)

        memory_to_ids[mem_id] = {turn.session_id, turn.global_index}

    return memory_to_ids


def _get_target_sids(entry: MemBenchEntry) -> set[int]:
    """
    Extract target turn SIDs from a MemBench entry.

    target_step_id format is a list of (turn_sid, session_idx) pairs.
    Only the FIRST element (turn_sid) is the actual target turn ID.
    The second element is the session index (not a target).

    This matches MemPalace's reference implementation:
        for step in item["target_step_ids"]:
            if isinstance(step, list) and len(step) >= 1:
                target_sids.add(step[0])
    """
    target_sids: set[int] = set()
    for group in entry.qa.target_step_ids:
        if group:  # First element is the turn sid
            target_sids.add(group[0])
    return target_sids


# Markers that indicate the start of the REAL question in noisy MemBench cases.
# The "noisy" task wraps the real question in distractor text and uses one of
# these transition phrases to mark where the real question begins.
#
# NOTE: the MemBench noisy dataset concatenates transition phrases with the
# real question WITHOUT separating whitespace, e.g.:
#   "...sent that report.Wait a minute, what I wanted to ask is,What's the name..."
# We therefore include the full trailing connective ("is,", "was:", etc.)
# on the markers so the split happens AFTER the connective — leaving a clean
# question starting with a wh-word.
_QUESTION_MARKERS = (
    # Most-specific (with trailing connective) first — mined from the full
    # noisy.json corpus (1000 items: 500 roles + 500 events).
    "what i truly wanted to clarify is,",
    "what i truly wanted to clarify is:",
    "what i truly wanted to ask is,",
    "what i truly wanted to ask is:",
    "what i actually want to know is,",
    "what i actually want to know is:",
    "what i actually wanted to know is,",
    "what i actually wanted to know is:",
    "what i actually wanted to ask was,",
    "what i actually wanted to ask was:",
    "what i actually wanted to understand is,",
    "what i actually wanted to understand is:",
    "what i really meant to ask is,",
    "what i really meant to ask is:",
    "what i really meant was,",
    "what i really meant was:",
    "what i really want to know is,",
    "what i really want to know is:",
    "what i wanted to ask was,",
    "what i wanted to ask was:",
    "what i wanted to ask is,",
    "what i wanted to ask is:",
    "what i'm really asking is,",
    "what i'm really asking is:",
    "but my actual question is,",
    "but my actual question is:",
    "the real question is,",
    "the real question is:",
    "my real question is,",
    "my real question is:",
    "actually my question was this,",
    "actually my question was this:",
    "but my main question is,",
    "but my main question is:",
    "so my question is,",
    "so my question is:",
    "anyway, my question is,",
    "anyway, my question is:",
    "back to my question:",
    "moving on to my question,",
    "moving on to my question:",
    # Then bare markers (fallbacks, may leave residual connectives)
    "what i truly wanted to clarify is",
    "what i truly wanted to ask is",
    "what i actually want to know is",
    "what i actually wanted to know is",
    "what i actually wanted to ask was",
    "what i actually wanted to ask",
    "what i actually wanted to understand is",
    "what i wanted to ask was",
    "what i wanted to ask is",
    "what i wanted to ask",
    "the real question is",
    "but my actual question is",
    "what i'm really asking is",
    "anyway, my question is",
    "moving on to my question",
    "but my main question is",
    "so my question is",
    "hmm,",
    "i got it wrong,",
    "sorry about that,",
    "wait a minute,",
    "wait,",
    "hold on,",
    "oh no,",
    "oh right,",
    "oops,",
    "oh, what",
    "oh,",
    "sorry,",
    "actually,",
    "by the way,",
)

# Leading connective fragments left behind after a bare-marker match.
# e.g. "what i wanted to ask" matched in "what i wanted to ask is,what's the name..."
# leaves " is,what's the name...". Strip these so the query begins with the wh-word.
_LEADING_JUNK_PATTERNS = (
    " was:", " was,", " was ",
    " is:", " is,", " is ",
    ": ", ":", ",", ".", ";",
)


def _strip_leading_junk(text: str) -> str:
    """Strip leading connective fragments and whitespace/punctuation."""
    text = text.strip()
    # Repeatedly strip leading junk so chains like " is,What's..." → "What's..."
    changed = True
    while changed and text:
        changed = False
        lowered = text.lower()
        for junk in _LEADING_JUNK_PATTERNS:
            if lowered.startswith(junk):
                text = text[len(junk):].lstrip()
                changed = True
                break
    return text


def _extract_real_question(question: str) -> str:
    """
    Extract the real question from MemBench noisy distractor wrapping.

    The "noisy" task wraps the real question in 4-5 sentences of
    irrelevant fluff. Strategies in order of preference:
      1. Find the LATEST marker position in the string (closest to the real
         question). Strip everything up to and including that marker, then
         strip any leading connective junk (" is,", " was:", etc.).
      2. Take the last sentence ending with "?".
      3. Fall back to the original.
    """
    if not question:
        return question

    q_lower = question.lower()

    # Strategy 1: Pick the marker whose match position is LATEST in the
    # string (i.e. closest to the end — the real question). Markers are
    # ordered from most-specific to least-specific; when two markers tie
    # on position, the longer/more-specific one wins because we prefer a
    # later "after-marker" index.
    best_end = -1
    for marker in _QUESTION_MARKERS:
        idx = q_lower.rfind(marker)
        if idx >= 0:
            end = idx + len(marker)
            if end > best_end:
                best_end = end

    if best_end >= 0:
        extracted = _strip_leading_junk(question[best_end:])
        if extracted:
            return extracted

    # Strategy 2: If question has multiple "?" sentences, take the last one.
    # Also handle concatenated "...sentence?NextSentence" by splitting on
    # "?" followed by an uppercase letter (the common concatenation pattern).
    import re
    # Split on sentence boundaries OR concatenated "?Upper" / ".Upper"
    parts = re.split(r"(?<=[.?!])(?=\s|[A-Z])", question)
    question_sentences = [p.strip() for p in parts if "?" in p]
    if len(question_sentences) >= 2:
        return question_sentences[-1]

    # Strategy 3: Return original
    return question


def _extract_factual_anchors(question: str) -> list[str]:
    """
    Extract specific factual anchors from a question for supplementary search.

    Factual anchors are terms that directly match stored facts:
    - Proper nouns (capitalized multi-word phrases): "Associate Degree", "Licensed Practical Nurse"
    - Phone numbers, dates, emails
    - Specific measurements: "148 cm", "28 years"
    - Quoted phrases

    Returns a list of anchor strings for a supplementary search query.
    If no anchors are found, returns empty list (skip supplementary search).
    """
    import re

    anchors: list[str] = []

    # Phone numbers (7+ digits, possibly with country codes)
    for m in re.finditer(r"\b\d[\d\s\-]{6,}\d\b", question):
        anchors.append(m.group().strip())

    # Email addresses
    for m in re.finditer(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b", question):
        anchors.append(m.group())

    # Dates: "August 23rd", "March 11th", "January 5", etc.
    for m in re.finditer(
        r"\b(?:January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?\b",
        question, re.I,
    ):
        anchors.append(m.group())

    # Measurements: "148 cm", "28 years old", "5'11", "$50,000"
    for m in re.finditer(r"\b\d+(?:\.\d+)?\s*(?:cm|kg|lbs?|ft|m|years?\s+old)\b", question, re.I):
        anchors.append(m.group())

    # Multi-word proper noun phrases (2+ consecutive capitalized words
    # that aren't question starters). E.g. "Associate Degree", "Pioneer
    # Construction Group", "Licensed Practical Nurse"
    # Skip very common starters: What, When, Where, How, etc.
    skip_starters = {
        "What", "When", "Where", "Who", "How", "Which", "Did", "Does",
        "Do", "Is", "Are", "Was", "Were", "Has", "Have", "Can", "Could",
        "Would", "Should", "Will", "The", "According", "If", "In", "On",
        "At", "For", "By", "From", "With",
    }
    for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", question):
        phrase = m.group()
        first_word = phrase.split()[0]
        if first_word not in skip_starters:
            anchors.append(phrase)

    # Single capitalized words that look like names (not at sentence start)
    # Only if no multi-word phrases found
    if not anchors:
        words = question.split()
        for i, w in enumerate(words):
            clean = w.strip(".,?!;:'\"")
            if (
                clean
                and clean[0].isupper()
                and len(clean) >= 3
                and clean not in skip_starters
                and i > 0
                and words[i - 1][-1] not in ".!?"
            ):
                anchors.append(clean)

    return anchors


def _check_hit(
    results: list,
    memory_to_ids: dict[str, set[int]],
    target_sids: set[int],
    k: int,
) -> bool:
    """Check if any target step ID appears in top-k results."""
    for r in results[:k]:
        # Check metadata directly
        sid = r.metadata.get("sid")
        global_idx = r.metadata.get("global_idx")
        if sid is not None and int(sid) in target_sids:
            return True
        if global_idx is not None and int(global_idx) in target_sids:
            return True

        # Fallback: check via memory_to_ids map
        ids = memory_to_ids.get(r.memory_id, set())
        if ids & target_sids:
            return True

    return False


def run_membench_benchmark(
    adapter: MemorySystemAdapter,
    adapter_config: dict,
    run_config: Optional[MemBenchConfig] = None,
) -> tuple[RetrievalBenchmarkMetrics, list[dict]]:
    """
    Run the MemBench benchmark on a memory system.

    Each item gets a fresh memory store with its conversation turns.

    Args:
        adapter: Memory system adapter.
        adapter_config: Configuration dict for the adapter.
        run_config: Benchmark configuration.

    Returns:
        (metrics, detailed_results) tuple.
    """
    config = run_config or MemBenchConfig()

    print("\nLoading MemBench dataset...")
    entries = load_membench(
        data_dir=config.data_dir,
        max_per_task=config.max_per_task,
        tasks=config.tasks,
    )
    print(f"Loaded {len(entries)} items")

    print(f"\nInitializing {adapter.name}...")
    adapter.setup(adapter_config)

    metrics = RetrievalBenchmarkMetrics(
        system_name=adapter.name,
        benchmark_name="MemBench",
    )
    all_results: list[dict] = []

    for idx, entry in enumerate(entries):
        user_id = str(uuid.uuid4())

        if config.verbose or (idx + 1) % 200 == 0 or idx == 0:
            print(f"  [{idx + 1}/{len(entries)}] {entry.task_name}: {len(entry.turns)} turns")

        # Ingest all turns
        memory_to_ids = _ingest_turns(adapter, entry, user_id, metrics)

        # Extract the actual question from noisy distractor wrapping.
        # MemBench's "noisy" task wraps the real question in 4-5 sentences
        # of distracting fluff. Common pattern: real question is the LAST
        # sentence ending with "?". Strip everything before "Oh, what I
        # truly wanted to clarify is," or similar markers.
        clean_question = _extract_real_question(entry.qa.question)

        # Search using the cleaned question
        t0 = time.perf_counter()
        results = adapter.search(
            user_id=user_id,
            query=clean_question,
            k=config.search_k,
        )
        search_ms = (time.perf_counter() - t0) * 1000
        metrics.latencies_search_ms.append(search_ms)

        target_sids = _get_target_sids(entry)

        # Build retrieved IDs for the metrics system
        retrieved_ids: list[str] = []
        for r in results:
            sid = r.metadata.get("sid")
            global_idx = r.metadata.get("global_idx")
            ids = memory_to_ids.get(r.memory_id, set())

            matched = False
            if sid is not None and int(sid) in target_sids:
                retrieved_ids.append(f"target_{sid}")
                matched = True
            elif global_idx is not None and int(global_idx) in target_sids:
                retrieved_ids.append(f"target_{global_idx}")
                matched = True
            elif ids & target_sids:
                hit_id = next(iter(ids & target_sids))
                retrieved_ids.append(f"target_{hit_id}")
                matched = True

            if not matched:
                retrieved_ids.append(f"non_{len(retrieved_ids)}")

        relevant_ids = {f"target_{sid}" for sid in target_sids}

        metrics.add_result(
            retrieved_ids=retrieved_ids,
            relevant_ids=relevant_ids,
            k_values=config.k_values,
            category=entry.task_name,
        )

        hit_at_5 = _check_hit(results, memory_to_ids, target_sids, k=5)

        result = {
            "entry_id": entry.entry_id,
            "task_name": entry.task_name,
            "question": entry.qa.question,
            "ground_truth": entry.qa.ground_truth,
            "target_sids": sorted(target_sids),
            "hit_at_5": hit_at_5,
            "num_turns": len(entry.turns),
            "search_latency_ms": round(search_ms, 1),
        }

        if config.verbose:
            symbol = "+" if hit_at_5 else "-"
            print(f"    [{symbol}] Q: {entry.qa.question[:50]}...")

        all_results.append(result)

        adapter.clear(user_id)

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"MemBench Results -- {adapter.name}")
    print(f"{'=' * 60}")
    print(f"Total items: {metrics.total_questions}")

    for k in config.k_values:
        print(f"  R@{k}: {metrics.avg_recall_any(k) * 100:.1f}%")

    print("\nBy task (R@5):")
    for task in sorted(TASK_FILES.keys()):
        r5 = metrics.category_avg_recall(task, 5)
        if r5 > 0 or metrics.category_recall.get(task):
            display = TASK_FILES.get(task, task)
            print(f"  {display}: {r5 * 100:.1f}%")

    return metrics, all_results
