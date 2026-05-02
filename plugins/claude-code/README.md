# NeuroMem Plugin for Claude Code

Brain-inspired persistent memory for your coding agent.

## Quickstart (v0.4.7+)

```bash
pip install neuromem-sdk[ui,mcp]    # one install
neuromem init                       # browser opens, finishes setup
neuromem ui                         # serves UI + MCP at http://127.0.0.1:7777
```

The plugin's `.mcp.json` already points at `http://127.0.0.1:7777/mcp/`.
As soon as `neuromem ui` is running, Claude Code picks up the tools.

## Installation (the plugin itself)

### From source (development)
```bash
cd plugins/claude-code
claude plugin install .
```

### From marketplace (when published)
```bash
claude plugin install neuromem
```

## Prerequisites

- Python 3.10+ with the `[ui,mcp]` extras (covers FastAPI + the MCP SDK)
- A running `neuromem ui` process — see Quickstart above
- Optional: OpenAI API key (only if you switch the wizard's embedding from Ollama to OpenAI)

## Commands

| Command | Description |
|---------|-------------|
| `/remember <text>` | Store a memory (auto-detects type: preference, decision, fact, goal) |
| `/recall <query>` | Semantic search across all memory layers |
| `/forget [id]` | Delete a memory (shows list if no ID given) |
| `/memories [type]` | Browse memories with optional type filter |
| `/consolidate` | Promote recurring patterns into stable knowledge |

## Automatic Behavior

The **neuromem skill** automatically:
- Searches relevant memories when you ask questions that could benefit from context
- Stores important new information (decisions, preferences, facts) during conversations
- Weaves memory context naturally into responses without showing raw data

## Agent

Use the **memory-assistant** agent for:
- Bulk memory management (cleanup, organization)
- Deep knowledge exploration and graph analysis
- Memory quality auditing (find outdated or contradictory memories)
- Statistics and diagnostics

## Architecture

```
Claude Code ──> Plugin Commands (/remember, /recall, ...)
             ──> Skill (auto-injects context)
             ──> Agent (deep operations)
             ──> MCP HTTP /mcp/ (mounted in-process by `neuromem ui`)
                  ──> NeuroMem SDK
                       ──> Storage Backend (Qdrant + SQLite by default)
```

## Standalone MCP fallback

If you can't run `neuromem ui` (Docker, headless agent host, CI), swap
the in-process URL in `.mcp.json` for the stdio command:

```json
{
  "mcpServers": {
    "neuromem": {
      "command": "python",
      "args": ["-m", "neuromem.mcp"],
      "env": {
        "NEUROMEM_CONFIG": "./neuromem.yaml",
        "NEUROMEM_USER_ID": "<your-uuid-from-yaml>"
      }
    }
  }
}
```
