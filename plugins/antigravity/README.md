# NeuroMem Plugin for Antigravity

Brain-inspired persistent memory inside Google's Antigravity coding
agent. Connects via MCP (Model Context Protocol).

> **Note on Antigravity MCP shape:** as of 2026-Q1, Antigravity supports
> the standard `mcpServers` config schema used by Claude Code, Cursor,
> and other MCP-aware IDEs. If your build of Antigravity expects a
> different config path or schema, see the troubleshooting section below.

## Installation

Drop `.antigravity/mcp.json` from this directory into your Antigravity
project root, or into `~/.antigravity/` for global enablement:

```bash
# Project-level
cp plugins/antigravity/.antigravity/mcp.json /path/to/your-project/.antigravity/mcp.json

# Global
cp plugins/antigravity/.antigravity/mcp.json ~/.antigravity/mcp.json
```

Restart the Antigravity session.

## Prerequisites

```bash
pip install 'neuromem-sdk[mcp]'
```

Set environment variables (or hard-code values in `.antigravity/mcp.json`):

| Variable | Purpose |
|---|---|
| `NEUROMEM_CONFIG` | path to `neuromem.yaml` |
| `NEUROMEM_USER_ID` | scoping ID for stored memories |
| `OPENAI_API_KEY` | embeddings + consolidation (skip if using Ollama) |

## Storage

Default `neuromem.yaml` uses Qdrant on `localhost:6333`:

```bash
docker run -p 6333:6333 qdrant/qdrant
```

NeuroMem falls back to in-memory storage with a warning if Qdrant is
unavailable.

## Tools exposed to Antigravity

Twelve MCP tools, grouped:

- **Write** — `store_memory`
- **Read** — `search_memories`, `search_advanced`, `get_memory`,
  `list_memories`, `find_by_tags`, `get_graph`, `get_context`
- **Edit** — `update_memory`, `delete_memory`
- **Maintenance** — `consolidate`, `get_stats`

## Troubleshooting

### Antigravity expects `${user_config.*}` style placeholders

Earlier Antigravity builds used a Claude-Code-compatible config schema
with `user_config.*` fields. Replace the `${env:NEUROMEM_*}` placeholders
in `.antigravity/mcp.json` with literal values, or fall back to the
config shape used in [`plugins/claude-code/.mcp.json`](../claude-code/.mcp.json).

### MCP server fails to start

Check that `python -m neuromem.mcp` runs cleanly from a terminal in the
same shell environment Antigravity launches. The most common failure is
a missing Python `mcp` package (`pip install 'neuromem-sdk[mcp]'`).
