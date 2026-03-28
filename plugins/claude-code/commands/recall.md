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
