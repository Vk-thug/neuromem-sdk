# NeuroMem SDK - Getting Started

## ✅ Installation Complete!

The NeuroMem SDK has been successfully installed in development mode.

---

## 🚀 Quick Test

Verify the installation:

```bash
python -c "from neuromem import NeuroMem, UserManager; print('✅ NeuroMem SDK ready!')"
```

---

## 📝 Next Steps

### 1. **Basic Usage**

Run the basic examples to see core functionality:

```bash
python examples/basic_usage.py
```

This demonstrates:
- User creation
- Memory operations
- LangChain integration
- Memory control

### 2. **Demo Agent (with or without OpenAI)**

The demo agent works with or without an OpenAI API key:

```bash
# Without API key (uses mock responses)
python examples/demo_agent.py

# With API key (uses real LLM)
export OPENAI_API_KEY=your_key_here
python examples/demo_agent.py
```

### 3. **Production Example**

For a complete production-ready example with LangGraph:

```bash
# Install additional dependencies
pip install langgraph openai

# Set API key
export OPENAI_API_KEY=your_key_here

# Run production example
python examples/langgraph_production.py
```

---

## 🔧 Configuration

The default configuration uses **in-memory storage** (no persistence).

### For Development (SQLite)

Edit `neuromem.yaml`:

```yaml
storage:
  database:
    type: sqlite
    url: neuromem.db
```

### For Production (PostgreSQL)

1. Install PostgreSQL with pgvector:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install postgresql postgresql-contrib postgresql-15-pgvector
   
   # Create database
   createdb neuromem
   ```

2. Edit `neuromem.yaml`:
   ```yaml
   storage:
     database:
       type: postgres
       url: postgresql://user:pass@localhost:5432/neuromem
   ```

---

## 💡 Usage Patterns

### Simple Memory

```python
from neuromem import NeuroMem, UserManager

# Create user
user = UserManager.create(external_id="user_123")

# Initialize memory
memory = NeuroMem.from_config("neuromem.yaml", user_id=user.id)

# Store interaction
memory.observe("I prefer concise answers", "Got it!")

# Retrieve memories
context = memory.retrieve("How should I answer?", k=5)
```

### With LangChain

```python
from neuromem import NeuroMem
from langchain.chains import LLMChain

memory = NeuroMem.for_langchain(user_id=user.id)
chain = LLMChain(llm=llm, prompt=prompt, memory=memory)
```

### With LangGraph

```python
from langgraph.graph import StateGraph
from neuromem import NeuroMem
from neuromem.adapters.langgraph import create_memory_node, AgentState

memory = NeuroMem.for_langgraph(user_id=user.id)

graph = StateGraph(AgentState)
graph.add_node("memory", create_memory_node(memory))
graph.add_node("agent", agent_node)

graph.set_entry_point("memory")
graph.add_edge("memory", "agent")

app = graph.compile()
```

---

## 📚 Documentation

- **README.md** - Full SDK documentation
- **QUICKSTART.md** - Setup guide
- **examples/README.md** - Example descriptions
- **Walkthrough** - Implementation details

---

## 🧪 Testing

The SDK includes multiple test approaches:

1. **Import Test** (quick):
   ```bash
   python -c "from neuromem import NeuroMem; print('OK')"
   ```

2. **Basic Examples**:
   ```bash
   python examples/basic_usage.py
   ```

3. **Demo Agent**:
   ```bash
   python examples/demo_agent.py
   ```

---

## 🎯 Key Features Demonstrated

✅ **Multi-layer memory** (Session, Episodic, Semantic, Procedural)
✅ **Brain-inspired retrieval** (not just vector similarity)
✅ **Memory consolidation** (episodic → semantic/procedural)
✅ **Memory decay** (Ebbinghaus forgetting curve)
✅ **User style learning** (procedural memory)
✅ **Full user control** (list, explain, update, forget)
✅ **LangChain integration** (drop-in replacement)
✅ **LangGraph integration** (node factories)
✅ **Multiple storage backends** (in-memory, SQLite, PostgreSQL)

---

## 🔥 What Makes This Special

Unlike traditional RAG or vector databases, NeuroMem:

- **Models memory dynamics**, not just storage
- **Learns user style** and adapts responses
- **Consolidates memories** over time
- **Forgets** unreinforced information
- **Explains** why memories are retrieved
- **Gives users control** over their memories

---

## 📞 Support

For issues or questions:
- Check the examples in `examples/`
- Review the README.md
- See the walkthrough documentation

---

**🎉 You're ready to build memory-enabled AI agents!**
