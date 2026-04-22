"""
LongMemEval dataset loader.

Downloads the cleaned LongMemEval dataset from HuggingFace and parses it
into frozen dataclasses for use by the benchmark runner.

Dataset: ~500 questions across 6 types testing long-term memory recall.
Each question has a haystack of sessions and ground-truth session IDs.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DATASET_URL = (
    "https://huggingface.co/datasets/xiaowu0162/"
    "longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json"
)
CACHE_DIR = Path(__file__).parent / ".cache"

QUESTION_TYPES = {
    "knowledge-update",
    "multi-session",
    "temporal-reasoning",
    "single-session-user",
    "single-session-assistant",
    "single-session-preference",
}


@dataclass(frozen=True)
class HaystackSession:
    """A single session in the haystack (context) for a question."""

    session_id: str
    date: str
    turns: tuple[dict, ...]  # Each dict has "role" and "content" keys


@dataclass(frozen=True)
class LongMemEvalEntry:
    """A single question entry from the LongMemEval dataset."""

    question_id: str
    question: str
    question_type: str
    question_date: str
    answer: str
    answer_session_ids: frozenset[str]
    haystack_sessions: tuple[HaystackSession, ...]


def load_longmemeval(
    force_download: bool = False,
    max_questions: Optional[int] = None,
    question_types: Optional[set[str]] = None,
) -> list[LongMemEvalEntry]:
    """
    Load the LongMemEval dataset.

    Args:
        force_download: Re-download even if cached.
        max_questions: Limit number of questions loaded.
        question_types: Filter to specific question types.

    Returns:
        List of LongMemEvalEntry objects.
    """
    cache_file = CACHE_DIR / "longmemeval_s_cleaned.json"

    if force_download or not cache_file.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        print("Downloading LongMemEval dataset...")
        urllib.request.urlretrieve(DATASET_URL, cache_file)
        print(f"Cached to {cache_file}")

    with open(cache_file, encoding="utf-8") as f:
        raw_data = json.load(f)

    entries: list[LongMemEvalEntry] = []
    for item in raw_data:
        qtype = item.get("question_type", "")
        if question_types and qtype not in question_types:
            continue

        # Parse haystack sessions
        sessions: list[HaystackSession] = []
        haystack_sessions = item.get("haystack_sessions", [])
        haystack_ids = item.get("haystack_session_ids", [])
        haystack_dates = item.get("haystack_dates", [])

        for i, sess_turns in enumerate(haystack_sessions):
            sid = haystack_ids[i] if i < len(haystack_ids) else f"session_{i}"
            date = haystack_dates[i] if i < len(haystack_dates) else ""
            turns = tuple(
                {"role": t.get("role", ""), "content": t.get("content", "")}
                for t in sess_turns
            )
            sessions.append(HaystackSession(
                session_id=str(sid),
                date=str(date),
                turns=turns,
            ))

        # Parse answer session IDs
        raw_answer_ids = item.get("answer_session_ids", [])
        if isinstance(raw_answer_ids, str):
            raw_answer_ids = [raw_answer_ids]
        answer_ids = frozenset(str(sid) for sid in raw_answer_ids)

        entries.append(LongMemEvalEntry(
            question_id=str(item.get("question_id", f"q_{len(entries)}")),
            question=item.get("question", ""),
            question_type=qtype,
            question_date=item.get("question_date", ""),
            answer=item.get("answer", ""),
            answer_session_ids=answer_ids,
            haystack_sessions=tuple(sessions),
        ))

        if max_questions and len(entries) >= max_questions:
            break

    return entries


def print_longmemeval_stats(entries: list[LongMemEvalEntry]) -> None:
    """Print dataset statistics."""
    print("\nLongMemEval Dataset Statistics")
    print("=" * 40)
    print(f"Total questions: {len(entries)}")

    type_counts: dict[str, int] = {}
    total_sessions = 0
    for entry in entries:
        type_counts[entry.question_type] = type_counts.get(entry.question_type, 0) + 1
        total_sessions += len(entry.haystack_sessions)

    print(f"Avg haystack sessions per question: {total_sessions / len(entries):.1f}")
    print("\nBy question type:")
    for qtype in sorted(type_counts.keys()):
        print(f"  {qtype}: {type_counts[qtype]}")
