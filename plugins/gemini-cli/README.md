# NeuroMem Extension for Gemini CLI

Brain-inspired persistent memory for your Gemini coding agent.

## Installation

```bash
# From source (development — link for live editing)
cd plugins/gemini-cli
gemini extensions link .

# From GitHub (when published)
gemini extensions install https://github.com/Vk-thug/neuromem-sdk --path plugins/gemini-cli
```

## Setup

During installation, you'll be prompted for:
1. **OpenAI API Key** — Stored securely in system keychain
2. **Config Path** — Path to `neuromem.yaml` (optional, defaults to `./neuromem.yaml`)
3. **User ID** — Your unique identifier (optional, defaults to "default")

## Prerequisites

- Python 3.10+ with `neuromem-sdk[mcp]` installed:
  ```bash
  pip install neuromem-sdk[mcp]
  ```
- A `neuromem.yaml` config file (see examples in the NeuroMem SDK repo)

## Commands

| Command | Description |
|---------|-------------|
| `/remember <text>` | Store a memory (auto-detects: preference, decision, fact, goal) |
| `/recall <query>` | Semantic search across all memory layers |
| `/forget [id]` | Delete a memory (shows list if no ID) |
| `/memories [type]` | Browse memories with optional type filter |
| `/consolidate` | Promote patterns into stable knowledge |

## Automatic Behavior

The GEMINI.md context file instructs Gemini to:
- Proactively search memories when context would help
- Store important new information during conversations
- Use advanced structured search syntax when needed
