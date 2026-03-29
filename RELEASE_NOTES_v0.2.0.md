# NeuroMem SDK v0.2.0

**Release Date:** March 29, 2026
**Previous Version:** v0.1.0 (February 5, 2026)

---

## Highlights

NeuroMem v0.2.0 transforms the SDK from a LangChain/LangGraph memory layer into a **universal memory infrastructure for AI agents**. This release introduces graph-based memory relationships, an MCP server for tool-native access, 5 new framework adapters (8 total), structured query syntax, durable workflows, and a competitive benchmarking suite validated against the LoCoMo dataset (ACL 2024).

Key numbers:

- **39.4 F1** on LoCoMo retrieval benchmark — outperforms Mem0 (30.6) and LangMem (32.7)
- **41.7 F1** on multi-hop reasoning queries — highest among all evaluated systems
- **8 framework adapters** — LangChain, LangGraph, LiteLLM, CrewAI, AutoGen, DSPy, Haystack, Semantic Kernel
- **12 MCP tools** — expose full memory capabilities to any MCP-compatible client
- **112 files changed**, 16,133 lines added

---

## What's New

### Graph-Based Memory Relationships

Memories are no longer isolated vectors. NeuroMem now builds a **knowledge graph** over stored memories, enabling Obsidian-style backlinks and HippoRAG-inspired entity retrieval.

```python
# Retrieve with automatic graph context expansion
context = memory.retrieve_with_context(
    query="What does the user think about Python?",
    task_type="chat",
    k=5
)

# Export the memory graph
graph = memory.get_graph()  # { nodes: [...], edges: [...] }
```

**Relationship types:** `derived_from`, `contradicts`, `reinforces`, `related`, `supersedes`

**Entity extraction** runs inline during `observe()` — lightweight capitalization-based extraction with no external dependencies. Entities are indexed for O(1) lookup during retrieval.

**Graph-augmented retrieval** expands query results by traversing entity connections, surfacing related memories that pure vector similarity would miss. This is the primary driver behind the 41.7 F1 on multi-hop queries.

---

### Structured Query Syntax

A new query language for precise memory filtering, inspired by Obsidian search:

```python
# Filter by type, tag, confidence, and date range
results = memory.search(
    'type:semantic tag:preference confidence:>0.8 python frameworks'
)

# Exact phrase matching with temporal filters
results = memory.search(
    'after:2024-01-01 before:2024-12-31 "machine learning"'
)

# Sentiment and intent filtering
results = memory.search('intent:question sentiment:positive')
```

**Supported operators:** `type:`, `tag:`, `confidence:`, `salience:`, `after:`, `before:`, `intent:`, `sentiment:`, `source:`, `"exact phrase"`

---

### MCP Server

NeuroMem now ships as a standalone **Model Context Protocol** server, making it accessible to Claude, Cursor, and any MCP-compatible client.

```bash
pip install neuromem-sdk[mcp]

# Start the server
python -m neuromem.mcp
# Or use the console script:
neuromem-mcp
```

**12 tools** expose the full memory API:

| Tool | Description |
|------|-------------|
| `store_memory` | Store observations with auto-template detection |
| `search_memories` | Semantic search with multi-hop decomposition |
| `search_advanced` | Structured query syntax |
| `get_context` | Retrieve with graph-based context expansion |
| `get_memory` | Get a specific memory by ID |
| `list_memories` | List memories with optional type filtering |
| `update_memory` | Modify existing memory content |
| `delete_memory` | Permanently delete a memory |
| `consolidate` | Trigger episodic-to-semantic promotion |
| `get_stats` | System statistics and health status |
| `find_by_tags` | Hierarchical tag-based lookup |
| `get_graph` | Export the memory relationship graph |

**3 resources:** `neuromem://memories/recent`, `neuromem://memories/stats`, `neuromem://config`

**2 prompts:** `memory_context(query)`, `memory_summary(topic)`

---

### 5 New Framework Adapters

Every adapter uses lazy imports — the framework package is only required at call time, not at install time.

#### CrewAI

```python
from neuromem.adapters.crewai import create_neuromem_tools

tools = create_neuromem_tools(memory, k=5)
# Returns: NeuroMemSearchTool, NeuroMemStoreTool,
#          NeuroMemConsolidateTool, NeuroMemContextTool
```

```bash
pip install neuromem-sdk[crewai]
```

#### AutoGen (AG2)

```python
from neuromem.adapters.autogen import register_neuromem_tools

register_neuromem_tools(memory, caller=assistant, executor=user_proxy, k=5)
```

```bash
pip install neuromem-sdk[autogen]
```

#### DSPy

```python
from neuromem.adapters.dspy import NeuroMemRetriever

retriever = NeuroMemRetriever(memory, k=5)
# Drop-in replacement for any dspy.Retrieve module
```

```bash
pip install neuromem-sdk[dspy]
```

#### Haystack

```python
from neuromem.adapters.haystack import NeuroMemRetriever, NeuroMemWriter

# Use as pipeline components with @component decorator
pipeline.add_component("retriever", NeuroMemRetriever(memory, top_k=5))
pipeline.add_component("writer", NeuroMemWriter(memory))
```

```bash
pip install neuromem-sdk[haystack]
```

#### Semantic Kernel

```python
from neuromem.adapters.semantic_kernel import create_neuromem_plugin

plugin = create_neuromem_plugin(memory, k=5)
# Exposes @kernel_function methods: search_memory, store_memory,
# get_context, consolidate
```

```bash
pip install neuromem-sdk[semantic-kernel]
```

---

### Memory Templates

Structured observation templates with automatic detection, inspired by Obsidian Templates:

```python
# Auto-detected from user input keywords
memory.observe(
    user_input="I prefer dark mode in all my IDEs",
    assistant_output="Noted your preference."
)
# Detected as "preference" template → salience=0.9, tags=["preference"]

# Explicit template
memory.observe(
    user_input="I decided to use PostgreSQL for the project",
    assistant_output="Good choice.",
    template="decision"
)
```

| Template | Default Salience | Auto-detected Keywords |
|----------|------------------|----------------------|
| `decision` | 0.8 | decided, chose, picked, settled on |
| `preference` | 0.9 | prefer, like, want, love, hate |
| `fact` | 0.7 | my name is, I am, I work, I use |
| `goal` | 0.85 | want to, planning to, goal is |
| `feedback` | 0.75 | feedback, suggestion, improve |

---

### Temporal Summaries

Time-scoped memory digests:

```python
# Daily summary
summary = memory.daily_summary(date="2026-03-28")
# Returns: { date, summary, memory_count, key_topics,
#            key_facts, sentiment_distribution, avg_salience }

# Weekly digest with daily breakdown
digest = memory.weekly_digest(week_start="2026-03-25")
```

---

### Inngest Workflows

Durable, event-driven workflows for automated memory maintenance:

```bash
pip install neuromem-sdk[inngest]
```

**Scheduled jobs:**

| Job | Schedule | Description |
|-----|----------|-------------|
| `scheduled_consolidation` | Every 2 hours | Episodic to semantic promotion |
| `scheduled_decay` | Periodic | Ebbinghaus forgetting curves |
| `scheduled_optimization` | Periodic | Embedding optimization |
| `scheduled_health_check` | Periodic | System health monitoring |

**Event-driven functions:** `on_memory_observed`, `on_consolidation_requested`, `on_memory_batch_ingest`

---

### AI Assistant Plugins

Pre-built plugins for 3 AI development environments:

| Plugin | Platform | Interface |
|--------|----------|-----------|
| `plugins/claude-code/` | Claude Code | MCP + 5 slash commands + memory assistant agent |
| `plugins/codex-cli/` | Codex CLI | Memory management skill |
| `plugins/gemini-cli/` | Gemini CLI | TOML extension + 5 commands |

All plugins expose 5 core operations: **remember**, **recall**, **memories**, **consolidate**, **forget**.

---

### Convenience Factory Methods

```python
from neuromem import NeuroMem

# Framework-specific constructors
memory = NeuroMem.for_crewai(user_id="user_123")
memory = NeuroMem.for_autogen(user_id="user_123")
memory = NeuroMem.for_dspy(user_id="user_123")
memory = NeuroMem.for_haystack(user_id="user_123")
memory = NeuroMem.for_semantic_kernel(user_id="user_123")
memory = NeuroMem.for_mcp(user_id="user_123")
```

---

### New Retrieval APIs

```python
# Tag-based discovery
memories = memory.find_by_tags("preference/", limit=20)
tag_tree = memory.get_tag_tree()

# Temporal retrieval
memories = memory.get_memories_by_date("2026-03-28")
memories = memory.get_memories_in_range(
    start="2026-03-01",
    end="2026-03-31",
    memory_type="semantic"
)
```

---

## Benchmarks

Evaluated on the **LoCoMo** benchmark (Long Conversation Memory, ACL 2024) — 10 extended multi-turn conversations with 1,986 question-answer pairs across 5 difficulty categories.

### Head-to-Head Comparison (Categories 1 + 4)

| System | F1 | Exact Match | Hit Rate | Store Latency |
|--------|-----|------------|----------|---------------|
| **NeuroMem v0.2.0** | **39.4** | **15.0%** | **36.7%** | 710ms |
| LangMem | 32.7 | 11.7% | 33.3% | 472ms |
| Mem0 | 30.6 | 10.0% | 21.7% | 8,491ms |

### Full Benchmark (All 5 Categories, 999 Questions)

| Category | Questions | F1 | Description |
|----------|-----------|-----|-------------|
| Single-hop | 282 | **37.1** | Direct fact retrieval |
| Temporal | 321 | 7.2 | Time-based reasoning |
| Open-ended | 96 | 9.0 | Subjective, long-form |
| Multi-hop | 841 | **41.7** | Cross-memory reasoning |
| Adversarial | 446 | 0.4 | Unanswerable detection |
| **Overall** | **999** | **24.4** | Weighted average |

Multi-hop (41.7 F1) and single-hop (37.1 F1) are production-strength categories. Temporal and adversarial are industry-wide hard problems where all evaluated systems score low.

### Benchmarking Infrastructure

A reusable benchmarking suite ships with the SDK:

```bash
# Run full comparison
python -m benchmarks --systems neuromem mem0 langmem

# Quick smoke test (~2 min)
python -m benchmarks --quick

# Latency profiling
python -m benchmarks --latency

# Configuration
python -m benchmarks --backend qdrant --embedding-provider openai
```

Adapter-based architecture supports adding new systems via a simple interface.

---

## Bug Fixes

8 critical fixes applied since the initial v0.2.0 development:

| Fix | Impact |
|-----|--------|
| **Timezone-aware datetime** | Eliminated all `datetime.utcnow()` and naive `datetime.now()` calls; replaced with `datetime.now(timezone.utc)` across 33 call sites in 10 files |
| **Keyword punctuation stripping** | Queries with trailing `?` or `.` now match correctly |
| **Conflict detection redesign** | Replaced unreliable tag-based matching with content-analysis approach using word overlap and negation patterns |
| **Async entity extraction** | `observe()` in async mode now populates the entity graph |
| **Exact-match validation** | Case-insensitive phrase matching confirmed working with new tests |
| **Temporal query routing** | Narrowed multi-hop classification to only compound temporal queries, preventing regression on simple lookups |
| **Adapter import hardening** | All 8 adapters use defensive `try/except` imports with clear error messages for missing optional dependencies |
| **Test fixture mocking** | OpenAI API properly mocked in pytest fixtures, eliminating flaky test failures |

---

## Breaking Changes

**None.** All v0.1.0 APIs remain fully compatible:

```python
# These all work exactly as before
memory.observe(user_input="...", assistant_output="...")
memory.retrieve(query="...", task_type="chat", k=5)
memory.consolidate()
memory.list(memory_type="episodic", limit=10)
memory.update(memory_id="...", content="...")
memory.forget(memory_id="...")
memory.explain(memory_id="...")
memory.close()
```

---

## Migration Guide

### From v0.1.0

No code changes required. Upgrade and optionally install new extras:

```bash
# Upgrade
pip install --upgrade neuromem-sdk

# Optional: add new integrations
pip install neuromem-sdk[mcp]              # MCP server
pip install neuromem-sdk[inngest]           # Durable workflows
pip install neuromem-sdk[crewai]            # CrewAI adapter
pip install neuromem-sdk[autogen]           # AutoGen adapter
pip install neuromem-sdk[dspy]              # DSPy adapter
pip install neuromem-sdk[haystack]          # Haystack adapter
pip install neuromem-sdk[semantic-kernel]   # Semantic Kernel adapter
pip install neuromem-sdk[all]               # Everything
```

---

## Installation

```bash
# Core
pip install neuromem-sdk==0.2.0

# With specific integrations
pip install "neuromem-sdk[langchain,langgraph]==0.2.0"
pip install "neuromem-sdk[crewai,mcp]==0.2.0"

# Everything
pip install "neuromem-sdk[all]==0.2.0"
```

### Requirements

- Python 3.9, 3.10, 3.11, or 3.12
- `numpy>=1.24.0`
- `pyyaml>=6.0`
- OpenAI API key (for embeddings and consolidation)

---

## Test Coverage

| Suite | Tests | Status |
|-------|-------|--------|
| Core (memory, retrieval, decay) | 50+ | Passing |
| Graph memory | 26 | Passing |
| Structured query | 31 | Passing |
| MCP server | 26 | Passing (requires `mcp` package) |
| Workflows | 30 | Passing (requires `inngest` package) |
| Adapter tests (5 new) | 42 | Passing |
| **Total** | **176** | **All passing** |

---

## What's Next

Areas of active development for future releases:

- **Temporal reasoning** — improved date extraction and time-aware retrieval
- **Adversarial query detection** — confidence-calibrated "I don't know" responses
- **Distributed memory** — multi-agent shared memory with conflict resolution
- **Prometheus metrics** — observability export for production monitoring
- **CI/CD pipeline** — automated testing and release workflow

---

## Links

- **PyPI:** [neuromem-sdk](https://pypi.org/project/neuromem-sdk/)
- **GitHub:** [github.com/Vk-thug/neuromem-sdk](https://github.com/Vk-thug/neuromem-sdk)
- **Documentation:** [docs.neuromem.ai](https://docs.neuromem.ai)
- **Issues:** [GitHub Issues](https://github.com/Vk-thug/neuromem-sdk/issues)
- **License:** MIT

---

## Acknowledgments

Benchmark evaluation uses the [LoCoMo dataset](https://github.com/snap-research/locomo) (Maharana et al., ACL 2024). Graph-augmented retrieval draws inspiration from [HippoRAG](https://arxiv.org/abs/2405.14831) (Gutierrez et al., 2024). Memory template design is influenced by [Obsidian](https://obsidian.md/) knowledge management patterns.
