"""
MemBench dataset loader.

Loads the MemBench (ACL 2025) dataset from a local directory.
Clone from: https://github.com/import-myself/Membench

8.5K items across 11 task categories testing conversational memory.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Task files and their display names
TASK_FILES = {
    "simple": "Simple",
    "highlevel": "High-Level",
    "knowledge_update": "Knowledge Update",
    "comparative": "Comparative",
    "conditional": "Conditional",
    "noisy": "Noisy",
    "aggregative": "Aggregative",
    "highlevel_rec": "High-Level Rec",
    "lowlevel_rec": "Low-Level Rec",
    "RecMultiSession": "Multi-Session Rec",
    "post_processing": "Post-Processing",
}


@dataclass(frozen=True)
class MemBenchTurn:
    """A single conversation turn."""

    user_text: str
    assistant_text: str
    timestamp: str
    session_id: int
    turn_index: int
    session_index: int
    global_index: int


@dataclass(frozen=True)
class MemBenchQA:
    """Question and answer with choices."""

    question: str
    choices: dict[str, str]  # {"A": "...", "B": "...", "C": "...", "D": "..."}
    ground_truth: str  # "A", "B", "C", or "D"
    target_step_ids: tuple[tuple[int, ...], ...]  # Session IDs containing the answer


@dataclass(frozen=True)
class MemBenchEntry:
    """A single benchmark item from MemBench."""

    entry_id: str
    task_name: str
    turns: tuple[MemBenchTurn, ...]
    qa: MemBenchQA


def _parse_items_from_file(filepath: Path, task_name: str) -> list[MemBenchEntry]:
    """Parse items from a single MemBench JSON file."""
    with open(filepath, encoding="utf-8") as f:
        raw = json.load(f)

    # Handle two schemas: topic-keyed and role-keyed
    item_lists: list[dict] = []
    if isinstance(raw, dict):
        if "roles" in raw:
            item_lists = raw["roles"]
        else:
            # Topic-keyed: {"movie": [...], "food": [...], ...}
            for topic_items in raw.values():
                if isinstance(topic_items, list):
                    item_lists.extend(topic_items)
    elif isinstance(raw, list):
        item_lists = raw

    entries: list[MemBenchEntry] = []
    for idx, item in enumerate(item_lists):
        message_list = item.get("message_list", [])
        qa_raw = item.get("QA", {})

        if not message_list or not qa_raw:
            continue

        # Parse turns across all sessions
        # MemBench uses "user_message"/"assistant_message" (FirstAgent) but some
        # other datasets may use "user"/"assistant" — support both.
        turns: list[MemBenchTurn] = []
        global_idx = 0
        for s_idx, session in enumerate(message_list):
            for t_idx, turn in enumerate(session):
                user_text = turn.get("user_message") or turn.get("user") or ""
                assistant_text = turn.get("assistant_message") or turn.get("assistant") or ""
                timestamp = str(turn.get("time", ""))
                place = turn.get("place", "")
                if place:
                    timestamp = f"{timestamp} @ {place}" if timestamp else place
                turns.append(MemBenchTurn(
                    user_text=user_text,
                    assistant_text=assistant_text,
                    timestamp=timestamp,
                    session_id=int(turn.get("sid", global_idx)),
                    turn_index=t_idx,
                    session_index=s_idx,
                    global_index=global_idx,
                ))
                global_idx += 1

        # Parse QA
        choices = qa_raw.get("choices", {})
        ground_truth = qa_raw.get("ground_truth", "")

        # Parse target_step_id — nested list of session IDs
        raw_targets = qa_raw.get("target_step_id", [])
        target_ids: list[tuple[int, ...]] = []
        for group in raw_targets:
            if isinstance(group, list):
                target_ids.append(tuple(int(x) for x in group))
            elif isinstance(group, (int, float)):
                target_ids.append((int(group),))

        entries.append(MemBenchEntry(
            entry_id=f"{task_name}_{idx}",
            task_name=task_name,
            turns=tuple(turns),
            qa=MemBenchQA(
                question=qa_raw.get("question", ""),
                choices=choices,
                ground_truth=ground_truth,
                target_step_ids=tuple(target_ids),
            ),
        ))

    return entries


def load_membench(
    data_dir: str = "data/FirstAgent",
    max_per_task: Optional[int] = None,
    tasks: Optional[list[str]] = None,
) -> list[MemBenchEntry]:
    """
    Load the MemBench dataset from a local directory.

    Args:
        data_dir: Path to the FirstAgent/ directory from MemBench repo.
        max_per_task: Limit entries per task file.
        tasks: Specific task names to load.

    Returns:
        List of MemBenchEntry objects.
    """
    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(
            f"MemBench data directory not found: {data_path}\n"
            "Clone from: https://github.com/import-myself/Membench"
        )

    target_tasks = tasks or list(TASK_FILES.keys())
    entries: list[MemBenchEntry] = []

    for task_name in target_tasks:
        filepath = data_path / f"{task_name}.json"
        if not filepath.exists():
            print(f"Warning: {filepath} not found, skipping")
            continue

        print(f"Loading MemBench/{task_name}...")
        task_entries = _parse_items_from_file(filepath, task_name)

        if max_per_task:
            task_entries = task_entries[:max_per_task]

        entries.extend(task_entries)

    return entries


def print_membench_stats(entries: list[MemBenchEntry]) -> None:
    """Print dataset statistics."""
    print("\nMemBench Dataset Statistics")
    print("=" * 40)
    print(f"Total items: {len(entries)}")

    task_counts: dict[str, int] = {}
    total_turns = 0
    for entry in entries:
        task_counts[entry.task_name] = task_counts.get(entry.task_name, 0) + 1
        total_turns += len(entry.turns)

    print(f"Avg turns per item: {total_turns / len(entries):.1f}")
    print("\nBy task:")
    for task in sorted(task_counts.keys()):
        display = TASK_FILES.get(task, task)
        print(f"  {display}: {task_counts[task]}")
