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
