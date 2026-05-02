# NeuroMem Plugin for Antigravity

Brain-inspired persistent memory inside Google's Antigravity coding
agent. Connects via MCP (Model Context Protocol) over HTTP.

> **Note on Antigravity MCP shape:** as of 2026-Q1, Antigravity supports
> the standard `mcpServers` config schema used by Claude Code, Cursor,
> and other MCP-aware IDEs. If your build of Antigravity expects a
> different config path or schema, see the troubleshooting section below.

## Quickstart (v0.4.7+)

```bash
pip install 'neuromem-sdk[ui,mcp]'
neuromem init                  # browser opens, finishes setup
neuromem ui                    # serves UI + MCP at http://127.0.0.1:7777
```

The plugin's `mcp.json` already points at `http://127.0.0.1:7777/mcp/`.
Antigravity picks up the tools as soon as `neuromem ui` is running.

## Installation

```bash
# Project-level
cp plugins/antigravity/.antigravity/mcp.json /path/to/your-project/.antigravity/mcp.json

# Global
cp plugins/antigravity/.antigravity/mcp.json ~/.antigravity/mcp.json
```

Restart the Antigravity session.

## Tools exposed to Antigravity

Twelve MCP tools, grouped:

- **Write** — `store_memory`
- **Read** — `search_memories`, `search_advanced`, `get_memory`,
  `list_memories`, `find_by_tags`, `get_graph`, `get_context`
- **Edit** — `update_memory`, `delete_memory`
- **Maintenance** — `consolidate`, `get_stats`

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

## Troubleshooting

### Antigravity expects `${user_config.*}` style placeholders

Earlier Antigravity builds used a Claude-Code-compatible config schema
with `user_config.*` fields. Replace the `${env:NEUROMEM_*}` placeholders
in the standalone fallback above with literal values, or fall back to the
config shape used in [`plugins/claude-code/.mcp.json`](../claude-code/.mcp.json).

### `neuromem ui` not running

If MCP tool calls fail with "connection refused", confirm `neuromem ui`
is alive: `curl http://127.0.0.1:7777/api/health`. Start it with the
Quickstart command above.
