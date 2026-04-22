"""
LoCoMo dataset loader for memory system benchmarks.

Downloads and parses the LoCoMo-10 dataset (ACL 2024) which contains
10 long-term multi-session conversations with 1986 QA pairs across
5 categories: single-hop, temporal, open-ended, multi-hop, adversarial.

Reference: https://github.com/snap-research/locomo
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import requests

LOCOMO_URL = (
    "https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json"
)
CACHE_DIR = Path(__file__).parent / ".cache"


@dataclass(frozen=True)
class DialogueTurn:
    """A single turn in a conversation session."""

    speaker: str
    text: str
    dia_id: str
    session_num: int
    turn_num: int
    img_url: tuple[str, ...] = ()
    blip_caption: str = ""


@dataclass(frozen=True)
class QAPair:
    """A question-answer pair from the LoCoMo benchmark."""

    question: str
    answer: str
    evidence: tuple[str, ...]
    category: int  # 1=single-hop, 2=temporal, 3=open-ended, 4=multi-hop, 5=adversarial
    is_adversarial: bool = False
    adversarial_answer: str = ""


CATEGORY_NAMES = {
    1: "single-hop",
    2: "temporal",
    3: "open-ended",
    4: "multi-hop",
    5: "adversarial",
}


@dataclass
class Conversation:
    """A full multi-session conversation from LoCoMo."""

    sample_id: str
    speaker_a: str
    speaker_b: str
    sessions: dict[int, list[DialogueTurn]]
    session_dates: dict[int, str]
    qa_pairs: list[QAPair]
    event_summaries: dict[int, dict[str, list[str]]]
    session_summaries: dict[int, str]
    observations: dict[int, dict[str, list[tuple[str, str]]]]

    @property
    def all_turns(self) -> list[DialogueTurn]:
        """Get all dialogue turns across all sessions, in order."""
        turns: list[DialogueTurn] = []
        for session_num in sorted(self.sessions.keys()):
            turns.extend(self.sessions[session_num])
        return turns

    @property
    def total_turns(self) -> int:
        return sum(len(turns) for turns in self.sessions.values())

    @property
    def qa_by_category(self) -> dict[int, list[QAPair]]:
        by_cat: dict[int, list[QAPair]] = {}
        for qa in self.qa_pairs:
            by_cat.setdefault(qa.category, []).append(qa)
        return by_cat

    def get_evidence_turns(self, qa: QAPair) -> list[DialogueTurn]:
        """Resolve evidence references (e.g., 'D1:3') to actual turns."""
        evidence_turns: list[DialogueTurn] = []
        for ref in qa.evidence:
            match = re.match(r"D(\d+):(\d+)", ref)
            if not match:
                continue
            session_num = int(match.group(1))
            turn_num = int(match.group(2))
            session_turns = self.sessions.get(session_num, [])
            # dia_id is 1-indexed, list is 0-indexed
            idx = turn_num - 1
            if 0 <= idx < len(session_turns):
                evidence_turns.append(session_turns[idx])
        return evidence_turns

    def format_conversation_text(self, max_sessions: Optional[int] = None) -> str:
        """Format all dialogue into a single text block for ingestion."""
        lines: list[str] = []
        session_nums = sorted(self.sessions.keys())
        if max_sessions:
            session_nums = session_nums[:max_sessions]

        for sn in session_nums:
            date = self.session_dates.get(sn, "unknown date")
            lines.append(f"\n--- Session {sn} ({date}) ---")
            for turn in self.sessions[sn]:
                lines.append(f"{turn.speaker}: {turn.text}")

        return "\n".join(lines)


def download_locomo(force: bool = False) -> Path:
    """Download the LoCoMo dataset and cache locally."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / "locomo10.json"

    if cache_file.exists() and not force:
        return cache_file

    print(f"Downloading LoCoMo dataset from {LOCOMO_URL}...")
    resp = requests.get(LOCOMO_URL, timeout=60)
    resp.raise_for_status()

    cache_file.write_text(resp.text, encoding="utf-8")
    print(f"Cached to {cache_file} ({len(resp.text) // 1024}KB)")
    return cache_file


def _parse_sessions(conv_data: dict[str, Any]) -> tuple[
    dict[int, list[DialogueTurn]], dict[int, str]
]:
    """Parse session turns and dates from conversation data."""
    sessions: dict[int, list[DialogueTurn]] = {}
    dates: dict[int, str] = {}

    for key, value in conv_data.items():
        # Match session data keys like "session_1", "session_2"
        session_match = re.match(r"session_(\d+)$", key)
        if session_match and isinstance(value, list):
            sn = int(session_match.group(1))
            turns: list[DialogueTurn] = []
            for i, turn_data in enumerate(value):
                img_urls = tuple(turn_data.get("img_url", []))
                turns.append(DialogueTurn(
                    speaker=turn_data["speaker"],
                    text=turn_data["text"],
                    dia_id=turn_data.get("dia_id", f"D{sn}:{i + 1}"),
                    session_num=sn,
                    turn_num=i + 1,
                    img_url=img_urls,
                    blip_caption=turn_data.get("blip_caption", ""),
                ))
            sessions[sn] = turns

        # Match date keys like "session_1_date_time"
        date_match = re.match(r"session_(\d+)_date_time$", key)
        if date_match and isinstance(value, str):
            dates[int(date_match.group(1))] = value

    return sessions, dates


def _parse_qa(qa_data: list[dict[str, Any]]) -> list[QAPair]:
    """Parse QA pairs from the dataset."""
    pairs: list[QAPair] = []
    for item in qa_data:
        cat = item.get("category", 1)
        is_adv = cat == 5

        # Category 5 (adversarial) may use "adversarial_answer" instead of "answer"
        answer = item.get("answer", "")
        adv_answer = item.get("adversarial_answer", "")
        if is_adv and not answer:
            answer = "unanswerable"

        pairs.append(QAPair(
            question=item["question"],
            answer=answer,
            evidence=tuple(item.get("evidence", [])),
            category=cat,
            is_adversarial=is_adv,
            adversarial_answer=adv_answer,
        ))
    return pairs


def _parse_events(event_data: dict[str, Any]) -> dict[int, dict[str, list[str]]]:
    """Parse event summaries."""
    events: dict[int, dict[str, list[str]]] = {}
    for key, value in event_data.items():
        match = re.match(r"events_session_(\d+)", key)
        if match and isinstance(value, dict):
            sn = int(match.group(1))
            events[sn] = {}
            for speaker, items in value.items():
                if speaker == "date":
                    continue
                if isinstance(items, list):
                    events[sn][speaker] = items
    return events


def _parse_summaries(summary_data: dict[str, Any]) -> dict[int, str]:
    """Parse session summaries."""
    summaries: dict[int, str] = {}
    for key, value in summary_data.items():
        match = re.match(r"session_(\d+)_summary", key)
        if match and isinstance(value, str):
            summaries[int(match.group(1))] = value
    return summaries


def _parse_observations(
    obs_data: dict[str, Any],
) -> dict[int, dict[str, list[tuple[str, str]]]]:
    """Parse observations (extracted facts with evidence references)."""
    observations: dict[int, dict[str, list[tuple[str, str]]]] = {}
    for key, value in obs_data.items():
        match = re.match(r"session_(\d+)_observation", key)
        if match and isinstance(value, dict):
            sn = int(match.group(1))
            observations[sn] = {}
            for speaker, items in value.items():
                if isinstance(items, list):
                    parsed = []
                    for item in items:
                        if isinstance(item, list) and len(item) >= 2:
                            parsed.append((item[0], item[1]))
                    observations[sn][speaker] = parsed
    return observations


def load_locomo(
    force_download: bool = False,
    max_conversations: Optional[int] = None,
    categories: Optional[list[int]] = None,
) -> list[Conversation]:
    """
    Load the LoCoMo benchmark dataset.

    Args:
        force_download: Re-download even if cached
        max_conversations: Limit number of conversations (for quick testing)
        categories: Filter QA pairs to these categories only (1-5)

    Returns:
        List of Conversation objects with all sessions and QA pairs
    """
    cache_file = download_locomo(force=force_download)
    raw = json.loads(cache_file.read_text(encoding="utf-8"))

    if max_conversations:
        raw = raw[:max_conversations]

    conversations: list[Conversation] = []
    for entry in raw:
        conv_data = entry["conversation"]
        sessions, dates = _parse_sessions(conv_data)
        qa_pairs = _parse_qa(entry.get("qa", []))

        # Filter by category if specified
        if categories:
            qa_pairs = [q for q in qa_pairs if q.category in categories]

        conversations.append(Conversation(
            sample_id=entry["sample_id"],
            speaker_a=conv_data.get("speaker_a", "Speaker A"),
            speaker_b=conv_data.get("speaker_b", "Speaker B"),
            sessions=sessions,
            session_dates=dates,
            qa_pairs=qa_pairs,
            event_summaries=_parse_events(entry.get("event_summary", {})),
            session_summaries=_parse_summaries(entry.get("session_summary", {})),
            observations=_parse_observations(entry.get("observation", {})),
        ))

    return conversations


def print_dataset_stats(conversations: list[Conversation]) -> None:
    """Print summary statistics for the loaded dataset."""
    total_turns = sum(c.total_turns for c in conversations)
    total_qa = sum(len(c.qa_pairs) for c in conversations)
    total_sessions = sum(len(c.sessions) for c in conversations)

    cat_counts: dict[int, int] = {}
    for conv in conversations:
        for qa in conv.qa_pairs:
            cat_counts[qa.category] = cat_counts.get(qa.category, 0) + 1

    print(f"\n{'=' * 50}")
    print(f"LoCoMo Dataset Statistics")
    print(f"{'=' * 50}")
    print(f"Conversations: {len(conversations)}")
    print(f"Total sessions: {total_sessions}")
    print(f"Total dialogue turns: {total_turns}")
    print(f"Total QA pairs: {total_qa}")
    print(f"\nQA by category:")
    for cat in sorted(cat_counts.keys()):
        name = CATEGORY_NAMES.get(cat, f"cat-{cat}")
        print(f"  {cat}. {name}: {cat_counts[cat]}")
    print(f"{'=' * 50}\n")
