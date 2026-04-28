"""Smoke test: initialize NeuroMem against the running Qdrant and round-trip one memory.

Run from repo root:
    python3 scripts/setup_qdrant_smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "neuromem.yaml"


def main() -> int:
    from neuromem import NeuroMem, UserManager
    from qdrant_client import QdrantClient

    print(f"Using config: {CONFIG_PATH}")

    user = UserManager.create(external_id="setup_smoke_user")
    print(f"User: {user.id}")

    memory = NeuroMem.from_config(str(CONFIG_PATH), user_id=user.id)
    print("NeuroMem initialised — Qdrant collection should now exist.")

    memory.observe(
        "Set up neuromem-sdk v0.4.0 with the local Qdrant on port 6333.",
        "Confirmed working — round-trip via Qdrant backend.",
    )

    listed = memory.list(limit=20)
    print(f"Listed {len(listed)} memory item(s) for this user.")

    results = memory.retrieve("How did I set up neuromem-sdk?", k=3)
    print(f"Retrieved {len(results)} memory item(s) via semantic search.")
    for i, item in enumerate(results, 1):
        snippet = (getattr(item, "content", "") or "")[:80]
        print(f"  {i}. {snippet}")

    client = QdrantClient(host="localhost", port=6333)
    cols = [c.name for c in client.get_collections().collections]
    info = client.get_collection("neuromem")
    print(f"Qdrant collections: {cols}")
    print(f"'neuromem' collection: {info.points_count} points")
    return 0 if listed else 1


if __name__ == "__main__":
    sys.exit(main())
