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

## Prerequisites

- Python 3.10+ with `neuromem-sdk[mcp]` installed:
  ```bash
  pip install neuromem-sdk[mcp]
  ```
- A `neuromem.yaml` config file in your project root
- `OPENAI_API_KEY` environment variable set

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
