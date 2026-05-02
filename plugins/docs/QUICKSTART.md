# NeuroMem Quickstart

n8n-style first-run guide. One install, one init, browser finishes setup,
every integration lights up automatically.

## 1. Install

```bash
pip install 'neuromem-sdk[ui,mcp]'
```

What's bundled:
- **`[ui]`** → FastAPI server, the SPA dashboard, the SQLAlchemy user store
- **`[mcp]`** → the FastMCP server (now mounted in-process by default)

## 2. Initialize

```bash
neuromem init
```

The wizard asks five questions:
- **Mode** — `single` (no auth, recommended for laptop) or `service` (multi-user, API-key auth)
- **Embedding model** — Ollama `nomic-embed-text` (free, local) or OpenAI
- **Vector store** — Qdrant (recommended), SQLite, in-memory, or Postgres
- **Storage URL** — only asked for SQLite/Postgres
- **UI port** — default 7777

After answers are collected, the wizard:
- Writes `./neuromem.yaml` with your choices
- Mints a fresh UUID under `neuromem.user.id` (no more literal `"default"`)
- Sets `mcp.enabled: true` so MCP auto-starts with the UI
- Auto-creates `~/.neuromem/` if you chose SQLite
- Optionally launches the UI

## 3. Run

```bash
neuromem ui
```

You see:

```
  NeuroMem  →  http://127.0.0.1:7777
  MCP       →  http://127.0.0.1:7777/mcp

  Press Ctrl+C to stop.
```

That's it. No per-request log spam (use `--verbose` if you need it).
The browser opens to the dashboard.

## 4. Connect your integrations

All MCP-aware clients point at the **same URL**: `http://127.0.0.1:7777/mcp/`.

| Client | Setup |
|---|---|
| Claude Code | `cd plugins/claude-code && claude plugin install .` |
| Cursor | `cp plugins/cursor/.cursor/mcp.json ~/.cursor/mcp.json` |
| Antigravity | `cp plugins/antigravity/.antigravity/mcp.json ~/.antigravity/mcp.json` |
| Gemini CLI | `cd plugins/gemini-cli && gemini extensions link .` |
| Codex CLI | `cp -r plugins/codex-cli ~/.agents/plugins/neuromem` |
| Cline / Windsurf / Copilot | Add the URL to your client's MCP settings |

Each plugin's `mcp.json` already contains `{"type":"http","url":"http://127.0.0.1:7777/mcp/"}`.
No second process to spawn, no port to coordinate, no `python -m neuromem.mcp` to keep alive.

## 5. SDK use (Python, in-process)

If you want to call NeuroMem from a Python script or LangChain/LangGraph
agent rather than through MCP, the same yaml works:

```python
from neuromem import NeuroMem

mem = NeuroMem.from_config("neuromem.yaml")
mem.observe("User prefers tabs over spaces.")
results = mem.retrieve("formatting preferences")
for item in results.items:
    print(item.content, item.score)
```

## What changed in v0.4.7

- **MCP mounts in-process** by default. The standalone `neuromem-mcp`
  console script still works for Docker / agent-host scenarios.
- **SQLite is a first-class storage choice** alongside Qdrant and Postgres.
  Wizard auto-creates `~/.neuromem/memory.db` if you pick it.
- **Auto-UUID for `mode:single`** — the wizard never lets the literal
  string `"default"` reach `user_id` again. Existing yamls without
  `user.id` get a UUID minted on first launch (warning printed).
- **Quiet startup** — uvicorn access logs hidden by default. Pass
  `--verbose` to bring them back.

## Troubleshooting

**MCP tool calls return "connection refused":** is `neuromem ui` running?
`curl http://127.0.0.1:7777/api/health` should return `{"status":"ok"}`.

**Wizard says "neuromem.yaml already exists":** pass `--force` or `--ui`
to use the browser wizard instead.

**Still see uvicorn `INFO: 127.0.0.1:xxxxx - "GET /..."` lines:** make sure
you're on v0.4.7+; the quiet log config landed there.
