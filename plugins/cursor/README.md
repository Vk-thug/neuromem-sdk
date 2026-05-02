# NeuroMem Plugin for Cursor

Brain-inspired persistent memory inside Cursor. Connects via MCP (Model
Context Protocol) — Cursor reads `.cursor/mcp.json` and dials the
NeuroMem MCP endpoint over HTTP.

## Quickstart (v0.4.7+)

```bash
pip install 'neuromem-sdk[ui,mcp]'
neuromem init                  # browser opens, finishes setup
neuromem ui                    # serves UI + MCP at http://127.0.0.1:7777
```

The plugin's `mcp.json` already points at `http://127.0.0.1:7777/mcp/`.
Drop it into your project (Option A) or globally (Option B) and Cursor
picks up the tools as soon as `neuromem ui` is running.

## Installation

### Option A — Project-level config (recommended)

```bash
cp plugins/cursor/.cursor/mcp.json /path/to/your-project/.cursor/mcp.json
```

### Option B — Global config

```bash
cp plugins/cursor/.cursor/mcp.json ~/.cursor/mcp.json
```

## Verifying the connection

In Cursor, open the MCP tools panel (Cmd-Shift-P → "MCP: Show Tools").
You should see twelve tools listed under `neuromem`:

- `store_memory`, `search_memories`, `search_advanced`
- `get_memory`, `list_memories`, `update_memory`, `delete_memory`
- `get_context`, `consolidate`, `find_by_tags`, `get_graph`, `get_stats`

Ask Cursor: _"Use neuromem.search_memories to recall my preferences."_

## Standalone MCP fallback

If you can't run `neuromem ui` (Docker, headless agent host, CI), swap
`mcp.json` for the stdio command:

```json
{
  "mcpServers": {
    "neuromem": {
      "command": "python",
      "args": ["-m", "neuromem.mcp"],
      "env": {
        "NEUROMEM_CONFIG": "${env:NEUROMEM_CONFIG}",
        "NEUROMEM_USER_ID": "${env:NEUROMEM_USER_ID}"
      }
    }
  }
}
```

## See also

- [`plugins/docs/QUICKSTART.md`](../docs/QUICKSTART.md) — first-run guide.
- [`plugins/docs/INTEGRATION_GUIDE.md`](../docs/INTEGRATION_GUIDE.md) — full
  integration overview across all clients.
- [`plugins/claude-code/`](../claude-code) — reference plugin with slash
  commands, hooks, and an agent definition.
