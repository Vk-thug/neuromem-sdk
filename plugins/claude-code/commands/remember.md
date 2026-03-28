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
