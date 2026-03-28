# Phase 2: NeuroMem Platform Plugin Bundles — Implementation Prompt

> Copy-paste this entire prompt into a new Claude Code session to build the plugin bundles.
> **Prerequisite**: Phase 1 (MCP server) must be complete. The MCP server at `neuromem/mcp/` must be working with `python -m neuromem.mcp`.

---

## Objective

Build distributable plugin bundles for the three platforms that support rich plugin ecosystems beyond raw MCP: **Claude Code**, **OpenAI Codex CLI**, and **Gemini CLI**. Each bundle wraps the Phase 1 MCP server with platform-native slash commands, agents, skills, hooks, and context files — giving users a first-class experience on each platform.

For platforms that only support raw MCP config (Cline, Cursor, Windsurf, GitHub Copilot, Claude.ai, ChatGPT), Phase 1's MCP server is already sufficient. Those platforms just need documentation (included at the end).

---

## Context

NeuroMem SDK (`neuromem-sdk` v0.2.0) has:
- A working MCP server at `neuromem/mcp/` (Phase 1) with 12 tools, 3 resources, 2 prompts
- Entry point: `python -m neuromem.mcp` (stdio) or `python -m neuromem.mcp --transport http` (HTTP)
- Console script: `neuromem-mcp`
- Core API: `observe()`, `retrieve()`, `search()`, `consolidate()`, `list()`, `update()`, `forget()`, `retrieve_with_context()`, `find_by_tags()`, `get_graph()`
- 4 memory types: episodic, semantic, procedural, affective
- Brain-inspired features: Ebbinghaus decay, LLM consolidation, graph-augmented retrieval, multi-hop decomposition

---

## File Structure

Create these directories at the project root:

```
plugins/
├── claude-code/                    # Claude Code plugin
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── .mcp.json
│   ├── skills/
│   │   └── neuromem/
│   │       └── SKILL.md
│   ├── commands/
│   │   ├── remember.md
│   │   ├── recall.md
│   │   ├── forget.md
│   │   ├── memories.md
│   │   └── consolidate.md
│   ├── agents/
│   │   └── memory-assistant.md
│   ├── hooks/
│   │   └── hooks.json
│   └── README.md
│
├── codex-cli/                      # OpenAI Codex CLI plugin
│   ├── .codex-plugin/
│   │   └── plugin.json
│   ├── .mcp.json
│   ├── skills/
│   │   └── neuromem/
│   │       └── SKILL.md
│   └── README.md
│
├── gemini-cli/                     # Gemini CLI extension
│   ├── gemini-extension.json
│   ├── GEMINI.md
│   ├── commands/
│   │   ├── remember.toml
│   │   ├── recall.toml
│   │   ├── forget.toml
│   │   ├── memories.toml
│   │   └── consolidate.toml
│   └── README.md
│
└── docs/
    └── INTEGRATION_GUIDE.md        # Universal guide for ALL platforms
```

---

## Part A: Claude Code Plugin

This is the richest integration — Claude Code supports commands, agents, skills, hooks, and MCP.

### A1. `.claude-plugin/plugin.json`

```json
{
  "name": "neuromem",
  "version": "0.2.0",
  "description": "Brain-inspired persistent memory for coding agents — remember experiences, learn facts, adapt to your style, and forget naturally",
  "author": {
    "name": "NeuroMem Team",
    "url": "https://github.com/Vk-thug/neuromem-sdk"
  },
  "homepage": "https://docs.neuromem.ai",
  "repository": "https://github.com/Vk-thug/neuromem-sdk",
  "license": "MIT",
  "keywords": ["memory", "ai", "agents", "knowledge-graph", "cognitive", "mcp"],
  "commands": "./commands/",
  "agents": "./agents/",
  "skills": "./skills/",
  "hooks": "./hooks/hooks.json",
  "mcpServers": "./.mcp.json",
  "userConfig": {
    "neuromem_config_path": {
      "description": "Path to neuromem.yaml config file (default: ./neuromem.yaml)",
      "sensitive": false
    },
    "neuromem_user_id": {
      "description": "Your unique user ID for memory scoping",
      "sensitive": false
    },
    "openai_api_key": {
      "description": "OpenAI API key for embeddings and consolidation",
      "sensitive": true
    }
  }
}
```

### A2. `.mcp.json`

```json
{
  "mcpServers": {
    "neuromem": {
      "command": "python",
      "args": ["-m", "neuromem.mcp"],
      "env": {
        "NEUROMEM_CONFIG": "${user_config.neuromem_config_path}",
        "NEUROMEM_USER_ID": "${user_config.neuromem_user_id}",
        "OPENAI_API_KEY": "${user_config.openai_api_key}"
      }
    }
  }
}
```

**Note**: `${user_config.*}` references values from `userConfig` in plugin.json that the user provides at install time. If the user doesn't set them, the MCP server falls back to its own defaults (env vars or `./neuromem.yaml`).

### A3. Commands (`commands/`)

Each command is a Markdown file with YAML frontmatter. These become `/remember`, `/recall`, etc. in Claude Code.

#### `commands/remember.md`

```markdown
---
name: remember
description: Store a memory — save context, decisions, preferences, or facts for later recall
argument-hint: "<what to remember>"
allowed-tools: neuromem
---

Use the NeuroMem MCP server to store a memory.

The user wants to remember: $ARGUMENTS

Call the `store_memory` tool from the neuromem MCP server with:
- `content`: set to the user's input ($ARGUMENTS)
- `assistant_response`: set to "Stored via /remember command"

If the content describes a preference, use `template: "preference"`.
If it describes a decision, use `template: "decision"`.
If it states a fact, use `template: "fact"`.
If it sets a goal, use `template: "goal"`.
Otherwise, omit the template field.

After storing, confirm to the user what was saved and mention the memory type that was detected.
```

#### `commands/recall.md`

```markdown
---
name: recall
description: Search memories — find relevant context, decisions, or knowledge from past sessions
argument-hint: "<what to search for>"
allowed-tools: neuromem
---

Use the NeuroMem MCP server to search for relevant memories.

The user is looking for: $ARGUMENTS

Call the `search_memories` tool from the neuromem MCP server with:
- `query`: set to the user's search query ($ARGUMENTS)
- `k`: 10

Present the results in a clear format:
- Show each memory's content, type (episodic/semantic/procedural), confidence score, and tags
- If memories have low confidence (<0.5), note that they may be fading
- If no results found, suggest the user try different search terms or check with `search_advanced` for structured queries
- Group results by memory type if there are more than 5 results
```

#### `commands/forget.md`

```markdown
---
name: forget
description: Delete a specific memory by ID
argument-hint: "<memory_id>"
allowed-tools: neuromem
---

Use the NeuroMem MCP server to delete a memory.

The user wants to forget memory with ID: $ARGUMENTS

First, call the `get_memory` tool to show the user what memory they're about to delete.

Ask the user to confirm deletion. If confirmed, call the `delete_memory` tool with:
- `memory_id`: the provided ID

Confirm the deletion to the user.

If no memory ID was provided ($ARGUMENTS is empty), call `list_memories` with `limit: 20` and show the user their recent memories so they can pick one to delete.
```

#### `commands/memories.md`

```markdown
---
name: memories
description: List and browse all stored memories with optional type filter
argument-hint: "[episodic|semantic|procedural]"
allowed-tools: neuromem
---

Use the NeuroMem MCP server to list memories.

If the user specified a type filter: $ARGUMENTS
- Call `list_memories` with `memory_type` set to the filter and `limit: 30`

If no filter was specified:
- Call `get_stats` first to show an overview (total count, breakdown by type)
- Then call `list_memories` with `limit: 20`

Present the results as a formatted table or list:
- ID (first 8 chars), Content (truncated to 80 chars), Type, Confidence, Tags, Age
- Sort by most recent first
- Show the total count and mention if there are more memories not shown
```

#### `commands/consolidate.md`

```markdown
---
name: consolidate
description: Trigger memory consolidation — promotes recurring patterns into stable knowledge
allowed-tools: neuromem
---

Use the NeuroMem MCP server to trigger memory consolidation.

Explain to the user what consolidation does:
- Reviews episodic (recent experience) memories
- Extracts stable facts and promotes them to semantic memory
- Identifies behavioral patterns and promotes them to procedural memory
- Applies Ebbinghaus forgetting curves to decay weak memories
- Merges similar facts to reduce redundancy

Then call the `consolidate` tool.

After consolidation completes, call `get_stats` to show the updated memory counts so the user can see what changed.
```

### A4. Skill (`skills/neuromem/SKILL.md`)

```markdown
---
name: neuromem
description: Automatically inject relevant NeuroMem memories as context when the user asks questions. Use this skill when the user's query could benefit from historical context, preferences, past decisions, or learned facts stored in memory.
user-invocable: false
disable-model-invocation: false
allowed-tools: neuromem
---

You have access to the NeuroMem brain-inspired memory system via MCP tools. When the user's message suggests they could benefit from stored context, proactively use the memory system.

## When to Search Memory

Automatically search memories when the user:
- References past conversations ("we discussed", "last time", "remember when")
- Asks about preferences ("how do I like", "what's my preferred")
- Makes decisions that past context could inform
- Works on a project where historical context exists
- Asks "what do you know about X"

## How to Use

1. Call `search_memories` with a relevant query extracted from the user's message
2. If results are relevant (confidence > 0.6), incorporate them naturally into your response
3. Do NOT dump raw memory contents — weave them into your answer as natural context
4. If the user shares new important information (decisions, preferences, facts), call `store_memory` to save it

## Memory Types

- **Episodic**: Recent experiences and conversations (high detail, fast decay)
- **Semantic**: Stable facts and knowledge (low decay, high confidence)
- **Procedural**: User preferences and behavioral patterns (how they like things done)
- **Affective**: Emotional context and sentiment patterns

## Important

- Never mention memory IDs, confidence scores, or internal details to the user unless asked
- If a memory seems outdated or contradicts current information, mention the potential discrepancy
- Do not store trivial information (greetings, acknowledgements, small talk)
```

### A5. Agent (`agents/memory-assistant.md`)

```markdown
---
name: memory-assistant
description: Specialized agent for deep memory operations — bulk management, analysis, graph exploration, knowledge auditing, and memory system diagnostics. Use when the user needs to work extensively with their memory system beyond simple store/recall.
model: sonnet
tools: neuromem, Read, Grep, Glob
---

You are NeuroMem Memory Assistant, a specialized agent for managing and analyzing the user's brain-inspired memory system.

## Your Capabilities

You have access to the full NeuroMem MCP toolset:
- `store_memory` — Store new memories
- `search_memories` — Semantic search with multi-hop decomposition
- `search_advanced` — Structured query syntax (type:, tag:, confidence:>, after:, before:)
- `get_context` — Graph-expanded context retrieval
- `get_memory` — Get single memory by ID
- `list_memories` — List with type filter
- `update_memory` — Edit memory content
- `delete_memory` — Remove a memory
- `consolidate` — Trigger episodic-to-semantic consolidation
- `get_stats` — Memory system statistics
- `find_by_tags` — Hierarchical tag search
- `get_graph` — Entity-relationship graph export

## When You Are Invoked

- User asks to "clean up" or "organize" their memories
- User wants to explore what the system knows about a topic (deep dive)
- User asks for memory analytics or statistics
- User wants to bulk update, tag, or delete memories
- User asks about memory relationships or the knowledge graph
- User wants to audit memory quality (find low-confidence, outdated, or contradictory memories)

## Approach

1. Start by calling `get_stats` to understand the current state
2. For bulk operations, use `list_memories` and `search_advanced` to identify targets
3. Confirm with the user before any destructive operations (delete, bulk update)
4. After operations, show a summary of what changed
5. Use `get_graph` to visualize entity relationships when exploring knowledge
```

### A6. Hooks (`hooks/hooks.json`)

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "python -c \"import json; print(json.dumps({'additionalContext': 'NeuroMem memory system is available. Use /remember to store, /recall to search, /memories to browse, /consolidate to promote patterns. The memory-assistant agent handles bulk operations and deep analysis.'}))\""
          }
        ]
      }
    ]
  }
}
```

This injects a session-start reminder that NeuroMem is available. Keep it lightweight — it runs every session.

### A7. `README.md`

```markdown
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
Claude Code ──→ Plugin Commands (/remember, /recall, ...)
             ──→ Skill (auto-injects context)
             ──→ Agent (deep operations)
             ──→ MCP Server (python -m neuromem.mcp)
                  ──→ NeuroMem SDK
                       ──→ Storage Backend (Qdrant/Postgres/SQLite/Memory)
```
```

---

## Part B: OpenAI Codex CLI Plugin

Codex CLI has a simpler plugin system — manifest, MCP, and skills only.

### B1. `.codex-plugin/plugin.json`

```json
{
  "name": "neuromem",
  "version": "0.2.0",
  "description": "Brain-inspired persistent memory for coding agents — remember experiences, learn facts, adapt to your style, and forget naturally",
  "author": {
    "name": "NeuroMem Team",
    "url": "https://github.com/Vk-thug/neuromem-sdk"
  },
  "homepage": "https://docs.neuromem.ai",
  "repository": "https://github.com/Vk-thug/neuromem-sdk",
  "license": "MIT",
  "keywords": ["memory", "ai", "agents", "knowledge-graph", "cognitive", "mcp"],
  "skills": "./skills/",
  "mcpServers": "./.mcp.json",
  "interface": {
    "displayName": "NeuroMem — Brain-Inspired Memory",
    "shortDescription": "Persistent memory with Ebbinghaus decay, LLM consolidation, and graph-augmented retrieval",
    "longDescription": "NeuroMem gives your coding agent a brain-inspired memory system with four memory types (episodic, semantic, procedural, affective), forgetting curves that naturally fade unused knowledge, LLM-driven consolidation that promotes patterns into stable facts, and a knowledge graph for multi-hop reasoning. Works with any storage backend: PostgreSQL+pgvector, Qdrant, SQLite, or in-memory.",
    "developerName": "NeuroMem Team",
    "category": "Productivity",
    "capabilities": ["Read", "Write"],
    "websiteURL": "https://docs.neuromem.ai",
    "defaultPrompt": [
      "Remember that I prefer Python type annotations on all functions",
      "What do you remember about my coding preferences?",
      "Search my memories for database migration decisions"
    ]
  }
}
```

### B2. `.mcp.json`

```json
{
  "mcpServers": {
    "neuromem": {
      "command": "python",
      "args": ["-m", "neuromem.mcp"],
      "env": {
        "NEUROMEM_CONFIG": "./neuromem.yaml",
        "OPENAI_API_KEY": "${OPENAI_API_KEY}"
      }
    }
  }
}
```

**Note**: Codex CLI doesn't support `userConfig` like Claude Code. Users must set `OPENAI_API_KEY` as a system env var, or the `${OPENAI_API_KEY}` reference passes through the existing env. Update `NEUROMEM_CONFIG` path as needed for their project.

### B3. Skill (`skills/neuromem/SKILL.md`)

```markdown
---
name: neuromem
description: Brain-inspired memory system for persistent context across coding sessions. Automatically stores decisions, preferences, and facts. Retrieves relevant memories when context would help.
---

You have access to the NeuroMem memory system via MCP tools. Use it to maintain persistent context across sessions.

## Available MCP Tools

- `store_memory` — Save a user-assistant interaction (content, optional assistant_response and template)
- `search_memories` — Semantic search with multi-hop query decomposition (query, k)
- `search_advanced` — Structured query: type:semantic tag:preference confidence:>0.8 "exact phrase"
- `get_context` — Retrieve with graph-expanded context (related memories auto-attached)
- `get_memory` — Get single memory by ID
- `list_memories` — List memories (optional memory_type filter, limit)
- `update_memory` — Update memory content by ID
- `delete_memory` — Delete memory by ID
- `consolidate` — Promote episodic patterns into semantic knowledge
- `get_stats` — Memory system statistics
- `find_by_tags` — Hierarchical tag search (e.g., "topic:python")
- `get_graph` — Export entity-relationship graph

## Automatic Behavior

- When the user shares preferences, decisions, or important facts — store them
- When the user's question could benefit from past context — search memories first
- When referencing past conversations — use search to find relevant history
- After extended sessions — suggest running consolidation

## Memory Types

- **Episodic**: Recent interactions (short-term, decays naturally)
- **Semantic**: Stable facts and knowledge (long-term, high confidence)
- **Procedural**: User preferences and coding patterns
- **Affective**: Sentiment and emotional context

## Do Not

- Store trivial exchanges (greetings, "ok", "thanks")
- Show raw memory IDs or confidence scores unless the user asks
- Override current information with stale memories — note discrepancies instead
```

### B4. `README.md`

```markdown
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
```

---

## Part C: Gemini CLI Extension

Gemini CLI uses a different structure — TOML commands, `GEMINI.md` context file, and inline MCP config.

### C1. `gemini-extension.json`

```json
{
  "name": "neuromem",
  "version": "0.2.0",
  "description": "Brain-inspired persistent memory for coding agents — remember, recall, consolidate, and forget naturally",
  "settings": [
    {
      "name": "OpenAI API Key",
      "description": "API key for embeddings and LLM consolidation (text-embedding-3-large + gpt-4o-mini)",
      "envVar": "OPENAI_API_KEY",
      "sensitive": true
    },
    {
      "name": "Config Path",
      "description": "Path to neuromem.yaml config file (default: ./neuromem.yaml)",
      "envVar": "NEUROMEM_CONFIG",
      "sensitive": false
    },
    {
      "name": "User ID",
      "description": "Unique user ID for memory scoping (default: 'default')",
      "envVar": "NEUROMEM_USER_ID",
      "sensitive": false
    }
  ],
  "contextFileName": "GEMINI.md",
  "mcpServers": {
    "neuromem": {
      "command": "python",
      "args": ["-m", "neuromem.mcp"],
      "cwd": "${workspacePath}"
    }
  }
}
```

**Note**: `settings` with `sensitive: true` are stored in the system keychain. Env vars (`OPENAI_API_KEY`, `NEUROMEM_CONFIG`, `NEUROMEM_USER_ID`) are automatically injected into the MCP server process environment.

### C2. `GEMINI.md`

```markdown
# NeuroMem — Brain-Inspired Memory System

You have access to a persistent memory system via the NeuroMem MCP tools. This system gives you four types of memory that work like the human brain:

- **Episodic memory**: Recent experiences and conversations (naturally decays over time)
- **Semantic memory**: Stable facts and knowledge (long-lasting, high confidence)
- **Procedural memory**: User preferences and behavioral patterns
- **Affective memory**: Sentiment and emotional context

## Available Commands

- `/remember <text>` — Store a memory
- `/recall <query>` — Search memories semantically
- `/forget <id>` — Delete a memory (shows list if no ID)
- `/memories [type]` — Browse stored memories
- `/consolidate` — Promote patterns into stable knowledge

## Automatic Behavior

When the user's question could benefit from past context, proactively search memories using `search_memories`. When the user shares important information (decisions, preferences, facts), store it using `store_memory`.

Do not store trivial exchanges. Do not show raw memory IDs or scores unless asked. If a memory seems outdated, note the discrepancy.

## Advanced Search Syntax

The `search_advanced` tool supports structured queries:
```
type:semantic tag:preference confidence:>0.8 python frameworks
after:2024-01-01 before:2024-12-31 "exact phrase"
intent:question sentiment:positive
```
```

### C3. Commands (`commands/`)

Gemini CLI commands use TOML format. Subdirectories create namespaced commands.

#### `commands/remember.toml`

```toml
description = "Store a memory — saves context, decisions, preferences, or facts for later recall"

prompt = """Use the NeuroMem `store_memory` MCP tool to save this memory:

Content to remember: {{args}}

Choose the appropriate template based on content:
- "preference" if it describes how the user likes things
- "decision" if it records a choice or decision
- "fact" if it states objective information
- "goal" if it sets an objective or target
- Omit template for general information

After storing, confirm what was saved and the detected memory type."""
```

#### `commands/recall.toml`

```toml
description = "Search memories — find relevant context, decisions, or knowledge from past sessions"

prompt = """Use the NeuroMem `search_memories` MCP tool to find relevant memories.

Search query: {{args}}

Set k=10 for a comprehensive search.

Present results clearly:
- Show each memory's content, type, confidence, and tags
- Note any low-confidence (<0.5) memories that may be fading
- Group by memory type if more than 5 results
- If no results, suggest alternative search terms or the structured `search_advanced` syntax"""
```

#### `commands/forget.toml`

```toml
description = "Delete a specific memory by ID, or browse recent memories to pick one"

prompt = """The user wants to delete a memory.

Memory ID provided: {{args}}

If a memory ID was provided:
1. First call `get_memory` to show what will be deleted
2. Ask for confirmation
3. If confirmed, call `delete_memory`

If no ID was provided:
1. Call `list_memories` with limit=20
2. Show the list with short IDs
3. Ask the user which one to delete"""
```

#### `commands/memories.toml`

```toml
description = "List and browse all stored memories with optional type filter (episodic, semantic, procedural)"

prompt = """Browse the user's stored memories.

Type filter: {{args}}

If a type was specified (episodic, semantic, or procedural):
- Call `list_memories` with that memory_type and limit=30

If no filter:
- First call `get_stats` for an overview
- Then call `list_memories` with limit=20

Show results as a formatted list:
- ID (first 8 chars), Content (truncated), Type, Confidence, Tags, Age
- Mention total count and whether more exist"""
```

#### `commands/consolidate.toml`

```toml
description = "Trigger memory consolidation — promotes recurring episodic patterns into stable semantic knowledge"

prompt = """Run NeuroMem memory consolidation.

First explain what will happen:
- Episodic memories are reviewed for recurring patterns
- Stable facts are extracted and promoted to semantic memory
- Behavioral patterns become procedural memory
- Ebbinghaus forgetting curves decay weak memories
- Similar facts are merged to reduce redundancy

Then call the `consolidate` MCP tool.

After completion, call `get_stats` to show updated memory counts so the user can see what changed."""
```

### C4. `README.md`

```markdown
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
```

---

## Part D: Universal Integration Guide (`plugins/docs/INTEGRATION_GUIDE.md`)

This is for ALL platforms, including those that don't need a full plugin.

```markdown
# NeuroMem Integration Guide — All Platforms

NeuroMem's MCP server works with every major coding agent and AI platform.

## Prerequisites (all platforms)

1. Install NeuroMem SDK with MCP support:
   ```bash
   pip install neuromem-sdk[mcp]
   ```

2. Create a `neuromem.yaml` config file (or copy from `examples/neuromem.yaml`)

3. Set your OpenAI API key:
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

4. Verify the MCP server starts:
   ```bash
   python -m neuromem.mcp
   # Should start without errors (ctrl+C to stop)
   ```

---

## Platforms with Full Plugin Support

### Claude Code
See `plugins/claude-code/README.md` — full plugin with commands, agent, skill, and hooks.

```bash
cd plugins/claude-code && claude plugin install .
```

### OpenAI Codex CLI
See `plugins/codex-cli/README.md` — plugin with skill and MCP.

```bash
cp -r plugins/codex-cli ~/.agents/plugins/neuromem
```

### Gemini CLI
See `plugins/gemini-cli/README.md` — extension with TOML commands and context.

```bash
cd plugins/gemini-cli && gemini extensions link .
```

---

## Platforms with MCP-Only Support

These platforms support MCP natively. Add the NeuroMem server to their config:

### Cline (VS Code Extension)

Open Cline settings and add to MCP servers, or edit `cline_mcp_settings.json`:
```json
{
  "mcpServers": {
    "neuromem": {
      "command": "python",
      "args": ["-m", "neuromem.mcp"],
      "env": {
        "NEUROMEM_CONFIG": "./neuromem.yaml",
        "OPENAI_API_KEY": "your-key-here"
      }
    }
  }
}
```

### Cursor

Settings > Features > MCP > Add Server:
```json
{
  "neuromem": {
    "command": "python",
    "args": ["-m", "neuromem.mcp"],
    "env": {
      "NEUROMEM_CONFIG": "./neuromem.yaml",
      "OPENAI_API_KEY": "your-key-here"
    }
  }
}
```

### Windsurf / Cascade

Add via Windsurf Settings > MCP Servers:
```json
{
  "neuromem": {
    "command": "python",
    "args": ["-m", "neuromem.mcp"],
    "env": {
      "NEUROMEM_CONFIG": "./neuromem.yaml",
      "OPENAI_API_KEY": "your-key-here"
    }
  }
}
```

### GitHub Copilot (Agent Mode)

Add to your repository's MCP config or VS Code settings:
```json
{
  "mcpServers": {
    "neuromem": {
      "command": "python",
      "args": ["-m", "neuromem.mcp"],
      "env": {
        "NEUROMEM_CONFIG": "./neuromem.yaml",
        "OPENAI_API_KEY": "your-key-here"
      }
    }
  }
}
```
Note: Copilot coding agent only supports MCP tools (not resources or prompts).

### Aider

Community MCP support via mcpm-aider or direct configuration. See Aider docs for current MCP integration status.

---

## Cloud AI Platforms (Remote HTTP)

For Claude.ai, ChatGPT, and Google AI Studio, run the MCP server in HTTP mode:

```bash
python -m neuromem.mcp --transport http --port 8000
```

This starts a Streamable HTTP server at `http://localhost:8000/mcp`.

For production, deploy behind HTTPS (e.g., with nginx, Caddy, or a cloud provider).

### Claude.ai

1. Go to Settings > Connectors > Add Custom Connector
2. Enter name: "NeuroMem"
3. Enter MCP server URL: `https://your-server.com/mcp`
4. Works on web, iOS, and Android

### ChatGPT

1. Go to Settings > Connectors > Advanced > Developer Mode
2. Add MCP server URL: `https://your-server.com/mcp`
3. The 12 NeuroMem tools will appear as available actions

### Google AI Studio

Use the Google Gen AI SDK to connect:
```python
from google import genai
client = genai.Client()
# Connect MCP server as tool provider
```

---

## Available MCP Tools

All platforms get access to these 12 tools:

| Tool | Description |
|------|-------------|
| `store_memory` | Store a user-assistant interaction with auto-type detection |
| `search_memories` | Semantic search with multi-hop query decomposition |
| `search_advanced` | Structured query syntax (type:, tag:, confidence:>, dates) |
| `get_context` | Retrieve with graph-expanded context (related memories attached) |
| `get_memory` | Get a specific memory by ID |
| `list_memories` | List memories with optional type filter |
| `update_memory` | Update memory content |
| `delete_memory` | Delete a memory |
| `consolidate` | Trigger episodic-to-semantic consolidation |
| `get_stats` | Memory system statistics and health |
| `find_by_tags` | Hierarchical tag search |
| `get_graph` | Export entity-relationship knowledge graph |

## Storage Backends

Configure in `neuromem.yaml`:

| Backend | Best For | Config |
|---------|----------|--------|
| In-Memory | Development, testing | `type: memory` |
| SQLite | Single-user local | `type: sqlite` |
| PostgreSQL + pgvector | Production | `type: postgres` |
| Qdrant | High-scale vector search | `type: qdrant` |
```

---

## Implementation Order

1. **`plugins/claude-code/`** — Full plugin (richest integration, most files)
   - `.claude-plugin/plugin.json`
   - `.mcp.json`
   - 5 commands in `commands/`
   - 1 skill in `skills/neuromem/SKILL.md`
   - 1 agent in `agents/memory-assistant.md`
   - hooks in `hooks/hooks.json`
   - `README.md`

2. **`plugins/codex-cli/`** — Plugin (manifest + MCP + skill)
   - `.codex-plugin/plugin.json`
   - `.mcp.json`
   - 1 skill in `skills/neuromem/SKILL.md`
   - `README.md`

3. **`plugins/gemini-cli/`** — Extension (manifest + commands + context)
   - `gemini-extension.json`
   - `GEMINI.md`
   - 5 commands in `commands/`
   - `README.md`

4. **`plugins/docs/INTEGRATION_GUIDE.md`** — Universal guide for all 10+ platforms

---

## Quality Checklist

### Claude Code Plugin
- [ ] `plugin.json` is valid JSON with all required fields
- [ ] `.mcp.json` uses `${user_config.*}` references correctly
- [ ] All 5 commands use `$ARGUMENTS` for user input
- [ ] Skill has `user-invocable: false` (auto-triggered only)
- [ ] Agent lists all relevant MCP tools
- [ ] `hooks.json` has valid SessionStart hook
- [ ] README documents installation, setup, commands, and prerequisites
- [ ] Test: `claude plugin install .` from `plugins/claude-code/` works
- [ ] Test: `/remember test`, `/recall test`, `/memories`, `/consolidate` work

### Codex CLI Plugin
- [ ] `plugin.json` has `name` and `version` (required fields)
- [ ] `interface` section has `displayName`, `shortDescription`, `defaultPrompt`
- [ ] `.mcp.json` references `OPENAI_API_KEY` from env
- [ ] Skill covers all 12 MCP tools in its description
- [ ] README documents installation and usage

### Gemini CLI Extension
- [ ] `gemini-extension.json` has `name`, `version`, `description` (all required)
- [ ] `settings` array includes sensitive flag for API key
- [ ] All 5 TOML commands have `prompt` (required) and `description` (recommended)
- [ ] Commands use `{{args}}` for argument substitution (NOT `$ARGUMENTS`)
- [ ] `GEMINI.md` provides clear behavioral guidance
- [ ] README documents installation via `gemini extensions link .`
- [ ] Test: `gemini extensions link .` from `plugins/gemini-cli/` works

### Integration Guide
- [ ] Covers all 10+ platforms (Claude Code, Codex, Gemini CLI, Cline, Cursor, Windsurf, Copilot, Aider, Claude.ai, ChatGPT, Google AI Studio)
- [ ] Each platform has copy-paste JSON config
- [ ] Prerequisites section is clear
- [ ] HTTP transport documented for cloud platforms
- [ ] All 12 MCP tools listed

### General
- [ ] No hardcoded API keys or secrets in any file
- [ ] All README files are accurate and complete
- [ ] File structure matches the spec exactly
- [ ] No modifications to existing NeuroMem core code or Phase 1 MCP server

---

## Key Reminders

1. **Do NOT modify Phase 1 files** — the MCP server (`neuromem/mcp/`) is complete. Plugins just configure and wrap it.
2. **Platform-specific syntax matters**:
   - Claude Code commands use `$ARGUMENTS` for args
   - Gemini CLI commands use `{{args}}` for args
   - Claude Code skills use YAML frontmatter with many optional fields
   - Codex CLI skills use minimal YAML frontmatter (just `name` and `description`)
3. **Test each plugin on its platform** if you have access. At minimum, verify JSON/TOML validity.
4. **userConfig vs env vars**: Claude Code has `userConfig` (prompted at install). Gemini CLI has `settings` (stored in keychain). Codex CLI relies on system env vars.
5. **MCP tool names must match Phase 1 exactly**: `store_memory`, `search_memories`, `search_advanced`, `get_context`, `get_memory`, `list_memories`, `update_memory`, `delete_memory`, `consolidate`, `get_stats`, `find_by_tags`, `get_graph`.
