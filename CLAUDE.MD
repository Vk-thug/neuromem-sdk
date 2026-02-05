# CLAUDE.MD - NeuroMem SDK Developer Guide

> **For AI Assistants**: This document provides comprehensive guidance for understanding, navigating, and contributing to the NeuroMem SDK project.

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture Overview](#architecture-overview)
- [Key Files & Module Guide](#key-files--module-guide)
- [Configuration System](#configuration-system)
- [Development Workflow & Guidelines](#development-workflow--guidelines)
- [Integration Examples](#integration-examples)
- [Extension Points](#extension-points)
- [Project Dependencies](#project-dependencies)
- [Key Design Patterns](#key-design-patterns)
- [Common Gotchas & Tips](#common-gotchas--tips)
- [Verification & Testing](#verification--testing)
- [Package Deployment & Distribution](#package-deployment--distribution)

---

## Project Overview

**NeuroMem SDK** is a brain-inspired, multi-layer memory system designed for LangChain and LangGraph agents.

### Key Information
- **Package Name**: `neuromem-sdk`
- **Version**: 0.1.0 (Alpha)
- **Language**: Python 3.9+
- **License**: MIT
- **Distribution**: PyPI Package

### Purpose
NeuroMem enables LLM agents to:
- **Remember experiences** through episodic memory
- **Learn stable facts** via semantic memory consolidation
- **Adapt to user thinking styles** with procedural memory
- **Manage memory decay** for realistic forgetting
- **Retrieve contextually** using hybrid search (similarity + recency + salience)

### Brain-Inspired Design
The system mimics human memory formation:
1. **Short-term** → Episodic memories (recent experiences)
2. **Consolidation** → Episodic gradually becomes semantic (like sleep)
3. **Long-term** → Semantic memories (stable facts and knowledge)
4. **Style Learning** → Procedural memories (user preferences and patterns)

### Target Users
LangChain and LangGraph developers building stateful, context-aware AI agents that need:
- Multi-turn conversation memory
- Long-term user preferences
- Knowledge accumulation over time
- Natural forgetting and memory management

### Current Status
**Alpha Release** - Core functionality implemented, API may change before 1.0.0

---

## Architecture Overview

### Memory System Architecture

NeuroMem implements a **four-layer memory system**:

#### 1. Episodic Memory
- **File**: `neuromem/memory/episodic.py`
- **Purpose**: Stores recent experiences and events with timestamps
- **Characteristics**:
  - Time-bound (short-term storage)
  - Rich contextual details
  - Subject to consolidation into semantic memory
  - Natural decay over time

#### 2. Semantic Memory
- **File**: `neuromem/memory/semantic.py`
- **Purpose**: Long-term storage of stable facts and knowledge
- **Characteristics**:
  - Abstracted from specific episodes
  - Higher confidence and salience
  - Slower decay rate
  - Created through consolidation process

#### 3. Procedural Memory
- **File**: `neuromem/memory/procedural.py`
- **Purpose**: Captures user's thinking style, preferences, and interaction patterns
- **Characteristics**:
  - Infers communication preferences
  - Learns task-solving approaches
  - Adapts response style over time
  - Pattern-based learning

#### 4. Session Memory
- **File**: `neuromem/memory/session.py`
- **Purpose**: Maintains current conversation context
- **Characteristics**:
  - Temporary (session-scoped)
  - Not persisted to storage
  - Fast access for immediate context
  - Cleared between sessions

### Consolidation Flow

```
Episodic Memory (recent events)
        ↓
    [Sleep-like Process]
        ↓
Semantic Memory (stable facts)
```

The consolidation process:
1. Identifies important episodic memories
2. Abstracts patterns and facts
3. Creates semantic memories with higher confidence
4. Applies slower decay rates to semantic memories

---

### Core Components

#### MemoryController
- **File**: `neuromem/core/controller.py`
- **Role**: Central orchestrator ("prefrontal cortex" of the system)
- **Responsibilities**:
  - Coordinates all memory operations
  - Manages memory lifecycle
  - Routes retrieval requests
  - Triggers consolidation
  - Coordinates workers

#### RetrievalEngine
- **File**: `neuromem/core/retrieval.py`
- **Role**: Hybrid memory search and ranking
- **Features**:
  - Similarity search (vector embeddings)
  - Recency weighting
  - Salience scoring
  - User-specific filtering
  - Session-aware context

#### Consolidator
- **File**: `neuromem/core/consolidation.py`
- **Role**: Transforms episodic memories into semantic memories
- **Process**:
  - Identifies consolidation candidates
  - Extracts patterns and facts
  - Creates abstracted semantic memories
  - Adjusts confidence and decay rates

#### DecayEngine
- **File**: `neuromem/core/decay.py`
- **Role**: Simulates natural memory forgetting
- **Features**:
  - Time-based decay curves
  - Salience-weighted decay
  - Reinforcement from retrieval
  - Configurable decay parameters

#### PriorityTaskScheduler
- **File**: `neuromem/core/task_scheduler.py`
- **Role**: Manages async task execution with priorities
- **Features**:
  - Priority queuing
  - Concurrent task execution
  - Resource management
  - Task lifecycle tracking

---

### Worker System

Background async processing architecture for expensive operations.

#### BaseWorker
- **File**: `neuromem/core/workers/base.py`
- **Role**: Abstract base class for all workers
- **Interface**:
  - `start()` - Initialize and start worker
  - `stop()` - Graceful shutdown
  - `process()` - Main work loop
  - `health_check()` - Worker status

#### IngestWorker
- **File**: `neuromem/core/workers/ingest_worker.py`
- **Role**: Handles memory ingestion in background
- **Operations**:
  - Batch embedding generation
  - Memory validation
  - Storage backend writes
  - Error handling and retries

#### MaintenanceWorker
- **File**: `neuromem/core/workers/maintenance_worker.py`
- **Role**: Periodic consolidation and decay
- **Operations**:
  - Scheduled consolidation runs
  - Memory decay application
  - Cleanup of old memories
  - Performance optimization

#### Worker Lifecycle
1. **Start**: Initialize worker thread/task
2. **Run**: Continuous processing loop
3. **Health Check**: Monitor worker status
4. **Stop**: Graceful shutdown with cleanup

---

### Policy Framework

Pluggable decision-making policies for customizable behavior.

#### ReconsolidationPolicy
- **File**: `neuromem/core/policies/reconsolidation.py`
- **Purpose**: Decides when memories should be reconsolidated
- **Factors**: Access patterns, confidence changes, conflicting information

#### SaliencePolicy
- **File**: `neuromem/core/policies/salience.py`
- **Purpose**: Determines memory importance
- **Factors**: User signals, context relevance, reinforcement

#### OptimizationPolicy
- **File**: `neuromem/core/policies/optimization.py`
- **Purpose**: Performance and resource tuning
- **Factors**: Memory count, query patterns, storage costs

#### ConflictResolutionPolicy
- **File**: `neuromem/core/policies/conflict_resolution.py`
- **Purpose**: Handles contradictory memories
- **Strategies**: Confidence-based, recency-based, manual resolution

---

## Key Files & Module Guide

### Entry Points

#### `neuromem/__init__.py`
Main SDK entry point. Exports:
- `NeuroMem` - Primary API class
- `MemoryController` - Core controller
- `MemoryType` - Memory type enum
- `MemoryItem` - Memory data structure
- All memory layer classes
- Storage backend interface

**Example Usage**:
```python
from neuromem import NeuroMem

memory = NeuroMem.from_config("neuromem.yaml", user_id="user_123")
context = memory.retrieve(query="Previous design patterns", task_type="coding")
memory.observe(user_input="Use factory pattern", assistant_output="Will do!")
```

#### `neuromem/config.py`
Configuration management with `NeuroMemConfig` class.
- Loads from YAML files
- Validates configuration
- Provides defaults
- Supports environment variable overrides

#### `neuromem/user.py`
User management with `User` and `UserManager` classes.
- Multi-user support
- User lifecycle management
- User-specific memory isolation

---

### Core System (`neuromem/core/`)

| File | Purpose |
|------|---------|
| `controller.py` | Central memory orchestrator, coordinates all operations |
| `retrieval.py` | Hybrid retrieval engine (similarity + recency + salience) |
| `consolidation.py` | Episodic → semantic memory transformation |
| `decay.py` | Memory forgetting simulation with decay curves |
| `task_scheduler.py` | Priority-based async task scheduling |
| `task_types.py` | Task and TaskType definitions for workers |
| `types.py` | Core data models: `MemoryItem`, `MemoryType`, `EmbeddingMetadata` |

**Critical Interfaces**:
- `MemoryItem` - Primary data structure for all memories
- `MemoryType` - Enum: EPISODIC, SEMANTIC, PROCEDURAL, AFFECTIVE
- `Task` - Worker task definition

**Dependencies**:
- Controller → Retrieval, Consolidation, Decay, TaskScheduler
- Retrieval → Types (MemoryItem)
- Consolidation → Types, Storage backends
- Workers → Task types, TaskScheduler

---

### Core Observability (`neuromem/core/observability/`)

| File | Purpose |
|------|---------|
| `metrics.py` | Performance metrics tracking (latency, throughput, cache hits) |
| `tracing.py` | Distributed tracing support for debugging |

---

### Core Policies (`neuromem/core/policies/`)

| File | Purpose |
|------|---------|
| `reconsolidation.py` | When to reconsolidate memories |
| `salience.py` | How to score memory importance |
| `optimization.py` | Performance tuning decisions |
| `conflict_resolution.py` | Handle contradictory memories |

---

### Core Workers (`neuromem/core/workers/`)

| File | Purpose |
|------|---------|
| `base.py` | BaseWorker abstract class - worker interface |
| `ingest_worker.py` | Background memory ingestion |
| `maintenance_worker.py` | Consolidation and decay scheduling |

---

### Memory Layers (`neuromem/memory/`)

| File | Purpose | Memory Type |
|------|---------|-------------|
| `episodic.py` | Recent experiences with timestamps | Short-term |
| `semantic.py` | Stable facts and knowledge | Long-term |
| `procedural.py` | User thinking style and preferences | Pattern-based |
| `session.py` | Current conversation context | Temporary |
| `consolidation.py` | Logic for episodic → semantic transformation | Process |
| `hybrid_retrieval.py` | Multi-signal retrieval strategies | Utility |

---

### Storage Backends (`neuromem/storage/`)

All backends implement the `MemoryBackend` interface from `base.py`.

| File | Purpose | Production Ready |
|------|---------|------------------|
| `base.py` | **MemoryBackend interface** - Critical for new backends | N/A |
| `postgres.py` | PostgreSQL with pgvector for vector search | Yes |
| `qdrant.py` | Qdrant vector database integration | Yes |
| `sqlite.py` | SQLite for lightweight deployments | Dev/Testing |
| `memory.py` | In-memory backend (no persistence) | Dev/Testing |

**MemoryBackend Interface** (from `base.py`):
```python
class MemoryBackend:
    def store(self, memory: MemoryItem) -> None
    def retrieve(self, query_embedding: List[float], filters: dict) -> List[MemoryItem]
    def update(self, memory_id: str, updates: dict) -> None
    def delete(self, memory_id: str) -> None
    def list_users(self) -> List[str]
    def get_memory(self, memory_id: str) -> Optional[MemoryItem]
    def close(self) -> None
```

---

### Framework Adapters (`neuromem/adapters/`)

| File | Framework | Integration Pattern |
|------|-----------|---------------------|
| `langchain.py` | LangChain | Memory wrapper around chains |
| `langgraph.py` | LangGraph | Custom checkpointer implementation |
| `litellm.py` | LiteLLM | Multi-provider LLM support (OpenAI, Anthropic, etc.) |

---

### Utilities (`neuromem/utils/`)

| File | Purpose |
|------|---------|
| `embeddings.py` | Embedding generation functions (OpenAI, custom models) |
| `auto_tagger.py` | Automatic tagging logic for memories |
| `time.py` | Time utilities for memory operations |

---

## Configuration System

### Configuration File Structure

The `neuromem.yaml` file has the following sections:

```yaml
model:
  embedding_model: "text-embedding-3-large"
  embedding_dimension: 3072

storage:
  backend: "postgres"  # or "qdrant", "sqlite", "memory"
  postgres:
    connection_string: "postgresql://user:pass@localhost/neuromem"

memory:
  episodic:
    decay_rate: 0.1
    max_age_days: 30
  semantic:
    decay_rate: 0.01
    consolidation_threshold: 3

consolidation:
  enabled: true
  interval_seconds: 3600
  batch_size: 100

async:
  workers:
    enabled: true
    ingest:
      enabled: true
      batch_size: 10
    maintenance:
      enabled: true
      interval_seconds: 3600

proactive:
  enabled: true
  suggestion_threshold: 0.7
```

### Loading Configuration

```python
from neuromem.config import NeuroMemConfig

# Load from YAML file
config = NeuroMemConfig.from_yaml("neuromem.yaml")

# Access configuration
storage_backend = config.storage.backend
decay_rate = config.memory.episodic.decay_rate
```

### Critical Settings

| Setting | Purpose | Impact |
|---------|---------|--------|
| `storage.backend` | Which storage backend to use | Determines persistence, vector search capabilities |
| `model.embedding_model` | Embedding model for vectors | Affects retrieval quality and cost |
| `consolidation.enabled` | Enable episodic → semantic consolidation | Memory organization and long-term learning |
| `memory.*.decay_rate` | How quickly memories fade | Forgetting behavior |
| `async.workers.enabled` | Enable background workers | Performance and resource usage |

### Environment Variable Overrides

Environment variables can override YAML settings:
```bash
export NEUROMEM_STORAGE_BACKEND="postgres"
export NEUROMEM_POSTGRES_CONNECTION_STRING="postgresql://..."
export OPENAI_API_KEY="sk-..."
```

---

## Development Workflow & Guidelines

### Code Style

- **Python Version**: 3.9+ with type hints
- **Formatter**: Black (line length: 100)
- **Linter**: Ruff
- **Type Checker**: Mypy
- **Docstrings**: NumPy/Google style

**Format Code**:
```bash
black neuromem/ --line-length 100
```

**Lint Code**:
```bash
ruff check neuromem/
```

**Type Check**:
```bash
mypy neuromem/
```

---

### Common Development Tasks

#### Task 1: Adding a New Storage Backend

**Steps**:
1. Create new file in `neuromem/storage/` (e.g., `pinecone.py`)
2. Import and inherit from `MemoryBackend`:
   ```python
   from neuromem.storage.base import MemoryBackend
   from neuromem.core.types import MemoryItem

   class PineconeBackend(MemoryBackend):
       def __init__(self, config: dict):
           # Initialize Pinecone client
           pass
   ```
3. Implement all required methods:
   - `store(memory: MemoryItem) -> None`
   - `retrieve(query_embedding: List[float], filters: dict) -> List[MemoryItem]`
   - `update(memory_id: str, updates: dict) -> None`
   - `delete(memory_id: str) -> None`
   - `list_users() -> List[str]`
   - `get_memory(memory_id: str) -> Optional[MemoryItem]`
   - `close() -> None`
4. Add configuration support in `neuromem/config.py`:
   ```python
   class StorageConfig:
       backend: str
       pinecone: Optional[PineconeConfig] = None
   ```
5. Register backend in controller or factory
6. Add example to `examples/` directory
7. Update documentation

**Reference Implementation**: See `neuromem/storage/postgres.py` for a complete example.

---

#### Task 2: Creating a Custom Policy

**Steps**:
1. Create file in `neuromem/core/policies/` (e.g., `my_policy.py`)
2. Define policy interface:
   ```python
   class MyCustomPolicy:
       def __init__(self, config: dict):
           self.threshold = config.get("threshold", 0.5)

       def should_apply(self, memory: MemoryItem) -> bool:
           # Policy logic here
           return memory.salience > self.threshold
   ```
3. Integrate with MemoryController or relevant component:
   ```python
   # In controller.py
   from neuromem.core.policies.my_policy import MyCustomPolicy

   class MemoryController:
       def __init__(self, ...):
           self.my_policy = MyCustomPolicy(config.policy_config)
   ```
4. Add configuration to `neuromem.yaml`:
   ```yaml
   policies:
     my_policy:
       threshold: 0.7
   ```
5. Document policy behavior in docstrings
6. Add tests for policy logic

---

#### Task 3: Extending Memory Types

**Steps**:
1. Modify existing memory class in `neuromem/memory/` (e.g., `episodic.py`)
2. Update data models in `neuromem/core/types.py`:
   ```python
   class MemoryType(str, Enum):
       EPISODIC = "episodic"
       SEMANTIC = "semantic"
       PROCEDURAL = "procedural"
       AFFECTIVE = "affective"
       MY_NEW_TYPE = "my_new_type"  # Add new type
   ```
3. Update `MemoryItem` dataclass if new fields needed:
   ```python
   @dataclass
   class MemoryItem:
       # Existing fields...
       my_new_field: Optional[str] = None  # Add new field
   ```
4. Adjust consolidation logic in `neuromem/memory/consolidation.py` if needed
5. Update `RetrievalEngine` in `neuromem/core/retrieval.py` for new type filtering
6. Update storage backend schemas (e.g., PostgreSQL tables)
7. Add tests for new memory type

---

#### Task 4: Adding Framework Adapter

**Steps**:
1. Create adapter file in `neuromem/adapters/` (e.g., `my_framework.py`)
2. Study existing adapters (`langchain.py`, `langgraph.py`) for patterns
3. Implement framework-specific interface:
   ```python
   from neuromem import NeuroMem

   class MyFrameworkAdapter:
       def __init__(self, neuromem: NeuroMem):
           self.neuromem = neuromem

       def framework_specific_method(self):
           # Adapt NeuroMem to framework
           pass
   ```
4. Create minimal example in `examples/my_framework_simple.py`:
   ```python
   from neuromem import NeuroMem
   from neuromem.adapters.my_framework import MyFrameworkAdapter

   memory = NeuroMem.from_config("neuromem.yaml", user_id="user_123")
   adapter = MyFrameworkAdapter(memory)
   ```
5. Document integration in adapter docstring
6. Add to `pyproject.toml` optional dependencies if needed:
   ```toml
   [project.optional-dependencies]
   myframework = ["myframework>=1.0.0"]
   ```

**Reference**: See `neuromem/adapters/langchain.py:8-45` for LangChain integration pattern.

---

#### Task 5: Modifying Worker Behavior

**Steps**:
1. Edit worker in `neuromem/core/workers/` (e.g., `ingest_worker.py`)
2. Maintain `BaseWorker` interface contract:
   ```python
   from neuromem.core.workers.base import BaseWorker

   class IngestWorker(BaseWorker):
       async def process(self):
           # Your modified logic here
           pass
   ```
3. Update task types in `neuromem/core/task_types.py` if new task types needed:
   ```python
   class TaskType(str, Enum):
       INGEST = "ingest"
       CONSOLIDATE = "consolidate"
       MY_NEW_TASK = "my_new_task"
   ```
4. Test worker lifecycle:
   - Start worker
   - Process tasks
   - Stop worker gracefully
5. Update async configuration in `neuromem/config.py`:
   ```python
   class AsyncConfig:
       workers: WorkersConfig
       my_worker_setting: int = 100
   ```

---

### Testing Patterns

- **Test Location**: Tests mirror source structure in `tests/` directory
- **Test Framework**: pytest with fixtures
- **Mocking**: Mock external dependencies (OpenAI API, storage backends)
- **Configuration Testing**: Use `test_setup.py` for config validation

**Run Tests**:
```bash
# All tests
pytest

# With coverage
pytest --cov=neuromem

# Specific module
pytest tests/test_memory.py

# Specific test
pytest tests/test_memory.py::test_episodic_store
```

---

### Dependency Management

#### Core Dependencies
Located in `requirements.txt`:
- `numpy>=1.24.0` - Numerical operations
- `pyyaml>=6.0` - Configuration parsing

#### Optional Dependencies
Defined in `pyproject.toml` under `[project.optional-dependencies]`:
- `postgres` - PostgreSQL support (psycopg2-binary)
- `qdrant` - Qdrant vector store (qdrant-client)
- `openai` - OpenAI embeddings (openai)
- `langchain` - LangChain integration (langchain)
- `langgraph` - LangGraph integration (langgraph)
- `all` - All optional dependencies
- `dev` - Development tools (pytest, black, ruff, mypy)

**Adding Dependencies**:
1. Core dependency → Add to `dependencies` in `pyproject.toml`
2. Optional dependency → Add to appropriate extra in `optional-dependencies`
3. Keep core minimal to avoid bloat

---

## Integration Examples

### LangChain Integration

**File**: `neuromem/adapters/langchain.py`

**Pattern**: Memory wrapper around LangChain chains

**Example**: `examples/langchain_simple.py`

```python
from neuromem import NeuroMem
from neuromem.adapters.langchain import LangChainMemoryAdapter
from langchain.chains import ConversationChain

# Initialize NeuroMem
memory = NeuroMem.from_config("neuromem.yaml", user_id="user_123")

# Wrap with LangChain adapter
lc_memory = LangChainMemoryAdapter(memory)

# Use in chain
chain = ConversationChain(memory=lc_memory)
response = chain.run("What's my name?")
```

**Key Classes**: `LangChainMemoryAdapter` - Implements LangChain's `BaseMemory` interface

---

### LangGraph Integration

**File**: `neuromem/adapters/langgraph.py`

**Pattern**: Custom checkpointer implementation

**Example**: `examples/langgraph_simple.py`

```python
from neuromem import NeuroMem
from neuromem.adapters.langgraph import LangGraphCheckpointer
from langgraph.graph import StateGraph

# Initialize NeuroMem
memory = NeuroMem.from_config("neuromem.yaml", user_id="user_123")

# Create LangGraph checkpointer
checkpointer = LangGraphCheckpointer(memory)

# Use in graph
graph = StateGraph(checkpointer=checkpointer)
```

**Key Classes**: `LangGraphCheckpointer` - Implements LangGraph's checkpointer interface

---

### LiteLLM Integration

**File**: `neuromem/adapters/litellm.py`

**Pattern**: Multi-provider LLM support (OpenAI, Anthropic, etc.)

**Example**: `examples/litellm_simple.py`

```python
from neuromem import NeuroMem
from neuromem.adapters.litellm import LiteLLMAdapter

# Works with any LiteLLM-supported provider
memory = NeuroMem.from_config("neuromem.yaml", user_id="user_123")
adapter = LiteLLMAdapter(memory, model="claude-3-opus")
```

---

### Full Agent Example

**File**: `examples/demo_agent.py`

**Features**:
- All memory layers (episodic, semantic, procedural, session)
- Consolidation demonstration
- Interactive and demo modes
- CLI interface

**Run**:
```bash
# Interactive mode
python examples/demo_agent.py --mode interactive

# Demo mode (automated)
python examples/demo_agent.py --mode demo
```

---

## Extension Points

Priority areas where the SDK is designed for customization:

### 1. Storage Backends (`neuromem/storage/base.py`)

**Why Extend**: Add support for new vector stores or databases

**Interface**: `MemoryBackend` abstract class with well-defined methods

**Examples to Add**:
- Pinecone vector store
- Weaviate database
- Chroma vector database
- Redis with vector search
- Custom enterprise databases

**Effort**: Medium - Well-defined interface, clear examples

---

### 2. Policies (`neuromem/core/policies/`)

**Why Extend**: Customize decision-making logic

**Use Cases**:
- Domain-specific salience scoring
- Custom consolidation triggers
- Industry-specific optimization rules
- Specialized conflict resolution

**Effort**: Low - Simple functions/classes, flexible integration

---

### 3. Memory Types (`neuromem/memory/`)

**Why Extend**: Add new memory layers or extend existing ones

**Examples**:
- Affective memory (emotions, sentiment)
- Spatial memory (locations, environments)
- Social memory (relationships, interactions)
- Skill memory (learned procedures)

**Effort**: High - Requires changes across consolidation, retrieval, storage

---

### 4. Framework Adapters (`neuromem/adapters/`)

**Why Extend**: Support new agent frameworks

**Examples**:
- AutoGen adapter
- CrewAI adapter
- Custom enterprise frameworks
- Hugging Face Transformers agents

**Effort**: Medium - Pattern established, framework-specific nuances

---

### 5. Observability (`neuromem/core/observability/`)

**Why Extend**: Add monitoring and debugging

**Use Cases**:
- Custom metrics (domain-specific KPIs)
- Integration with Datadog, New Relic, etc.
- Performance profiling
- Memory usage tracking

**Effort**: Low - Add alongside existing metrics/tracing

---

## Project Dependencies

### Core Framework Stack

| Package | Purpose | Version |
|---------|---------|---------|
| LangChain | Agent framework | >=0.1.0 (optional) |
| LangGraph | Stateful agent graphs | >=0.0.1 (optional) |
| LiteLLM | Multi-provider LLM support | Latest (optional) |

### Storage & Vectors

| Package | Purpose | Version |
|---------|---------|---------|
| psycopg2-binary | PostgreSQL driver | >=2.9.0 (optional) |
| pgvector | PostgreSQL vector extension | - (install separately) |
| qdrant-client | Qdrant vector store | >=1.7.0 (optional) |
| SQLite | Embedded database | Built-in (Python stdlib) |

### Utilities

| Package | Purpose | Version |
|---------|---------|---------|
| numpy | Numerical operations | >=1.24.0 (required) |
| pyyaml | Configuration parsing | >=6.0 (required) |
| openai | OpenAI API (embeddings) | >=1.0.0 (optional) |

### Development Tools

| Package | Purpose | Version |
|---------|---------|---------|
| pytest | Testing framework | >=7.0.0 (dev) |
| pytest-cov | Coverage reporting | >=4.0.0 (dev) |
| black | Code formatting | >=23.0.0 (dev) |
| ruff | Linting | >=0.1.0 (dev) |
| mypy | Type checking | >=1.0.0 (dev) |

---

## Key Design Patterns

### 1. Brain-Inspired Architecture

**Pattern**: Mimics human memory formation and consolidation

**Implementation**:
- **Episodic → Semantic** transformation (like sleep consolidation)
- **Decay curves** for realistic forgetting
- **Reconsolidation** when memories are retrieved
- **Salience-based** importance scoring

**Benefits**:
- Natural memory behavior
- Automatic knowledge extraction
- Realistic forgetting patterns
- Context-aware retrieval

---

### 2. Async Worker Model

**Pattern**: Background processing for expensive operations

**Implementation**:
- `BaseWorker` abstract class
- Priority-based task scheduling
- Non-blocking memory operations
- Graceful shutdown handling

**Benefits**:
- Non-blocking API calls
- Resource efficiency
- Scalable processing
- Clean lifecycle management

**Components**:
- `IngestWorker` - Async memory storage
- `MaintenanceWorker` - Periodic consolidation/decay
- `PriorityTaskScheduler` - Task management

---

### 3. Pluggable Storage

**Pattern**: Storage backend abstraction

**Implementation**:
- `MemoryBackend` interface
- Switch backends via configuration
- Consistent API across backends

**Benefits**:
- Easy backend migration
- Testing flexibility (in-memory)
- Production scaling (PostgreSQL, Qdrant)
- Custom storage solutions

---

### 4. Hybrid Retrieval

**Pattern**: Multi-signal memory search

**Implementation**:
- **Similarity** - Vector embedding search
- **Recency** - Time-based weighting
- **Salience** - Importance scoring
- **Context** - User/session filtering

**Benefits**:
- More relevant results
- Context-aware retrieval
- Balances multiple factors
- Customizable weighting

---

### 5. Configuration-Driven

**Pattern**: YAML-based configuration with defaults

**Implementation**:
- `neuromem.yaml` - Central configuration
- `NeuroMemConfig` - Type-safe config class
- Environment variable overrides
- Runtime reconfiguration

**Benefits**:
- Easy deployment
- No code changes for config
- Clear documentation
- Version control friendly

---

## Common Gotchas & Tips

### Async Workers

**Gotcha**: Forgetting to stop workers can cause resource leaks

**Fix**: Always call `controller.shutdown()` or use context managers:
```python
memory = NeuroMem.from_config("neuromem.yaml", user_id="user_123")
try:
    # Use memory
    pass
finally:
    memory.controller.shutdown()
```

**Tip**: Worker health checks are important for production monitoring.

---

### Embeddings

**Gotcha**: Embedding dimension mismatch causes retrieval failures

**Fix**: Ensure all memories use the same embedding model and dimension:
```yaml
model:
  embedding_model: "text-embedding-3-large"
  embedding_dimension: 3072  # Must match across all memories
```

**Tip**: Cache embeddings to improve performance and reduce API costs.

---

### Storage Backends

**Gotcha**: PostgreSQL requires pgvector extension installation

**Fix**: Install pgvector before using PostgreSQL backend:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

**Gotcha**: Qdrant requires running Qdrant server

**Fix**: Start Qdrant before using the backend:
```bash
docker run -p 6333:6333 qdrant/qdrant
```

**Gotcha**: In-memory backend loses data on restart

**Fix**: Use persistent backends (PostgreSQL, Qdrant, SQLite) for production.

---

### Memory Consolidation

**Gotcha**: Too frequent consolidation increases costs

**Fix**: Tune consolidation interval based on use case:
```yaml
consolidation:
  interval_seconds: 3600  # Run every hour
  batch_size: 100         # Process 100 memories per run
```

**Tip**: Disable consolidation during testing to reduce complexity:
```yaml
consolidation:
  enabled: false
```

---

### Configuration

**Gotcha**: Invalid configuration causes runtime errors

**Fix**: Always validate configuration before deploying:
```bash
python test_setup.py
```

**Tip**: Use environment variables for sensitive data:
```bash
export OPENAI_API_KEY="sk-..."
export NEUROMEM_POSTGRES_CONNECTION_STRING="postgresql://..."
```

---

## Verification & Testing

### 1. Unit Tests

**Run All Tests**:
```bash
pytest
```

**With Coverage**:
```bash
pytest --cov=neuromem
```

**Specific Module**:
```bash
pytest tests/test_memory.py
```

**Specific Test**:
```bash
pytest tests/test_memory.py::test_episodic_store
```

---

### 2. Integration Tests

**Full Test Suite**:
```bash
./test_sdk.sh
```

**With Real Backends** (requires setup):
```bash
# PostgreSQL
export NEUROMEM_POSTGRES_CONNECTION_STRING="postgresql://localhost/test"
pytest tests/integration/test_postgres.py

# Qdrant
export NEUROMEM_QDRANT_URL="http://localhost:6333"
pytest tests/integration/test_qdrant.py
```

**Example Tests**:
```bash
cd examples
python demo_agent.py --mode demo
```

---

### 3. Configuration Validation

**Validate Setup**:
```bash
python test_setup.py
```

This checks:
- YAML configuration validity
- Dependencies installed
- Storage backend connectivity
- API keys present

---

### 4. Example Verification

**Test LangChain Integration**:
```bash
python examples/langchain_simple.py
```

**Test LangGraph Integration**:
```bash
python examples/langgraph_simple.py
```

**Test Full Demo**:
```bash
python examples/demo_agent.py --mode demo
```

**Test LiteLLM**:
```bash
python examples/litellm_simple.py
```

---

### 5. Code Quality

**Format Code**:
```bash
black neuromem/ --line-length 100
```

**Lint Code**:
```bash
ruff check neuromem/
```

**Type Check**:
```bash
mypy neuromem/
```

**Run All Quality Checks**:
```bash
black neuromem/ --line-length 100 && \
ruff check neuromem/ && \
mypy neuromem/
```

---

### Environment Setup for Testing

```bash
# Required: Set OpenAI key (or other provider)
export OPENAI_API_KEY="sk-..."

# Optional: Configure storage backend
export NEUROMEM_STORAGE_BACKEND="postgres"
export NEUROMEM_POSTGRES_CONNECTION_STRING="postgresql://user:pass@localhost/neuromem"

# Optional: Qdrant
export NEUROMEM_QDRANT_URL="http://localhost:6333"
export NEUROMEM_QDRANT_COLLECTION="neuromem_test"

# Run tests
pytest

# Or run with specific backend
NEUROMEM_STORAGE_BACKEND=sqlite pytest
```

---

## Package Deployment & Distribution

### Package Structure

- **Package Name**: `neuromem-sdk`
- **Distribution**: PyPI (Python Package Index)
- **Version**: 0.1.0 (Alpha)
- **Build System**: Modern Python packaging (`pyproject.toml`)

### Build System

- **Build Backend**: setuptools
- **Configuration**: `pyproject.toml` (PEP 621 compliant)
- **Version**: Defined in `pyproject.toml` under `[project]`

---

### Publishing to PyPI

#### Pre-deployment Checklist

Before publishing a new version:

1. Update version in `pyproject.toml`:
   ```toml
   [project]
   version = "0.1.1"  # Bump version
   ```

2. Run all tests:
   ```bash
   pytest
   ```

3. Check code quality:
   ```bash
   black neuromem/ --line-length 100
   ruff check neuromem/
   mypy neuromem/
   ```

4. Verify configuration:
   ```bash
   python test_setup.py
   ```

5. Test examples work:
   ```bash
   python examples/demo_agent.py --mode demo
   ```

6. Update CHANGELOG or release notes

7. Ensure all dependencies are properly specified in `pyproject.toml`

---

#### Build Commands

```bash
# Install build tools
pip install build twine

# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Build distribution packages
python -m build

# This creates:
# - dist/neuromem_sdk-X.Y.Z-py3-none-any.whl (wheel)
# - dist/neuromem-sdk-X.Y.Z.tar.gz (source distribution)
```

---

#### Publishing

```bash
# Test on TestPyPI first (recommended)
python -m twine upload --repository testpypi dist/*

# Install from TestPyPI to verify
pip install --index-url https://test.pypi.org/simple/ neuromem-sdk

# Test the installed package
python -c "from neuromem import NeuroMem; print('Import successful')"

# If all good, publish to production PyPI
python -m twine upload dist/*
```

**Note**: Publishing to PyPI requires:
- PyPI account
- API token configured in `~/.pypirc`
- Appropriate permissions

---

### Version Management

#### Semantic Versioning

Follow semantic versioning: **MAJOR.MINOR.PATCH**

- **Current**: 0.1.0 (Alpha) - Breaking changes expected
- **Beta**: 0.x.x - API stabilizing but not yet stable
- **Stable**: 1.0.0+ - Backwards-compatible changes only

#### Version Bump Guidelines

| Change Type | Version Bump | Example |
|-------------|--------------|---------|
| Bug fixes, no API changes | PATCH | 0.1.0 → 0.1.1 |
| New features, backwards compatible | MINOR | 0.1.0 → 0.2.0 |
| Breaking API changes | MAJOR | 0.9.0 → 1.0.0 |

**Update Version**:
Edit `pyproject.toml`:
```toml
[project]
version = "0.1.1"  # Update here
```

---

### Installation for Users

#### Standard Installation

```bash
pip install neuromem-sdk
```

#### With Optional Dependencies

```bash
# PostgreSQL support
pip install neuromem-sdk[postgres]

# Qdrant support
pip install neuromem-sdk[qdrant]

# LangChain integration
pip install neuromem-sdk[langchain]

# LangGraph integration
pip install neuromem-sdk[langgraph]

# OpenAI embeddings
pip install neuromem-sdk[openai]

# All extras
pip install neuromem-sdk[all]
```

#### Development Installation

```bash
# Clone repository
git clone https://github.com/neuromem/neuromem-sdk.git
cd neuromem-sdk

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# This allows changes to source code to be immediately reflected
```

---

### Distribution Considerations

#### When Making Changes

1. **Breaking Changes**:
   - Require major version bump (0.x.x → 1.0.0)
   - Document in migration guide
   - Announce prominently in release notes

2. **New Features**:
   - Minor version bump (0.1.x → 0.2.0)
   - Update examples
   - Add to documentation

3. **Bug Fixes**:
   - Patch version bump (0.1.0 → 0.1.1)
   - Add to changelog
   - Consider hotfix release

4. **Dependencies**:
   - Consider version constraints carefully
   - Pin major versions for stability
   - Test with minimum and maximum versions

5. **Storage Backends**:
   - New backends should be optional dependencies
   - Don't bloat core package
   - Use extras: `pip install neuromem-sdk[new-backend]`

6. **Framework Adapters**:
   - Keep as optional extras
   - Don't force framework dependencies
   - Allow users to install only what they need

---

#### Packaging Best Practices

1. **Minimal Core**:
   - Keep core dependencies minimal (currently: numpy, pyyaml)
   - Everything else is optional
   - Reduces installation time and conflicts

2. **Extras Strategy**:
   - Use extras for optional features
   - Clear naming: `postgres`, `qdrant`, `langchain`, etc.
   - `all` extra for convenience

3. **Clean Builds**:
   ```bash
   # Always clean before building
   rm -rf dist/ build/ *.egg-info
   python -m build
   ```

4. **Verify Package**:
   ```bash
   # Check package contents
   tar -tzf dist/neuromem-sdk-*.tar.gz

   # Install in clean environment
   python -m venv test_env
   source test_env/bin/activate
   pip install dist/neuromem_sdk-*.whl
   python -c "from neuromem import NeuroMem"
   ```

5. **Include Necessary Files**:
   - Ensure `LICENSE` is included
   - Include `README.md`
   - Include `neuromem.yaml` template (if applicable)
   - Use `MANIFEST.in` for non-Python files if needed

---

### Release Workflow

#### Pre-release

1. Create feature branch for changes
2. Update version in `pyproject.toml`
3. Run full test suite: `pytest`
4. Update documentation and examples
5. Create PR and get review
6. Merge to main branch

#### Release

1. Merge to main branch
2. Tag release:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```
3. Build package:
   ```bash
   rm -rf dist/ build/ *.egg-info
   python -m build
   ```
4. Test on TestPyPI (optional but recommended):
   ```bash
   python -m twine upload --repository testpypi dist/*
   pip install --index-url https://test.pypi.org/simple/ neuromem-sdk
   ```
5. Publish to PyPI:
   ```bash
   python -m twine upload dist/*
   ```
6. Create GitHub release with changelog
7. Announce release (Twitter, blog, mailing list, etc.)

#### Post-release

1. Verify installation:
   ```bash
   pip install --upgrade neuromem-sdk
   python -c "from neuromem import NeuroMem; print(NeuroMem.__doc__)"
   ```
2. Test examples with published package:
   ```bash
   pip install neuromem-sdk[all]
   python examples/demo_agent.py --mode demo
   ```
3. Monitor for issues (GitHub issues, support channels)
4. Plan next release cycle

---

## Additional Resources

### Examples Directory

The `examples/` directory contains:
- `demo_agent.py` - Full-featured agent with all memory layers
- `langchain_simple.py` - LangChain integration (2-liner)
- `langgraph_simple.py` - LangGraph integration (1-liner)
- `litellm_simple.py` - LiteLLM multi-provider example
- `README.md` - Detailed examples documentation
- `QUICKSTART.md` - Quick start guide

### Configuration Template

See `neuromem.yaml` for a complete configuration template with all options documented.

### Project Links

- **Homepage**: https://github.com/neuromem/neuromem-sdk
- **Documentation**: https://docs.neuromem.ai
- **Issues**: https://github.com/neuromem/neuromem-sdk/issues
- **PyPI**: https://pypi.org/project/neuromem-sdk/

---

## Summary for AI Assistants

### Quick Reference

**Entry Point**: `neuromem/__init__.py` - Start here

**Core Controller**: `neuromem/core/controller.py` - Central orchestrator

**Data Models**: `neuromem/core/types.py` - `MemoryItem`, `MemoryType`

**Storage Interface**: `neuromem/storage/base.py` - Extend for new backends

**Configuration**: `neuromem/config.py` - Load from `neuromem.yaml`

### Common Tasks

1. **New Storage Backend** → Extend `MemoryBackend` in `neuromem/storage/`
2. **Custom Policy** → Add to `neuromem/core/policies/`
3. **Framework Adapter** → Add to `neuromem/adapters/`
4. **Modify Workers** → Edit `neuromem/core/workers/`
5. **Extend Memory Types** → Update `neuromem/memory/` and `core/types.py`

### Testing

- Run tests: `pytest`
- Check quality: `black neuromem/ && ruff check neuromem/ && mypy neuromem/`
- Validate config: `python test_setup.py`
- Test examples: `python examples/demo_agent.py --mode demo`

### Deployment

- Build: `python -m build`
- Test: Publish to TestPyPI first
- Publish: `python -m twine upload dist/*`
- Version: Update in `pyproject.toml`

---

**Last Updated**: 2026-02-05
**SDK Version**: 0.1.0 (Alpha)
