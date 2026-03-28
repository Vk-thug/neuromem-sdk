# CLAUDE.md - NeuroMem SDK

## Project Identity

| Attribute | Detail |
|-----------|--------|
| **Package** | `neuromem-sdk` |
| **Version** | 0.1.0 (Alpha) |
| **Python** | 3.9+ |
| **License** | MIT |
| **Distribution** | PyPI |
| **Codebase** | ~8,300 LOC across 40 Python files |

**Purpose**: Brain-inspired, multi-layer memory system for LangChain and LangGraph agents. Enables LLM agents to remember experiences (episodic), learn stable facts (semantic), adapt to user style (procedural), and forget naturally (decay curves).

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Build | setuptools + pyproject.toml (PEP 621) |
| Core deps | `numpy>=1.24.0`, `pyyaml>=6.0` |
| Embeddings | OpenAI `text-embedding-3-large` (1536 dims) |
| Consolidation LLM | OpenAI `gpt-4o-mini` |
| Vector Storage | PostgreSQL+pgvector, Qdrant, SQLite, In-Memory |
| Framework Adapters | LangChain (LCEL Runnable), LangGraph (Checkpointer), LiteLLM |
| Testing | pytest + pytest-cov |
| Linting | ruff, black (line-length 100), mypy |
| Concurrency | `threading.Thread` (daemon workers), `ThreadPoolExecutor` (parallel retrieval) |
| Config | YAML (`neuromem.yaml`) + env var overrides |

---

## Architecture

Brain-inspired layered memory with Controller + Worker + Policy model.

```
NeuroMem (Facade)
  └── MemoryController ("prefrontal cortex")
        ├── EpisodicMemory ──┐
        ├── SemanticMemory ──┤── all use MemoryBackend (Protocol)
        ├── ProceduralMemory ┘
        ├── SessionMemory (RAM-only)
        ├── RetrievalEngine (multi-factor scoring)
        ├── Consolidator → ConsolidationEngine (OpenAI LLM)
        ├── DecayEngine (Ebbinghaus forgetting curves)
        ├── PriorityTaskScheduler (5-level queues)
        ├── IngestWorker (daemon thread)
        ├── MaintenanceWorker (daemon thread)
        └── Policies (salience, reconsolidation, conflict, optimization)

Storage Backends (MemoryBackend Protocol):
  ├── PostgresBackend (psycopg2 + pgvector)
  ├── QdrantStorage (qdrant-client)
  ├── SQLiteBackend (sqlite3)
  └── InMemoryBackend (dict)
```

### Data Flow

**Write path** (`observe()`):
```
input → validate → [async] enqueue CRITICAL task → IngestWorker
                   [sync]  get_embedding() → MemoryItem → backend.upsert()
       → session.add_turn()
       → every N turns: consolidate()
```

**Read path** (`retrieve()`):
```
query → get_embedding()
      → parallel retrieval (3 threads): semantic + procedural + episodic
      → [hybrid] HybridRetrieval.rank_results()
        [basic] RetrievalEngine.rank() → inhibition → confidence filter
      → reinforce accessed memories → return top-k
```

**Consolidation** (`consolidate()`):
```
episodic.get_all() → filter candidates by age+strength
  → OpenAI LLM: extract_facts() + summarize_conversation()
  → merge_similar_facts() → store as semantic memories
  → apply_decay() → delete forgotten episodic memories
```

---

## Key Files

### Entry Points
| File | Purpose |
|------|---------|
| `neuromem/__init__.py` | `NeuroMem` facade class, `from_config()` factory |
| `neuromem/config.py` | `NeuroMemConfig` YAML loader |
| `neuromem/constants.py` | All magic numbers and defaults (172 lines) |

### Core (`neuromem/core/`)
| File | Purpose |
|------|---------|
| `controller.py` | Central orchestrator (554 lines, largest file) |
| `retrieval.py` | Multi-factor scoring: similarity(0.45) + salience(0.20) + recency(0.15) + reinforcement(0.10) + confidence(0.10) |
| `consolidation.py` | Wrapper around `memory/consolidation.py` engine |
| `decay.py` | Ebbinghaus forgetting: `strength = e^(-decay_rate * time)` |
| `types.py` | `MemoryItem`, `MemoryType`, `ConsolidationResult` dataclasses |
| `task_scheduler.py` | 5-level priority queue with salience-aware backpressure |
| `task_types.py` | `Task`, `TaskType`, `TaskPriority` definitions |

### Workers (`neuromem/core/workers/`)
| File | Purpose |
|------|---------|
| `base.py` | `BaseWorker(threading.Thread, ABC)` — daemon thread pattern |
| `ingest_worker.py` | Background memory ingestion with retry + dead letter queue |
| `maintenance_worker.py` | Periodic consolidation and decay |

### Policies (`neuromem/core/policies/`)
| File | Purpose |
|------|---------|
| `salience.py` | Memory importance scoring |
| `reconsolidation.py` | When to re-consolidate on retrieval |
| `conflict_resolution.py` | Handle contradictory memories |
| `optimization.py` | Performance tuning decisions |

### Memory Layers (`neuromem/memory/`)
| File | Purpose |
|------|---------|
| `episodic.py` | Recent experiences (short-term, high decay) |
| `semantic.py` | Stable facts (long-term, low decay) |
| `procedural.py` | User style/preferences (pattern-based) |
| `session.py` | Current conversation (RAM-only, not persisted) |
| `consolidation.py` | `ConsolidationEngine` — LLM-based fact extraction and summarization |
| `hybrid_retrieval.py` | Multi-signal ranking (recency + importance + similarity) |

### Storage (`neuromem/storage/`)
| File | Backend | Production Ready |
|------|---------|-----------------|
| `base.py` | `MemoryBackend(Protocol)` — interface | N/A |
| `postgres.py` | PostgreSQL + pgvector | Yes |
| `qdrant.py` | Qdrant vector DB | Yes |
| `sqlite.py` | SQLite (file-based) | Dev/Testing |
| `memory.py` | In-memory dict | Dev/Testing |

### Adapters (`neuromem/adapters/`)
| File | Framework | Integration |
|------|-----------|-------------|
| `langchain.py` | LangChain | `NeuroMemRunnable` (LCEL), `add_memory()` decorator, `NeuroMemChatMessageHistory` |
| `langgraph.py` | LangGraph | Custom checkpointer |
| `litellm.py` | LiteLLM | Multi-provider completion wrapper |

### Utilities (`neuromem/utils/`)
| File | Purpose |
|------|---------|
| `embeddings.py` | OpenAI embedding calls with cache, retry, circuit breaker, mock fallback |
| `validation.py` | Input validation (UUID, content length, SQL filter whitelisting) |
| `retry.py` | `@retry_with_exponential_backoff` decorator + `CircuitBreaker` class |
| `logging.py` | Structured JSON logging with PII redaction |
| `auto_tagger.py` | LLM-based auto-tagging (intent, sentiment, entities) |
| `time.py` | Time utilities |

### Other
| File | Purpose |
|------|---------|
| `health.py` | Health/readiness/liveness probes (database, workers, queues, APIs, DLQ) |
| `user.py` | `User` and `UserManager` classes |

---

## Configuration

Config is loaded from `neuromem.yaml` via `NeuroMemConfig(path)`. Access via method calls:

```python
config.model()          # embedding model, consolidation LLM
config.storage()        # backend type and connection info
config.memory()         # decay, consolidation interval, retention
config.consolidation()  # fact extraction, summarization, forgetting
config.retrieval()      # hybrid scoring weights
config.tagging()        # auto-tag settings
config.embeddings()     # dimension reduction, quantization, dedup
config.get("key.path")  # dot-separated key access
```

**Critical settings**:
- `storage.database.type` — `memory` | `postgres` | `sqlite`
- `storage.vector_store.type` — `memory` | `qdrant` | (pgvector via postgres)
- `async.enabled` — `true` enables background workers; `false` for sync mode
- `retrieval.hybrid_enabled` — multi-factor vs basic similarity ranking
- `memory.decay_enabled` — toggles Ebbinghaus forgetting curves

**Env var overrides**: `OPENAI_API_KEY`, `NEUROMEM_CACHE_EMBEDDINGS`, `NEUROMEM_LOG_LEVEL`

---

## Design Patterns

| Pattern | Location | Details |
|---------|----------|---------|
| Protocol (structural typing) | `storage/base.py` | `MemoryBackend(Protocol)` — duck-typed storage |
| Facade | `__init__.py::NeuroMem` | Single API hiding controller/worker/policy complexity |
| Strategy | `core/policies/` | Pluggable salience, reconsolidation, conflict, optimization |
| Worker/Queue | `core/workers/` + `task_scheduler.py` | Daemon threads with 5-level priority queues |
| Circuit Breaker | `utils/retry.py` | 3-state (CLOSED/OPEN/HALF_OPEN) for OpenAI API |
| Retry with Backoff | `utils/retry.py` | Exponential backoff + jitter decorator |
| Factory Method | `NeuroMem.from_config()` | Constructs full object graph from YAML |
| Adapter | `adapters/` | LangChain LCEL, LangGraph Checkpointer, LiteLLM |
| Composite Scoring | `core/retrieval.py` | Weighted multi-factor: similarity + salience + recency + reinforcement + confidence |
| Lateral Inhibition | `core/retrieval.py` | Jaccard similarity to prevent near-duplicate results |
| Ebbinghaus Decay | `core/decay.py` | `strength = e^(-adjusted_decay * days)`, adjusted by reinforcement and salience |

---

## Development Commands

```bash
# Tests
pytest                                    # all tests
pytest --cov=neuromem                      # with coverage
pytest tests/test_core.py::TestObserve     # specific class

# Code quality
black neuromem/ --line-length 100         # format
ruff check neuromem/                       # lint
mypy neuromem/                             # type check

# All quality checks
black neuromem/ --line-length 100 && ruff check neuromem/ && mypy neuromem/

# Config validation
python test_setup.py

# Build & publish
python -m build
python -m twine upload --repository testpypi dist/*  # test
python -m twine upload dist/*                         # production

# Examples
python examples/demo_agent.py --mode demo
python examples/langchain_simple.py
python examples/langgraph_simple.py
```

---

## Code Style

- Python 3.9+ with type annotations on all signatures
- Black formatter, line-length 100, target py39
- Ruff linter, line-length 100
- Mypy with `disallow_untyped_defs = false` (relaxed)
- NumPy/Google-style docstrings
- Constants in `constants.py`, never inline magic numbers
- Structured logging via `neuromem.utils.logging.get_logger(__name__)`
- Input validation at system boundaries via `utils/validation.py`
- Parameterized SQL queries (never string interpolation)

---

## Extending the SDK

### New Storage Backend
1. Create `neuromem/storage/my_backend.py`
2. Implement `MemoryBackend` protocol: `upsert`, `query`, `get_by_id`, `update`, `delete`, `list_all`
3. Wire in `NeuroMem.from_config()` factory
4. Reference: `storage/postgres.py`

### New Policy
1. Create `neuromem/core/policies/my_policy.py`
2. Integrate with `MemoryController`
3. Add config section to `neuromem.yaml`

### New Framework Adapter
1. Create `neuromem/adapters/my_framework.py`
2. Follow patterns in `adapters/langchain.py` (LCEL Runnable) or `adapters/langgraph.py` (Checkpointer)
3. Add optional dependency in `pyproject.toml`

### New Memory Type
1. Add to `MemoryType` enum in `core/types.py`
2. Create memory layer in `neuromem/memory/`
3. Update `MemoryController` to coordinate
4. Update storage backend schemas

---

## Known Issues & Technical Debt

| Issue | Location | Impact |
|-------|----------|--------|
| `MemoryItem` is mutable dataclass | `core/types.py` | `DecayEngine.reinforce()` mutates in place |
| Bare `except:` clauses | `adapters/langchain.py:322` | Silently swallows errors |
| `print()` instead of logger | `memory/consolidation.py:116,183` | Inconsistent error reporting |
| Module-level mutable cache | `utils/embeddings.py` | `_embedding_cache` dict not thread-safe |
| `np.random.seed()` global state | `utils/embeddings.py:50` | Not thread-safe for mock embeddings |
| Hardcoded `VECTOR(1536)` | `storage/postgres.py:62` | Mismatch if model produces 3072 dims |
| `datetime.utcnow()` deprecated | Multiple files | Should use `datetime.now(timezone.utc)` |
| Thin test coverage | `tests/` | Only 1 test file (~160 lines), no backend/worker/adapter tests |
| No context manager | `__init__.py::NeuroMem` | Has `close()` and `__del__` but no `__enter__`/`__exit__` |
| Direct OpenAI import | `memory/consolidation.py` | Bypasses LiteLLM adapter, creates provider lock-in |
| No DB migrations | `storage/postgres.py` | Schema created inline, no migration framework |
| No CI/CD | Project root | No GitHub Actions or automated pipeline |

---

## Dependencies

### Core (always installed)
- `numpy>=1.24.0` — vector operations
- `pyyaml>=6.0` — config parsing

### Optional (extras)
```bash
pip install neuromem-sdk[postgres]    # psycopg2-binary
pip install neuromem-sdk[qdrant]      # qdrant-client
pip install neuromem-sdk[openai]      # openai + langchain-openai
pip install neuromem-sdk[anthropic]   # langchain-anthropic
pip install neuromem-sdk[langchain]   # langchain
pip install neuromem-sdk[langgraph]   # langgraph
pip install neuromem-sdk[all]         # everything
pip install neuromem-sdk[dev]         # pytest, black, ruff, mypy
```

---

## Quick Start

```python
from neuromem import NeuroMem

memory = NeuroMem.from_config("neuromem.yaml", user_id="uuid-here")

# Store interaction
memory.observe(user_input="I prefer Python", assistant_output="Noted!")

# Retrieve relevant memories
context = memory.retrieve(query="What languages?", task_type="chat", k=5)

# Consolidate (episodic -> semantic)
memory.consolidate()

# List, update, forget
memories = memory.list(memory_type="episodic", limit=10)
memory.update(memory_id="...", content="Updated content")
memory.forget(memory_id="...")

# Cleanup
memory.close()
```

### LangChain Integration
```python
from neuromem import NeuroMem
from neuromem.adapters.langchain import add_memory

memory = NeuroMem.from_config("neuromem.yaml", user_id="uuid")
chain_with_memory = add_memory(chain, memory, k=5)
response = chain_with_memory.invoke({"input": "Hello"})
```

### LangGraph Integration
```python
from neuromem import NeuroMem
from neuromem.adapters.langgraph import with_memory

memory = NeuroMem.from_config("neuromem.yaml", user_id="uuid")
app = with_memory(graph.compile(), memory)
```

---

## Versioning

Semantic versioning: `MAJOR.MINOR.PATCH`
- Current: **0.1.0** (Alpha) — breaking changes expected
- Update version in `pyproject.toml` `[project] version`

---

**Last Updated**: 2026-03-25
**SDK Version**: 0.1.0 (Alpha)
