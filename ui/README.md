# NeuroMem UI (v0.4.0)

Local-only React SPA that runs alongside the SDK on `http://127.0.0.1:7777`.

## Routes

- **Memories** — CRUD + filter + structured query browser. Click for full
  metadata + `explain()` retrieval-attribution trace.
- **Graph (2D)** — Obsidian-style force layout via Cytoscape.js +
  cose-bilkent. Node colour = `MemoryType`; edge colour = `link_type`;
  flashbulb-tagged memories pulse red.
- **Brain (3D)** — Jarvis-style anatomical view via react-force-graph-3d.
  Each memory is anchored to one of five regions (hippocampus core,
  neocortex shell, basal-ganglia ring, amygdala cluster, prefrontal-cortex
  orbital ring) per its `MemoryType` + metadata. Translucent halos mark
  region volumes.
- **Retrieval runs** — Inngest-style timeline of every `retrieve()` call
  with full per-stage trace (vector search → hybrid boosts → BM25 →
  cross-encoder → LLM rerank → conflict resolution → brain gating). SSE
  stream for live runs.
- **Observations** — live feed of every `observe()` event, tagged with
  template, salience, emotional weight, flashbulb flag, extracted
  entities.
- **Brain telemetry** — working-memory slots (Cowan 4), TD values, schema
  centroids. Refreshes every second.
- **MCP setup** — ready-to-paste JSON for Claude.ai / Gemini chat /
  ChatGPT, plus generic `mcp.json` for Cursor / Antigravity / VS Code.
  Reads `~/.neuromem/mcp-public.json` if a `cloudflared` tunnel is live.

## Development

```bash
# Dev server — proxies /api → :7777 (the FastAPI app)
cd ui
npm install
npm run dev      # http://localhost:5173

# In another terminal, start the FastAPI server (or the SDK + UI in one):
neuromem-ui      # http://127.0.0.1:7777
```

## Production build

```bash
cd ui
npm run build    # writes static bundle into ../neuromem/ui/web/
```

The Python `FastAPI` app at `neuromem/ui/server.py` mounts that directory
at `/`, so `neuromem-ui` then serves both API and SPA from the same port.

## Stack

- **vite** + **React 18** + **TypeScript**
- **Tailwind** for layout / colours
- **Cytoscape.js** + `cose-bilkent` for the 2D graph
- **react-force-graph-3d** + **three.js** + **three-spritetext** for the
  3D brain
- **SWR** for data fetching with focus revalidation
- **EventSource** (native) for SSE streams
