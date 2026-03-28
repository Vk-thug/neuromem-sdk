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
