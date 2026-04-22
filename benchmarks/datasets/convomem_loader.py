"""
ConvoMem dataset loader.

Downloads the Salesforce/ConvoMem benchmark from HuggingFace.
75K QA pairs across 6 categories testing conversational memory recall.
"""

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

CACHE_DIR = Path(__file__).parent / ".cache" / "convomem"

HF_BASE = (
    "https://huggingface.co/datasets/Salesforce/ConvoMem"
    "/resolve/main/core_benchmark/evidence_questions"
)
HF_TREE_API = (
    "https://huggingface.co/api/datasets/Salesforce/ConvoMem"
    "/tree/main/core_benchmark/evidence_questions"
)

CATEGORIES = (
    "user_evidence",
    "assistant_facts_evidence",
    "changing_evidence",
    "abstention_evidence",
    "preference_evidence",
    "implicit_connection_evidence",
)


@dataclass(frozen=True)
class ConvoMemMessage:
    """A single message in a conversation."""

    speaker: str
    text: str


@dataclass(frozen=True)
class ConvoMemEntry:
    """A single QA entry from the ConvoMem dataset."""

    entry_id: str
    category: str
    question: str
    answer: str
    conversations: tuple[tuple[ConvoMemMessage, ...], ...]
    evidence_texts: tuple[str, ...]


def _list_hf_files(category: str) -> list[str]:
    """List JSON files for a category via HuggingFace tree API."""
    url = f"{HF_TREE_API}/{category}/1_evidence"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            tree = json.loads(resp.read().decode("utf-8"))
        return [
            item["path"].split("/")[-1]
            for item in tree
            if item.get("path", "").endswith(".json")
        ]
    except Exception:
        return []


def _download_category(category: str, force: bool = False) -> list[dict]:
    """Download all files for a category."""
    cat_dir = CACHE_DIR / category
    cat_dir.mkdir(parents=True, exist_ok=True)

    # Check if already cached
    cached = list(cat_dir.glob("*.json"))
    if cached and not force:
        items = []
        for f in sorted(cached):
            with open(f, encoding="utf-8") as fh:
                items.append(json.load(fh))
        return items

    # List and download files
    filenames = _list_hf_files(category)
    if not filenames:
        # Fallback: try numbered files
        filenames = [f"{i}.json" for i in range(100)]

    items = []
    for fname in filenames:
        url = f"{HF_BASE}/{category}/1_evidence/{fname}"
        cache_file = cat_dir / fname
        try:
            if not cache_file.exists() or force:
                urllib.request.urlretrieve(url, cache_file)
            with open(cache_file, encoding="utf-8") as fh:
                items.append(json.load(fh))
        except Exception:
            if cache_file.exists():
                cache_file.unlink()
            continue

    return items


def _parse_entry_dict(item: dict, cat: str, entry_id: str) -> ConvoMemEntry:
    """Parse a single evidence item into a ConvoMemEntry."""
    # Parse conversations — each file has a list of conversations;
    # each conversation has a list of messages.
    convos: list[tuple[ConvoMemMessage, ...]] = []
    for conv in item.get("conversations", []):
        messages: list[ConvoMemMessage] = []
        for msg in conv.get("messages", []):
            messages.append(ConvoMemMessage(
                speaker=msg.get("speaker", msg.get("role", "unknown")),
                text=msg.get("text", msg.get("content", "")),
            ))
        convos.append(tuple(messages))

    # Parse evidence — list of {speaker, text} or plain strings
    evidence: list[str] = []
    for ev in item.get("message_evidences", []):
        if isinstance(ev, dict):
            evidence.append(ev.get("text", ""))
        elif isinstance(ev, str):
            evidence.append(ev)

    return ConvoMemEntry(
        entry_id=entry_id,
        category=cat,
        question=item.get("question", ""),
        answer=item.get("answer", ""),
        conversations=tuple(convos),
        evidence_texts=tuple(evidence),
    )


def load_convomem(
    force_download: bool = False,
    max_per_category: Optional[int] = None,
    categories: Optional[tuple[str, ...]] = None,
) -> list[ConvoMemEntry]:
    """
    Load the ConvoMem dataset.

    Each file may contain either a single entry (top-level question/answer)
    or multiple entries wrapped in an "evidence_items" list. Both schemas
    are supported.
    """
    target_cats = categories or CATEGORIES
    entries: list[ConvoMemEntry] = []

    for cat in target_cats:
        if cat not in CATEGORIES:
            print(f"Warning: unknown category '{cat}', skipping")
            continue

        print(f"Loading ConvoMem/{cat}...")
        raw_items = _download_category(cat, force=force_download)

        cat_count = 0
        for file_idx, item in enumerate(raw_items):
            if max_per_category and cat_count >= max_per_category:
                break

            # Handle wrapper schema: {"evidence_items": [...]}
            if isinstance(item, dict) and "evidence_items" in item:
                sub_items = item["evidence_items"]
                for sub_idx, sub in enumerate(sub_items):
                    if max_per_category and cat_count >= max_per_category:
                        break
                    entries.append(_parse_entry_dict(
                        sub, cat, f"{cat}_{file_idx}_{sub_idx}"
                    ))
                    cat_count += 1
            else:
                # Direct schema: file is a single entry
                entries.append(_parse_entry_dict(item, cat, f"{cat}_{file_idx}"))
                cat_count += 1

    return entries


def print_convomem_stats(entries: list[ConvoMemEntry]) -> None:
    """Print dataset statistics."""
    print("\nConvoMem Dataset Statistics")
    print("=" * 40)
    print(f"Total entries: {len(entries)}")

    cat_counts: dict[str, int] = {}
    for entry in entries:
        cat_counts[entry.category] = cat_counts.get(entry.category, 0) + 1

    print("\nBy category:")
    for cat in sorted(cat_counts.keys()):
        print(f"  {cat}: {cat_counts[cat]}")
