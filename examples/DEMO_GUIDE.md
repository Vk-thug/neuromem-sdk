# Interactive Demo Agent - Quick Start Guide

## Overview

The updated `demo_agent.py` now features:

✅ **Interactive Chat Interface** - No more hardcoded conversations!  
✅ **Brain-Inspired Optimization** - Auto-tagging, hybrid retrieval, consolidation  
✅ **Real-time Commands** - Control memory operations during chat  
✅ **LangGraph Integration** - Production-ready agent architecture  

## Setup

1. **Install Dependencies**:
```bash
cd /Users/vikramvenkateshkumar/megadot/production/services/neuromem-sdk
source venv/bin/activate
pip install langgraph openai scikit-learn
```

2. **Set OpenAI API Key**:
```bash
export OPENAI_API_KEY=your_key_here
```

3. **Run the Demo**:
```bash
python examples/demo_agent.py
```

## Features

### Interactive Chat
- Type naturally to chat with the agent
- Agent remembers past conversations
- Uses hybrid retrieval for better context

### Chat Commands

- `/stats` - Show memory statistics (episodic, semantic, procedural counts)
- `/consolidate` - Run memory consolidation to extract facts and summaries
- `/quit` - Exit the chat

### Brain-Inspired Features

1. **Auto-Tagging** 🏷️
   - Automatically generates hierarchical tags for each message
   - Tags include: topics, entities, intents, sentiment

2. **Hybrid Retrieval** 🔍
   - Multi-stage ranking combining:
     - Semantic similarity (50%)
     - Recency (20%)
     - Importance (30%)

3. **Memory Consolidation** 🧠
   - Extract semantic facts from conversations
   - Create concise summaries
   - Merge duplicate facts

4. **Embedding Optimization** 💾
   - Reduce storage by 90%
   - PCA dimensionality reduction
   - int8 quantization

## Example Session

```
🧠 NeuroMem Demo Agent with Brain-Inspired Optimization
============================================================

✅ Created user: abc-123
✅ Initialized NeuroMem
✅ Initialized optimization components
✅ OpenAI client initialized
🔧 Building LangGraph...
✅ LangGraph compiled

💬 Interactive Chat Mode
============================================================

Commands:
  /stats    - Show memory statistics
  /consolidate - Run memory consolidation
  /quit     - Exit chat

Start chatting! (or use a command)
============================================================

👤 You: I prefer concise, bullet-point answers

--- Turn 1 ---
  🏷️  Auto-tagging input...
  ✅ Generated 5 tags
  🧠 Retrieving memories for: 'I prefer concise, bullet-point answers'...
  📚 No memories found
  🤖 Calling LLM...
  ✅ LLM response generated
  💾 Storing interaction in memory...
  ✅ Stored with 5 tags

🤖 Agent: Understood! I'll provide:
• Concise responses
• Bullet-point format
• Clear, structured information

👤 You: What is a vector database?

--- Turn 2 ---
  🏷️  Auto-tagging input...
  ✅ Generated 6 tags
  🧠 Retrieving memories for: 'What is a vector database?'...
  📚 Retrieved and ranked 1 memories
  🤖 Calling LLM...
  ✅ LLM response generated
  💾 Storing interaction in memory...
  ✅ Stored with 6 tags

🤖 Agent: Based on your preference for bullet points:

• Database optimized for vector/embedding storage
• Enables fast similarity search
• Uses techniques like ANN (Approximate Nearest Neighbor)
• Common examples: Pinecone, Qdrant, Weaviate
• Key for AI applications like semantic search, RAG

👤 You: /stats

============================================================
📊 Memory Statistics
============================================================

Memory counts:
  - Episodic: 2
  - Semantic: 0
  - Procedural: 0

👤 You: /consolidate

============================================================
🧠 Running Memory Consolidation...
============================================================
Found 2 episodic memories

✅ Consolidation Results:
  - Facts extracted: 2
  - Summaries created: 1

📝 Extracted Facts:
  - [preference] User prefers concise, bullet-point answers (confidence: 0.95)
  - [knowledge] User asked about vector databases (confidence: 0.85)

📋 Conversation Summary:
  Summary: User expressed preference for concise answers and asked about vector databases
  Topics: preferences, databases, vector_search

👤 You: /quit

👋 Goodbye!
```

## Architecture

The agent pipeline flows through these nodes:

```
User Input
    ↓
[Auto-Tagging] - Generate hierarchical tags
    ↓
[Hybrid Retrieval] - Retrieve & rank relevant memories
    ↓
[LLM Agent] - Generate response with context
    ↓
[Observation] - Store interaction with tags
    ↓
Output
```

## Key Improvements

### Before (Old Version)
- ❌ Hardcoded conversations
- ❌ No auto-tagging
- ❌ Basic retrieval
- ❌ No consolidation during chat
- ❌ No interactive commands

### After (New Version)
- ✅ Interactive chat interface
- ✅ Auto-tagging with entities, intents, sentiment
- ✅ Hybrid retrieval with multi-factor ranking
- ✅ On-demand consolidation via `/consolidate`
- ✅ Real-time stats via `/stats`
- ✅ Clean command system

## Tips

1. **Chat naturally** - The agent learns your preferences over time
2. **Use `/consolidate`** after several turns to extract facts
3. **Check `/stats`** to see memory growth
4. **Express preferences** early (e.g., "I like technical depth")
5. **Ask follow-up questions** to test memory recall

## Troubleshooting

**No OpenAI API Key?**
- The demo will use mock responses
- Still demonstrates memory and optimization features

**Import Errors?**
- Make sure you're in the venv: `source venv/bin/activate`
- Install missing packages: `pip install langgraph openai scikit-learn`

**LangGraph Not Available?**
- Install: `pip install langgraph`
- Or use the basic example: `python examples/brain_optimization_example.py`

## Next Steps

After trying the demo:
1. Integrate brain-inspired features into your production code
2. Enable consolidation in `neuromem.yaml`
3. Set up background jobs for automated consolidation
4. Customize hybrid retrieval weights for your use case

Enjoy the optimized memory system! 🧠✨
