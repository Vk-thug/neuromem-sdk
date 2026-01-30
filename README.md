# NeuroMem SDK

**Brain-Inspired Memory System for LangChain & LangGraph Agents**

NeuroMem provides a human-inspired, multi-layer memory system that enables LLM agents to:

- 🧠 **Remember experiences** (episodic memory)
- 📚 **Learn stable facts** (semantic memory)
- 🎯 **Adapt to user style** (procedural memory)
- ⏰ **Forget and correct over time** (memory decay)
- 🎨 **Retrieve based on goal, salience, and context** (brain-inspired retrieval)

All with **one-line integration** into LangChain and LangGraph.

---

## 🚀 Quick Start

### Installation

```bash
pip install neuromem-sdk
```

### Basic Usage

```python
from neuromem import NeuroMem, UserManager

# 1. Create a user
user = UserManager.create(external_id="user_123")

# 2. Initialize memory
memory = NeuroMem.from_config("neuromem.yaml", user_id=user.id)

# 3. Observe interactions
memory.observe(
    user_input="I prefer concise answers",
    assistant_output="Got it! I'll keep responses brief."
)

# 4. Retrieve relevant memories
context = memory.retrieve(
    query="How should I answer?",
    task_type="chat",
    k=5
)

print(context)
```

---

## 🔗 LangChain Integration

```python
from neuromem import NeuroMem
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

# Create memory
memory = NeuroMem.for_langchain(user_id=user.id)

# Use with LangChain
chain = LLMChain(
    llm=llm,
    prompt=prompt,
    memory=memory
)

# Memory is automatically managed
response = chain.run("Design a database agent")
```

---

## 🕸️ LangGraph Integration

```python
from langgraph.graph import StateGraph
from neuromem import NeuroMem
from neuromem.adapters.langgraph import create_memory_node, AgentState

# Create memory
memory = NeuroMem.for_langgraph(user_id=user.id)

# Build graph
graph = StateGraph(AgentState)
graph.add_node("memory", create_memory_node(memory))
graph.add_node("agent", agent_node)

graph.set_entry_point("memory")
graph.add_edge("memory", "agent")

app = graph.compile()

# Run
result = app.invoke({"input": "Explain vector databases"})
```

---

## 🧠 Memory Layers

| Layer | Purpose | Persistence |
|-------|---------|-------------|
| **Session** | Current conversation context | In-RAM |
| **Episodic** | Recent user-agent interactions | Persistent |
| **Semantic** | Stable facts & beliefs | Persistent |
| **Procedural** | User style, habits, preferences | Persistent |

---

## 🎯 Brain-Inspired Retrieval

Unlike pure vector similarity, NeuroMem retrieves memories based on:

```python
score = (
    0.45 * semantic_similarity +
    0.20 * salience +
    0.15 * recency +
    0.10 * reinforcement +
    0.10 * confidence
)
```

This mimics how human memory actually works!

---

## 🔧 Configuration

Create a `neuromem.yaml` file:

```yaml
neuromem:
  model:
    embedding: text-embedding-3-large
    consolidation_llm: gpt-4o-mini

  storage:
    database:
      type: postgres  # or sqlite, memory
      url: postgresql://user:pass@localhost:5432/neuromem

  memory:
    decay_enabled: true
    consolidation_interval: 10
    max_active_memories: 50
```

### Storage Options

- **PostgreSQL + pgvector** - Production-ready with vector search
- **SQLite** - Lightweight for development
- **In-Memory** - Fast, ephemeral (testing)

---

## 🛡️ User Control & Privacy

```python
# List all memories
memories = memory.list(memory_type="semantic")

# Explain why a memory was used
explanation = memory.explain(memory_id)

# Update a memory
memory.update(memory_id, "New content")

# Delete a memory
memory.forget(memory_id)
```

All memories are:
- ✅ Visible to users
- ✅ Editable
- ✅ Deletable
- ✅ Labeled (inferred vs explicit)

---

## 📊 Memory Consolidation

NeuroMem automatically consolidates episodic memories into semantic/procedural:

```python
# Triggered automatically every N turns
memory.consolidate()
```

**Anti-Hallucination Rule:**
> Inferred memories are never promoted without repetition.

---

## 🎨 Procedural Memory (The Moat)

NeuroMem learns **how the user thinks**:

- Preferred answer length
- Structure (bullets vs prose)
- Technical depth
- Tone (analytical, concise, exploratory)
- Vocabulary patterns

This enables truly personalized responses!

---

## 📦 Project Structure

```
neuromem/
├── __init__.py          # Main SDK entry point
├── config.py            # Configuration management
├── user.py              # User lifecycle
├── core/
│   ├── controller.py    # Memory orchestration
│   ├── retrieval.py     # Brain-inspired retrieval
│   ├── consolidation.py # Episodic → Semantic/Procedural
│   ├── decay.py         # Forgetting curves
│   └── types.py         # Core data types
├── memory/
│   ├── session.py       # Working memory
│   ├── episodic.py      # Recent experiences
│   ├── semantic.py      # Stable facts
│   └── procedural.py    # User style & patterns
├── storage/
│   ├── base.py          # Storage protocol
│   ├── postgres.py      # PostgreSQL + pgvector
│   ├── sqlite.py        # SQLite backend
│   └── memory.py        # In-memory backend
├── adapters/
│   ├── langchain.py     # LangChain integration
│   └── langgraph.py     # LangGraph integration
└── utils/
    ├── embeddings.py    # Text → Vector
    └── time.py          # Temporal utilities
```

---

## 🔬 Example: Demo Agent

See `examples/demo_agent.py` for a complete LangGraph agent with memory.

---

## 🚧 Roadmap

### v1 (Current)
- ✅ Episodic, Semantic, Procedural memory
- ✅ LangChain & LangGraph integration
- ✅ PostgreSQL, SQLite, In-Memory backends
- ✅ Brain-inspired retrieval
- ✅ Memory consolidation & decay

### v2
- 🔄 Affective memory (likes/dislikes)
- 🔄 Shared memory across agents
- 🔄 Memory visualization UI

### v3
- 🔄 Memory quality evaluation
- 🔄 Self-healing memory
- 🔄 Multi-modal memory

---

## 📄 License

MIT License - see LICENSE file for details.

---

## 🤝 Contributing

Contributions welcome! Please see CONTRIBUTING.md for guidelines.

---

## 📚 Documentation

Full documentation available at: [docs.neuromem.ai](https://docs.neuromem.ai)

---

## 💡 Philosophy

> "Memory is not storage. Memory is behavior."

NeuroMem models **memory dynamics**, not just data retrieval. This is what makes it fundamentally different from RAG or vector databases.

---

**Built with 🧠 by the NeuroMem team**
