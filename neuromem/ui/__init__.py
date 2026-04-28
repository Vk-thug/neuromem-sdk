"""
NeuroMem local UI (v0.4.0).

A FastAPI app + React SPA that runs alongside the SDK on
``http://127.0.0.1:7777``. Exposes:

* **Memories** — CRUD + structured-query syntax browser.
* **Knowledge graph** — 2D Obsidian-style and 3D Jarvis-style brain views,
  both rendered from the same ``MemoryGraph.export()`` data.
* **Retrieval inspector** — Inngest-style timeline of every ``retrieve()``
  run with full per-stage trace (vector search, hybrid boosts, BM25,
  cross-encoder, brain gating).
* **Observation feed** — live SSE stream of every ``observe()`` event.
* **Brain telemetry** — working memory, TD values, schema centroids,
  decay heatmap.
* **MCP setup** — ready-to-paste config for Claude.ai / Gemini / ChatGPT
  via the cloudflared tunnel helper.

Launch via the ``neuromem ui`` CLI; see :mod:`neuromem.ui.cli`.
"""

from neuromem.ui.server import create_app

__all__ = ["create_app"]
