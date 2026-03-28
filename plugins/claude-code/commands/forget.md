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
