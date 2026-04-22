<p align="center">
  <h1 align="center">NeuroMem SDK</h1>
  <p align="center">
    Brain-inspired memory infrastructure for AI agents.
    <br />
    Graph-based relationships. Multi-framework. MCP-native.
  </p>
</p>

<p align="center">
  <a href="https://pypi.org/project/neuromem-sdk/"><img src="https://img.shields.io/pypi/v/neuromem-sdk?color=blue" alt="PyPI" /></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+" /></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License" /></a>
  <a href="https://github.com/Vk-thug/neuromem-sdk"><img src="https://img.shields.io/badge/status-beta-green.svg" alt="Status" /></a>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &middot;
  <a href="#framework-adapters">Adapters</a> &middot;
  <a href="#mcp-server">MCP Server</a> &middot;
  <a href="#benchmarks">Benchmarks</a> &middot;
  <a href="RELEASE_NOTES_v0.2.0.md">Release Notes</a>
</p>

---

## What is NeuroMem?

NeuroMem is a **multi-layer memory system** modeled after human cognition. It gives AI agents the ability to remember experiences, learn stable facts, adapt to user preferences, and forget naturally — across any framework.

```
Episodic Memory ── recent interactions, conversations, events
Semantic Memory ── consolidated facts, knowledge, learned patterns
Procedural Memory ── behavioral preferences, user style, habits
Session Memory ── current conversation context (RAM-only)
```

Memories are connected through a **knowledge graph** with entity extraction, enabling retrieval that goes beyond vector similarity — surfacing related memories through relationship traversal.

### Key Capabilities

- **Graph-augmented retrieval** — entity-linked memory graph with backlinks, clusters, and bridge detection
- **Multi-factor scoring** — similarity (0.45) + salience (0.20) + recency (0.15) + reinforcement (0.10) + confidence (0.10)
- **Structured query syntax** — filter by type, tag, confidence, date range, sentiment, intent
- **Natural forgetting** — Ebbinghaus decay curves with reinforcement on access
- **LLM-powered consolidation** — automatic episodic-to-semantic promotion via fact extraction
- **8 framework adapters** — LangChain, LangGraph, LiteLLM, CrewAI, AutoGen, DSPy, Haystack, Semantic Kernel
- **MCP server** — 12 tools for any MCP-compatible client (Claude, Cursor, etc.)
- **4 storage backends** — PostgreSQL+pgvector, Qdrant, SQLite, In-Memory

---

## Quick Start

### Install

```bash
pip install neuromem-sdk
```

With optional integrations:

```bash
pip install neuromem-sdk[langchain]          # LangChain adapter
pip install neuromem-sdk[langgraph]          # LangGraph adapter
pip install neuromem-sdk[crewai]             # CrewAI adapter
pip install neuromem-sdk[mcp]               # MCP server
pip install neuromem-sdk[postgres]           # PostgreSQL backend
pip install neuromem-sdk[qdrant]             # Qdrant backend
pip install neuromem-sdk[all]               # Everything
```

### Configure

Create a `neuromem.yaml`:

```yaml
neuromem:
  model:
    embedding: text-embedding-3-large
    consolidation_llm: gpt-4o-mini

  storage:
    database:
      type: memory          # memory | postgres | sqlite | qdrant

  memory:
    decay_enabled: true
    consolidation_interval: 10

  retrieval:
    hybrid_enabled: true

  async:
    enabled: false
```

Set your API key:

```bash
export OPENAI_API_KEY=sk-...
```

### Use

```python
from neuromem import NeuroMem

memory = NeuroMem.from_config("neuromem.yaml", user_id="user_123")

# Store an interaction
memory.observe(
    user_input="I prefer Python over JavaScript for backend work",
    assistant_output="Noted — I'll prioritize Python examples."
)

# Retrieve relevant memories
results = memory.retrieve(query="What languages does the user prefer?", k=5)
for item in results:
    print(f"[{item.memory_type}] {item.content}")

# Consolidate episodic memories into semantic facts
memory.consolidate()

# Cleanup
memory.close()
```

---

## Framework Adapters

NeuroMem integrates with 8 frameworks through drop-in adapters. All adapters use lazy imports — the framework package is only loaded when called.

### LangChain

```python
from neuromem import NeuroMem
from neuromem.adapters.langchain import add_memory

memory = NeuroMem.for_langchain(user_id="user_123")
chain_with_memory = add_memory(chain, memory, k=5)
response = chain_with_memory.invoke({"input": "What are my preferences?"})
```

### LangGraph

```python
from neuromem import NeuroMem
from neuromem.adapters.langgraph import with_memory

memory = NeuroMem.for_langgraph(user_id="user_123")
app = with_memory(graph.compile(), memory)
result = app.invoke({"input": "Hello"})
```

### CrewAI

```python
from neuromem import NeuroMem
from neuromem.adapters.crewai import create_neuromem_tools

memory = NeuroMem.for_crewai(user_id="user_123")
tools = create_neuromem_tools(memory, k=5)
# tools: [NeuroMemSearchTool, NeuroMemStoreTool, NeuroMemConsolidateTool, NeuroMemContextTool]
```

### AutoGen (AG2)

```python
from neuromem import NeuroMem
from neuromem.adapters.autogen import register_neuromem_tools

memory = NeuroMem.for_autogen(user_id="user_123")
register_neuromem_tools(memory, caller=assistant, executor=user_proxy, k=5)
```

### DSPy

```python
from neuromem import NeuroMem
from neuromem.adapters.dspy import NeuroMemRetriever

memory = NeuroMem.for_dspy(user_id="user_123")
retriever = NeuroMemRetriever(memory, k=5)  # Drop-in dspy.Retrieve replacement
```

### Haystack

```python
from neuromem import NeuroMem
from neuromem.adapters.haystack import NeuroMemRetriever, NeuroMemWriter

memory = NeuroMem.for_haystack(user_id="user_123")
pipeline.add_component("retriever", NeuroMemRetriever(memory, top_k=5))
pipeline.add_component("writer", NeuroMemWriter(memory))
```

### Semantic Kernel

```python
from neuromem import NeuroMem
from neuromem.adapters.semantic_kernel import create_neuromem_plugin

memory = NeuroMem.for_semantic_kernel(user_id="user_123")
plugin = create_neuromem_plugin(memory, k=5)
# Exposes: search_memory, store_memory, get_context, consolidate
```

### LiteLLM

```python
from neuromem import NeuroMem
from neuromem.adapters.litellm import completion_with_memory

memory = NeuroMem.for_litellm(user_id="user_123")
response = completion_with_memory(
    model="gpt-4",
    messages=[{"role": "user", "content": "What do I like?"}],
    memory=memory
)
```

---

## MCP Server

NeuroMem ships as a standalone MCP server with 12 tools, 3 resources, and 2 prompts.

```bash
pip install neuromem-sdk[mcp]

# Start the server
python -m neuromem.mcp
# Or: neuromem-mcp
```

### Tools

| Tool | Description |
|------|-------------|
| `store_memory` | Store observations with auto-template detection |
| `search_memories` | Semantic search with multi-hop decomposition |
| `search_advanced` | Structured query syntax with filters |
| `get_context` | Retrieve with graph-based context expansion |
| `get_memory` | Get a specific memory by ID |
| `list_memories` | List memories with optional type filtering |
| `update_memory` | Modify existing memory content |
| `delete_memory` | Permanently delete a memory |
| `consolidate` | Trigger episodic-to-semantic promotion |
| `get_stats` | System statistics and health status |
| `find_by_tags` | Hierarchical tag-based lookup |
| `get_graph` | Export the memory relationship graph |

### Claude Code Integration

```json
{
  "mcpServers": {
    "neuromem": {
      "command": "neuromem-mcp",
      "env": {
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

---

## Graph Memory

Memories are linked through a knowledge graph with 5 relationship types:

```
derived_from  — semantic memory created from episodic sources
contradicts   — conflicting memories
reinforces    — strengthening relationships
related       — similar content detected
supersedes    — newer memory replaces older
```

```python
# Retrieve with graph context expansion
context = memory.retrieve_with_context(query="What does the user prefer?", k=5)

# Export the graph
graph = memory.get_graph()  # { nodes: [...], edges: [...] }
```

Entity extraction runs inline during `observe()` — lightweight, no external dependencies, <1ms. Entities are indexed for O(1) lookup during retrieval.

---

## Structured Query Syntax

```python
# Filter by type and confidence
results = memory.search('type:semantic confidence:>0.8 python')

# Date range with exact phrase
results = memory.search('after:2024-01-01 before:2024-12-31 "machine learning"')

# Sentiment and intent
results = memory.search('intent:question sentiment:positive')

# Tag hierarchy
results = memory.find_by_tags("preference/", limit=20)
tag_tree = memory.get_tag_tree()
```

**Operators:** `type:`, `tag:`, `confidence:`, `salience:`, `after:`, `before:`, `intent:`, `sentiment:`, `source:`, `"exact phrase"`

---

## Memory Templates

Structured observation templates with auto-detection:

```python
# Auto-detected from keywords
memory.observe(
    user_input="I prefer dark mode in all my IDEs",
    assistant_output="Noted."
)
# Detected as "preference" → salience=0.9, tags=["preference"]

# Explicit template
memory.observe(
    user_input="I decided to use PostgreSQL",
    assistant_output="Good choice.",
    template="decision"
)
```

| Template | Salience | Auto-detected Keywords |
|----------|----------|----------------------|
| `decision` | 0.8 | decided, chose, picked, settled on |
| `preference` | 0.9 | prefer, like, want, love, hate |
| `fact` | 0.7 | my name is, I am, I work, I use |
| `goal` | 0.85 | want to, planning to, goal is |
| `feedback` | 0.75 | feedback, suggestion, improve |

---

## Temporal Summaries

```python
# Daily digest
summary = memory.daily_summary(date="2026-03-28")
# { date, summary, memory_count, key_topics, key_facts, sentiment_distribution }

# Weekly digest
digest = memory.weekly_digest(week_start="2026-03-25")
```

---

## Storage Backends

| Backend | Install | Use Case |
|---------|---------|----------|
| **In-Memory** | Built-in | Development, testing |
| **SQLite** | Built-in | Local development, small datasets |
| **PostgreSQL + pgvector** | `pip install neuromem-sdk[postgres]` | Production, large-scale |
| **Qdrant** | `pip install neuromem-sdk[qdrant]` | Production, high-performance vector search |

```yaml
# PostgreSQL
storage:
  database:
    type: postgres
    url: postgresql://user:pass@localhost:5432/neuromem

# Qdrant
storage:
  vector_store:
    type: qdrant
    config:
      host: localhost
      port: 6333
      collection_name: neuromem
```

---

## Benchmarks

**NeuroMem v0.3.2 beats MemPalace on all three industry retrieval benchmarks** — MemBench (ACL 2025), LongMemEval, and ConvoMem — using the same embeddings (`all-MiniLM-L6-v2`), same data, and the same cross-encoder (`ms-marco-MiniLM-L-12-v2`).

### Head-to-head vs MemPalace (2026-04-22)

| Benchmark | Items | NeuroMem v0.3.2 R@5 | MemPalace R@5 | Delta | NeuroMem config |
|---|---:|---:|---:|---:|---|
| **MemBench** | 330 | **97.0%** | 87.9% | **+9.1** 🟢 | `--verbatim-only` (default blends) |
| **LongMemEval** | 100 | **98.0%** | 94.0% | **+4.0** 🟢 | cognitive defaults |
| **ConvoMem** | 150 | **81.3%** | 80.7% | **+0.6** 🟢 | `--verbatim-only --bm25-blend 0.0 --ce-blend 0.9` |

### MemBench per-task breakdown (11 tasks, 30 items each)

| Task | NeuroMem | MemPalace | Delta |
|---|---:|---:|---:|
| `aggregative` | 100.0% | 100.0% | — |
| `comparative` | 100.0% | 100.0% | — |
| `conditional` | 96.7% | 83.3% | +13.4 |
| `highlevel` | 100.0% | 93.3% | +6.7 |
| `highlevel_rec` | 80.0% | 76.7% | +3.3 |
| `knowledge_update` | 100.0% | 93.3% | +6.7 |
| `lowlevel_rec` | 100.0% | 100.0% | — |
| `noisy` | 96.7% | 73.3% | **+23.4** |
| `post_processing` | 100.0% | 76.7% | **+23.3** |
| `RecMultiSession` | 100.0% | 100.0% | — |
| `simple` | 93.3% | 70.0% | **+23.3** |

NeuroMem wins 7 of 11 categories; ties the other 4 at 100%.

### Workload-specific retrieval recipes (v0.3.2+)

`bm25_blend` and `ce_blend` are configurable in `neuromem.yaml` under `retrieval:`. Tune per dominant query profile:

```yaml
retrieval:
  # Exact-fact recall (phone, dates, proper nouns, IDs) — DEFAULT
  bm25_blend: 0.5
  ce_blend: 0.9

  # Abstract advice-seeking ("what should I look into...", "how can I...")
  # bm25_blend: 0.0
  # ce_blend: 0.9

  # Pure semantic search (MemPalace-equivalent)
  # bm25_blend: 0.0
  # ce_blend: 0.0
```

### Reproduce the benchmarks

```bash
# MemBench (~5 min, beats MemPalace by +9.1)
python -m benchmarks.run_benchmark --benchmark membench --systems neuromem mempalace \
  --embedding-provider sentence-transformers --embedding-model all-MiniLM-L6-v2 \
  --verbatim-only --search-k 10 --max-per-slice 30 --no-judge

# LongMemEval (~12 min, beats MemPalace by +4.0)
python -m benchmarks.run_benchmark --benchmark longmemeval --systems neuromem mempalace \
  --embedding-provider sentence-transformers --embedding-model all-MiniLM-L6-v2 \
  --search-k 100 --max-questions 100 --no-judge

# ConvoMem (~3 min, beats MemPalace by +0.6)
python -m benchmarks.run_benchmark --benchmark convomem --systems neuromem \
  --embedding-provider sentence-transformers --embedding-model all-MiniLM-L6-v2 \
  --verbatim-only --bm25-blend 0.0 --ce-blend 0.9 \
  --search-k 30 --max-per-slice 30 --no-judge
```

### Honest open item

LongMemEval `multi-session` sub-category: 93.3% (2/30 counting-type queries miss because they need all 4 relevant sessions in top-5). Quorum / multi-hop coverage fix parked for v0.4.0.

### Earlier benchmark (LoCoMo, v0.2.0 reference)

For historical context — [LoCoMo benchmark](https://github.com/snap-research/locomo) (ACL 2024), Categories 1+4:

| System | F1 | Exact Match | Retrieval Hit Rate |
|--------|-----|------------|-------------------|
| **NeuroMem v0.2.0** | **39.4** | **15.0%** | **36.7%** |
| LangMem | 32.7 | 11.7% | 33.3% |
| Mem0 | 30.6 | 10.0% | 21.7% |

---

## API Reference

### Core

```python
NeuroMem.from_config(config_path, user_id)      # Initialize from YAML
NeuroMem.for_langchain(user_id, config_path)     # LangChain constructor
NeuroMem.for_langgraph(user_id, config_path)     # LangGraph constructor
NeuroMem.for_crewai(user_id, config_path)        # CrewAI constructor
NeuroMem.for_autogen(user_id, config_path)       # AutoGen constructor
NeuroMem.for_dspy(user_id, config_path)          # DSPy constructor
NeuroMem.for_haystack(user_id, config_path)      # Haystack constructor
NeuroMem.for_semantic_kernel(user_id, config_path) # Semantic Kernel constructor
NeuroMem.for_mcp(user_id, config_path)           # MCP constructor
NeuroMem.for_litellm(user_id, config_path)       # LiteLLM constructor
```

### Memory Operations

```python
memory.observe(user_input, assistant_output, template=None)
memory.retrieve(query, task_type="chat", k=8, parallel=True)
memory.retrieve_with_context(query, task_type="chat", k=5)
memory.search(query_string, k=10)
memory.consolidate()
memory.list(memory_type=None, limit=50)
memory.update(memory_id, content)
memory.forget(memory_id)
memory.explain(memory_id)
memory.close()
```

### Graph & Discovery

```python
memory.get_graph()                                # Export graph as {nodes, edges}
memory.find_by_tags(tag_prefix, limit=20)         # Hierarchical tag search
memory.get_tag_tree()                             # Tag hierarchy with counts
memory.get_memories_by_date(date)                 # Temporal retrieval
memory.get_memories_in_range(start, end, memory_type)
```

### Summaries

```python
memory.daily_summary(date)                        # Daily memory digest
memory.weekly_digest(week_start)                  # Weekly summary
```

---

## Architecture

```
NeuroMem (Facade)
  └── MemoryController
        ├── EpisodicMemory ──┐
        ├── SemanticMemory ──┤── MemoryBackend (Protocol)
        ├── ProceduralMemory ┘
        ├── SessionMemory (RAM-only)
        ├── MemoryGraph (entity index, backlinks, clusters)
        ├── MemoryQuery (structured query parser)
        ├── RetrievalEngine (multi-factor scoring)
        ├── ConsolidationEngine (LLM-powered)
        ├── DecayEngine (Ebbinghaus curves)
        ├── PriorityTaskScheduler (5-level queues)
        ├── IngestWorker (daemon thread)
        ├── MaintenanceWorker (daemon thread)
        └── Policies (salience, reconsolidation, conflict, optimization)

Storage Backends:
  ├── PostgresBackend (psycopg2 + pgvector)
  ├── QdrantStorage (qdrant-client)
  ├── SQLiteBackend (sqlite3)
  └── InMemoryBackend (dict)

Adapters:
  ├── LangChain (LCEL Runnable, ChatMessageHistory)
  ├── LangGraph (StateGraph nodes, BaseStore)
  ├── CrewAI (BaseTool subclasses)
  ├── AutoGen (callable tools, Teachability-style)
  ├── DSPy (Retrieve module, ReAct tools)
  ├── Haystack (@component pipeline nodes)
  ├── Semantic Kernel (@kernel_function plugin)
  └── LiteLLM (completion wrapper)
```

---

## Development

```bash
# Clone
git clone https://github.com/Vk-thug/neuromem-sdk.git
cd neuromem-sdk

# Install with dev dependencies
pip install -e .[dev]

# Run tests
pytest
pytest --cov=neuromem

# Code quality
black neuromem/ --line-length 100
ruff check neuromem/
mypy neuromem/
```

### Test Coverage

| Suite | Tests |
|-------|-------|
| Core (memory, retrieval, decay) | 50+ |
| Graph memory | 26 |
| Structured query | 31 |
| MCP server | 26 |
| Workflows | 30 |
| Framework adapters | 42 |
| **Total** | **176** |

---

## Roadmap

- [ ] Temporal reasoning improvements (date extraction, time-aware retrieval)
- [ ] Adversarial query detection (calibrated "I don't know" responses)
- [ ] Distributed memory (multi-agent shared state with conflict resolution)
- [ ] Prometheus metrics export
- [ ] CI/CD pipeline with automated benchmarking

---

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

[MIT](LICENSE)

---

## Links

- [PyPI](https://pypi.org/project/neuromem-sdk/)
- [Release Notes](RELEASE_NOTES_v0.2.0.md)
- [Changelog](CHANGELOG.md)
- [Issues](https://github.com/Vk-thug/neuromem-sdk/issues)

---

## Acknowledgments

Benchmark evaluation uses the [LoCoMo dataset](https://github.com/snap-research/locomo) (Maharana et al., ACL 2024). Graph-augmented retrieval is inspired by [HippoRAG](https://arxiv.org/abs/2405.14831). Memory template design draws from [Obsidian](https://obsidian.md/) knowledge management patterns.
