# NeuroMem Plugin for Cursor

Brain-inspired persistent memory inside Cursor. Connects via MCP (Model
Context Protocol) — Cursor reads `.cursor/mcp.json` and spawns the
NeuroMem MCP server as a subprocess.

## Installation

### Option A — Project-level config (recommended)

Copy the file `.cursor/mcp.json` from this directory into the root of your
Cursor project:

```bash
cp plugins/cursor/.cursor/mcp.json /path/to/your-project/.cursor/mcp.json
```

Cursor picks up the MCP server on the next session.

### Option B — Global config

Drop the same file into `~/.cursor/mcp.json` to enable NeuroMem across all
your Cursor projects.

## Prerequisites

```bash
pip install 'neuromem-sdk[mcp]'
```

Set environment variables (or replace the `${env:...}` placeholders in
`.cursor/mcp.json` with literal values):

| Variable | Purpose | Default |
|---|---|---|
| `NEUROMEM_CONFIG` | path to `neuromem.yaml` | `./neuromem.yaml` |
| `NEUROMEM_USER_ID` | scoping ID for stored memories | `default` |
| `OPENAI_API_KEY` | embeddings + consolidation | _(required if using OpenAI)_ |

For local-only Ollama embeddings, point `neuromem.yaml` at
`ollama/nomic-embed-text` and skip the OpenAI key.

## Verifying the connection

In Cursor, open the MCP tools panel (Cmd-Shift-P → "MCP: Show Tools").
You should see twelve tools listed under `neuromem`:

- `store_memory`, `search_memories`, `search_advanced`
- `get_memory`, `list_memories`, `update_memory`, `delete_memory`
- `get_context`, `consolidate`, `find_by_tags`, `get_graph`, `get_stats`

Ask Cursor: _"Use neuromem.search_memories to recall my preferences."_

## Storage backend

The default `neuromem.yaml` uses Qdrant. Start it locally:

```bash
docker run -p 6333:6333 qdrant/qdrant
```

If Qdrant is unavailable, NeuroMem falls back to in-memory storage with a
warning — your memories will not persist across sessions in that case.

## See also

- [`plugins/docs/INTEGRATION_GUIDE.md`](../docs/INTEGRATION_GUIDE.md) — full
  integration overview across all clients.
- [`plugins/claude-code/`](../claude-code) — reference plugin with slash
  commands, hooks, and an agent definition. Cursor's plugin shape is
  simpler (config-only); use the Claude Code plugin as the model for
  custom prompts and workflows.
