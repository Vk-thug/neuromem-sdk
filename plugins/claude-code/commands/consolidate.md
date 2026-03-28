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
