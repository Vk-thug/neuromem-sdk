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
