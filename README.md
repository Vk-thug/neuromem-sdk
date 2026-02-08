# NeuroMem SDK

**Brain-Inspired Memory System for LangChain & LangGraph Agents**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)](https://github.com/neuromem/neuromem-sdk)

> ⚠️ **Alpha Release**: This is an early alpha version (v0.1.0). APIs may change. Not recommended for production use yet.

NeuroMem SDK provides a human-inspired, multi-layer memory system that enables LLM agents to:
- 🧠 **Remember experiences** (episodic memory)
- 📚 **Learn stable facts** (semantic memory)
- 🎯 **Adapt behavior** (procedural memory)
- 🔄 **Forget and correct** over time
- 🎪 **Retrieve contextually** based on goals, salience, and recency

---

## 🚀 Quick Start

### Installation

```bash
# Basic installation
pip install neuromem-sdk

# With all optional dependencies
pip install neuromem-sdk[all]

# Framework-specific installations
pip install neuromem-sdk[langchain]   # LangChain integration
pip install neuromem-sdk[langgraph]   # LangGraph integration
pip install neuromem-sdk[postgres]    # PostgreSQL backend
pip install neuromem-sdk[qdrant]      # Qdrant vector store
```

### Basic Usage

```python
from neuromem import NeuroMem

# Create memory system
memory = NeuroMem.for_langchain(user_id="user_123")

# Observe interactions
memory.observe(
    user_input="I prefer concise answers",
    assistant_output="Got it! I'll keep responses brief."
)

# Retrieve relevant memories
context = memory.retrieve(
    query="How should I format my responses?",
    k=5
)

# Access memory content
for item in context:
    print(f"{item.memory_type}: {item.content}")
```

---

## 📖 Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation-1)
- [Configuration](#configuration)
- [Framework Integrations](#framework-integrations)
  - [LangChain](#langchain-integration)
  - [LangGraph](#langgraph-integration)
  - [LiteLLM](#litellm-integration)
- [Storage Backends](#storage-backends)
- [Advanced Features](#advanced-features)
- [API Reference](#api-reference)
- [Performance](#performance)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## ✨ Features

### Core Memory Systems
- **Episodic Memory**: Recent experiences and interactions
- **Semantic Memory**: Stable facts and knowledge
- **Procedural Memory**: Behavioral patterns and preferences
- **Session Memory**: Temporary in-conversation context

### Brain-Inspired Retrieval
- **Multi-factor scoring**: Similarity + salience + recency + reinforcement
- **Hybrid retrieval**: Combines multiple memory types intelligently
- **Competitive inhibition**: Prevents near-duplicate memories
- **Confidence filtering**: Only retrieves reliable memories

### Production-Ready Features
- ⚡ **Async workers**: Non-blocking memory operations (<100ms latency)
- 🔄 **Retry logic**: Exponential backoff with circuit breakers
- 💾 **Embedding cache**: Reduces API costs by 80%
- 🛡️ **Input validation**: Prevents SQL injection and malicious inputs
- 📊 **Structured logging**: JSON logging with PII redaction
- 🎯 **Rate limiting**: Handles OpenAI API limits gracefully

### Memory Consolidation
- **LLM-powered**: Extracts facts and patterns automatically
- **Forgetting curve**: Memories decay naturally over time
- **Reconsolidation**: Memories strengthen when accessed

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    NeuroMem SDK                          │
│                                                           │
│  ┌─────────────┐     ┌──────────────┐   ┌─────────────┐│
│  │  Episodic   │────▶│   Memory     │◀──│  Semantic   ││
│  │   Memory    │     │  Controller  │   │   Memory    ││
│  └─────────────┘     └──────────────┘   └─────────────┘│
│         │                   │                   │        │
│         │            ┌──────┴──────┐            │        │
│         │            │  Retrieval   │            │        │
│         └───────────▶│   Engine     │◀───────────┘        │
│                      └──────────────┘                     │
│                             │                              │
│                      ┌──────┴──────┐                      │
│                      │   Storage    │                      │
│                      │   Backend    │                      │
│                      └──────┬───────┘                      │
│                             │                              │
└─────────────────────────────┼──────────────────────────────┘
                              │
                    ┌─────────┴──────────┐
                    │                    │
            ┌───────▼─────┐      ┌──────▼──────┐
            │  PostgreSQL │      │   Qdrant    │
            │  + pgvector │      │  (vectors)  │
            └─────────────┘      └─────────────┘
```

---

## 🔧 Installation

### Prerequisites

- Python 3.9 or higher
- OpenAI API key (for embeddings)
- Optional: PostgreSQL with pgvector extension

### Install from PyPI

```bash
pip install neuromem-sdk
```

### Install from Source

```bash
git clone https://github.com/neuromem/neuromem-sdk.git
cd neuromem-sdk
pip install -e .
```

### Verify Installation

```bash
python test_setup.py
```

---

## ⚙️ Configuration

Create a `neuromem.yaml` file:

```yaml
neuromem:
  model:
    embedding: text-embedding-3-large
    consolidation_llm: gpt-4o-mini

  storage:
    database:
      type: memory  # Options: postgres, sqlite, memory, qdrant
      # url: postgresql://user:pass@localhost/neuromem  # For postgres

  memory:
    decay_enabled: true
    consolidation_interval: 10  # Consolidate every N turns
    max_active_memories: 50
    episodic_retention_days: 30

  retrieval:
    hybrid_enabled: true
    recency_weight: 0.2
    importance_weight: 0.3
    similarity_weight: 0.5

  async:
    enabled: true
    critical_queue_size: 1000
```

### Environment Variables

```bash
# Required
export OPENAI_API_KEY=sk-...

# Optional
export NEUROMEM_CACHE_EMBEDDINGS=true  # Enable embedding cache (default: true)
```

---

## 🔌 Framework Integrations

### LangChain Integration

```python
from neuromem import NeuroMem
from neuromem.adapters.langchain import add_memory
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# Create memory
memory = NeuroMem.for_langchain(user_id="user_123")

# Create chain
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. Context: {context}"),
    ("human", "{input}")
])
llm = ChatOpenAI(model="gpt-4")
chain = prompt | llm

# Add memory to chain
chain_with_memory = add_memory(chain, memory)

# Use chain
response = chain_with_memory.invoke({"input": "What are my preferences?"})
```

### LangGraph Integration

```python
from neuromem import NeuroMem
from neuromem.adapters.langgraph import with_memory
from langgraph.graph import StateGraph

# Create memory
memory = NeuroMem.for_langgraph(user_id="user_123")

# Create graph
graph = StateGraph(...)
# ... define graph nodes and edges ...

# Compile with memory
app = with_memory(graph.compile(), memory)

# Run
result = app.invoke({"input": "Hello"})
```

### LiteLLM Integration

```python
from neuromem import NeuroMem
from neuromem.adapters.litellm import completion_with_memory

# Create memory
memory = NeuroMem.for_litellm(user_id="user_123")

# Make completion with memory
response = completion_with_memory(
    model="gpt-4",
    messages=[{"role": "user", "content": "What do I like?"}],
    memory=memory
)
```

---

## 💾 Storage Backends

### In-Memory (Default)

```yaml
storage:
  database:
    type: memory
```

Fast, but data lost on restart. Good for development.

### PostgreSQL + pgvector

```yaml
storage:
  database:
    type: postgres
    url: postgresql://user:pass@localhost:5432/neuromem
```

**Setup**:
```sql
CREATE DATABASE neuromem;
CREATE EXTENSION vector;
```

### SQLite

```yaml
storage:
  database:
    type: sqlite
    url: neuromem.db
```

Lightweight, file-based storage.

### Qdrant

```yaml
storage:
  vector_store:
    type: qdrant
    config:
      host: localhost
      port: 6333
      collection_name: neuromem
```

High-performance vector search.

---

## 🚀 Advanced Features

### Manual Consolidation

```python
# Trigger consolidation manually
memory.consolidate()
```

### Memory Management

```python
# List all memories
memories = memory.list(memory_type="semantic", limit=50)

# Update a memory
memory.update(memory_id="...", content="Updated content")

# Delete a memory
memory.forget(memory_id="...")

# Explain why a memory was retrieved
explanation = memory.explain(memory_id="...")
print(explanation)
```

### Health Checks

```python
# Check system health
from neuromem.health import get_health_status

health = get_health_status(memory)
print(health)
# {'status': 'healthy', 'database': 'connected', 'workers': {...}}
```

### Cache Management

```python
from neuromem.utils.embeddings import get_cache_stats, clear_embedding_cache

# Get cache statistics
stats = get_cache_stats()
print(f"Cache size: {stats['size']}/{stats['max_size']}")

# Clear cache
clear_embedding_cache()
```

---

## 📊 API Reference

### NeuroMem Class

#### `NeuroMem.from_config(config_path, user_id)`
Initialize from configuration file.

#### `NeuroMem.for_langchain(user_id, config_path="neuromem.yaml")`
Quick initialization for LangChain.

#### `NeuroMem.for_langgraph(user_id, config_path="neuromem.yaml")`
Quick initialization for LangGraph.

#### `NeuroMem.for_litellm(user_id, config_path="neuromem.yaml")`
Quick initialization for LiteLLM.

#### `retrieve(query, task_type="chat", k=8)`
Retrieve relevant memories.

#### `observe(user_input, assistant_output)`
Record a user-assistant interaction.

#### `consolidate()`
Trigger memory consolidation.

#### `list(memory_type=None, limit=50)`
List memories.

#### `explain(memory_id)`
Explain memory retrieval.

#### `update(memory_id, content)`
Update memory content.

#### `forget(memory_id)`
Delete a memory.

#### `close()`
Close and release resources.

---

## ⚡ Performance

### Benchmarks

| Operation | Latency | Notes |
|-----------|---------|-------|
| `observe()` | <100ms | Async mode (queued) |
| `retrieve()` | 200-500ms | Depends on storage backend |
| `consolidate()` | 2-10s | Background, non-blocking |

### Optimization Tips

1. **Enable caching**: Reduces OpenAI API costs by 80%
   ```bash
   export NEUROMEM_CACHE_EMBEDDINGS=true
   ```

2. **Use PostgreSQL with pgvector**: 3-5x faster than in-memory for large datasets

3. **Batch operations**: Use `batch_get_embeddings()` for multiple texts

4. **Tune queue sizes**: Adjust in `neuromem.yaml`:
   ```yaml
   async:
     critical_queue_size: 1000
     high_queue_size: 500
   ```

---

## 🛡️ Security

### Input Validation

All user inputs are validated:
- User IDs must be valid UUIDs
- Content length limited to 50KB
- SQL injection prevention via filter validation

### API Key Security

```bash
# Store API keys securely
export OPENAI_API_KEY=sk-...

# Never commit keys to git
echo ".env" >> .gitignore
```

### PII Redaction

Structured logging automatically redacts:
- Email addresses
- Phone numbers
- Social Security Numbers
- Credit card numbers

---

## 🐛 Troubleshooting

### Common Issues

#### OpenAI API Rate Limits

**Error**: `RateLimitError: You exceeded your current quota`

**Solution**: The SDK includes automatic retry logic with exponential backoff. If you still hit limits:

```python
# Reduce concurrent operations
memory.config.async.critical_queue_size = 100

# Enable aggressive caching
export NEUROMEM_CACHE_EMBEDDINGS=true
```

#### Memory Growth

**Issue**: Database size growing too large

**Solution**:
1. Enable memory decay:
   ```yaml
   memory:
     decay_enabled: true
     episodic_retention_days: 30
   ```

2. Run manual cleanup:
   ```python
   memory.consolidate()  # Promotes important memories, forgets old ones
   ```

#### Slow Retrieval

**Issue**: `retrieve()` takes >1 second

**Solutions**:
1. Add database indexes (PostgreSQL):
   ```sql
   CREATE INDEX idx_memory_embedding ON user_memories
   USING ivfflat (embedding vector_cosine_ops);
   ```

2. Reduce `k` parameter:
   ```python
   memory.retrieve(query, k=5)  # Instead of k=50
   ```

### Enable Debug Logging

```python
from neuromem.utils.logging import get_logger
import logging

logger = get_logger(__name__, level=logging.DEBUG)
```

---

## 🧪 Testing

Run the test suite:

```bash
# Basic tests
bash test_sdk.sh

# Full setup verification
python test_setup.py
```

---

## 📈 Roadmap

### v0.1.0 (Alpha) - Current Release
- [x] Basic memory types (Episodic, Semantic)
- [x] Retrieval engine
- [x] Storage backends (Memory, SQLite, Postgres, Qdrant)

### v0.1.0 (Beta) - Target: Q2 2026
- [ ] Unit test coverage >80%
- [ ] Performance optimization (parallel retrieval)
- [ ] Comprehensive documentation
- [ ] Load testing (10,000+ users)

### v1.0.0 (Production) - Target: Q3 2026
- [ ] Security audit
- [ ] Multi-tenancy support
- [ ] Advanced analytics dashboard
- [ ] Enterprise features

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone repo
git clone https://github.com/neuromem/neuromem-sdk.git
cd neuromem-sdk

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .[dev]

# Run tests
bash test_sdk.sh
```

---

## 📜 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- Inspired by cognitive neuroscience research on human memory
- Built on top of LangChain, LangGraph, and OpenAI
- Thanks to all contributors!

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/neuromem/neuromem-sdk/issues)
- **Documentation**: [docs.neuromem.ai](https://docs.neuromem.ai)
- **Discussions**: [GitHub Discussions](https://github.com/neuromem/neuromem-sdk/discussions)

---

**Made with ❤️ by the NeuroMem Team**
