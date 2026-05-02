# NeuroMem Plugin for OpenAI Codex CLI

Brain-inspired persistent memory for your Codex coding agent.

## Installation

### From local source
Place this directory in your project or personal plugin location:
```bash
# Project-level
cp -r plugins/codex-cli $PROJECT_ROOT/.agents/plugins/neuromem

# Personal
cp -r plugins/codex-cli ~/.agents/plugins/neuromem
```

### Via marketplace (when published)
```bash
codex plugin install neuromem
```

## Quickstart (v0.4.7+)

```bash
pip install 'neuromem-sdk[ui,mcp]'
neuromem init                 # browser opens, finishes setup
neuromem ui                   # serves UI + MCP at http://127.0.0.1:7777
```

The skill calls the in-process MCP at `http://127.0.0.1:7777/mcp/`.
Codex picks up the tools as soon as `neuromem ui` is running.

## Prerequisites

- Python 3.10+ with `neuromem-sdk[ui,mcp]` installed
- A `neuromem.yaml` config file (created by `neuromem init`)
- `OPENAI_API_KEY` environment variable (only if you switched to OpenAI in the wizard)

## Usage

The NeuroMem skill automatically activates. The agent will:
- Store important information you share (preferences, decisions, facts)
- Search memories when your questions could benefit from past context
- Suggest consolidation after extended sessions

You can also directly ask:
- "Remember that I prefer tabs over spaces"
- "What do you know about my database setup?"
- "Search my memories for API design decisions"
- "Show me my memory statistics"
- "Run memory consolidation"
