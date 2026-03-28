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
