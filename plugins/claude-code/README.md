# NeuroMem Plugin for Claude Code

Brain-inspired persistent memory for your coding agent.

## Installation

### From source (development)
```bash
cd plugins/claude-code
claude plugin install .
```

### From marketplace (when published)
```bash
claude plugin install neuromem
```

## Setup

During installation, you'll be prompted for:
1. **Config path** — Path to your `neuromem.yaml` (default: `./neuromem.yaml`)
2. **User ID** — Your unique identifier for memory scoping
3. **OpenAI API key** — For embeddings and LLM consolidation

## Prerequisites

- Python 3.10+ with `neuromem-sdk[mcp]` installed:
  ```bash
  pip install neuromem-sdk[mcp]
  ```
- A `neuromem.yaml` config file (see [examples/neuromem.yaml](../../examples/neuromem.yaml))
- OpenAI API key (for embeddings)

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
             ──> MCP Server (python -m neuromem.mcp)
                  ──> NeuroMem SDK
                       ──> Storage Backend (Qdrant/Postgres/SQLite/Memory)
```
