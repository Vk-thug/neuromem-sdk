# Phase 3: NeuroMem Framework-Native Adapters — Implementation Prompt

> Copy-paste this entire prompt into a new Claude Code session to build the framework adapters.
> **Prerequisites**: Phase 1 (MCP server) and Phase 2 (plugins) should be complete, but Phase 3 is independent — it only depends on the existing NeuroMem core.

---

## Objective

Build native Python adapters for five AI agent frameworks: **CrewAI**, **AutoGen (AG2)**, **DSPy**, **Haystack**, and **Semantic Kernel**. Each adapter wraps NeuroMem's memory system into the framework's native extension API so developers can plug in NeuroMem with one line of code.

These complement the MCP server (Phase 1) — MCP is for coding agents and AI platforms, while these adapters are for developers building agents programmatically in Python.

---

## Context

NeuroMem SDK already has adapters for LangChain, LangGraph, and LiteLLM in `neuromem/adapters/`. Phase 3 adapters MUST follow the exact same patterns. Read these files before writing any code:

- `neuromem/adapters/langchain.py` — Most complete reference (LCEL Runnable, chat wrapper, history)
- `neuromem/adapters/litellm.py` — Simpler reference (function wrapper, streaming)
- `neuromem/adapters/__init__.py` — Lazy import pattern with try/except
- `neuromem/__init__.py` — `NeuroMem` facade class with `for_langchain()`, `for_langgraph()`, etc.
- `pyproject.toml` — Optional dependency structure

---

## Existing Adapter Contract

**Every adapter follows this pattern:**

### Constructor
```python
def __init__(self, neuromem, k: int = 5):
    self.neuromem = neuromem
    self.k = k
```

### Retrieve Pattern (always try/except, never crash)
```python
try:
    memories = self.neuromem.retrieve(query=user_query, task_type="chat", k=self.k)
    context = "\n".join([f"- {m.content}" for m in memories]) if memories else ""
except Exception as e:
    logger.warning("Memory retrieval failed", extra={"error": str(e)[:200]})
    context = ""
```

### Store Pattern (always silent fail)
```python
try:
    self.neuromem.observe(user_input, assistant_output)
except Exception:
    pass  # Memory storage is non-critical
```

### Streaming Pattern
1. Forward chunks to user immediately
2. Accumulate text in a list
3. After stream completes, join and call `observe()`

### Context Injection
- For dict-based messages: inject/append to system message
- For message objects: insert SystemMessage after existing system message
- Format: `"Relevant context from memory:\n{joined_memories}"`

---

## File Structure

Create these files:

```
neuromem/adapters/
├── __init__.py          # UPDATE: add lazy imports for new adapters
├── langchain.py         # EXISTING — do not modify
├── langgraph.py         # EXISTING — do not modify
├── litellm.py           # EXISTING — do not modify
├── crewai.py            # NEW
├── autogen.py           # NEW
├── dspy.py              # NEW
├── haystack.py          # NEW
└── semantic_kernel.py   # NEW

tests/
├── test_crewai_adapter.py
├── test_autogen_adapter.py
├── test_dspy_adapter.py
├── test_haystack_adapter.py
└── test_semantic_kernel_adapter.py
```

Plus updates to:
- `neuromem/__init__.py` — add `for_crewai()`, `for_autogen()`, `for_dspy()`, `for_haystack()`, `for_semantic_kernel()` factory methods
- `neuromem/adapters/__init__.py` — add lazy imports for all 5 new adapters
- `pyproject.toml` — add optional dependency groups

---

## Adapter 1: CrewAI (`neuromem/adapters/crewai.py`)

**Package**: `crewai>=1.10.0` (Python >=3.10)
**Integration Points**: Custom `BaseTool` subclasses + `StorageBackend` protocol

### What to Build

#### 1a. CrewAI Tools (4 tools)

```python
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
```

Create these `BaseTool` subclasses, each holding a reference to a `NeuroMem` instance:

**`NeuroMemSearchTool(BaseTool)`**
- `name = "neuromem_search"`
- `description = "Search the memory system for relevant context, past decisions, preferences, and knowledge"`
- Input schema: `query: str`, `k: int = 5`, `memory_type: str | None = None`
- `_run()`: calls `self.neuromem.retrieve(query, task_type="chat", k=k)`, returns formatted string of results
- Include memory type, confidence, and tags in the formatted output

**`NeuroMemStoreTool(BaseTool)`**
- `name = "neuromem_store"`
- `description = "Store important information as a memory — preferences, decisions, facts, or goals"`
- Input schema: `content: str`, `assistant_response: str = "Acknowledged"`, `template: str | None = None`
- `_run()`: calls `self.neuromem.observe(content, assistant_response, template)`

**`NeuroMemConsolidateTool(BaseTool)`**
- `name = "neuromem_consolidate"`
- `description = "Consolidate memories — promote recurring patterns into stable knowledge and apply forgetting curves"`
- No input schema needed
- `_run()`: calls `self.neuromem.consolidate()`

**`NeuroMemContextTool(BaseTool)`**
- `name = "neuromem_context"`
- `description = "Get graph-expanded context for a query — retrieves memories plus related entities and connections"`
- Input schema: `query: str`, `k: int = 8`
- `_run()`: calls `self.neuromem.retrieve_with_context(query, task_type="chat", k=k)`
- Includes expanded_context from metadata in output

**Factory function:**
```python
def create_neuromem_tools(neuromem, k: int = 5) -> list:
    """Create all NeuroMem tools for CrewAI agents.

    Usage:
        tools = create_neuromem_tools(memory, k=5)
        agent = Agent(role="...", tools=tools)
    """
    return [
        NeuroMemSearchTool(neuromem=neuromem, k=k),
        NeuroMemStoreTool(neuromem=neuromem),
        NeuroMemConsolidateTool(neuromem=neuromem),
        NeuroMemContextTool(neuromem=neuromem, k=k),
    ]
```

**Important**: Each tool class needs to store `neuromem` and `k` as class attributes (Pydantic model fields). Use `model_config = ConfigDict(arbitrary_types_allowed=True)` since NeuroMem is not a Pydantic type. Or store it via a private attribute pattern:

```python
class NeuroMemSearchTool(BaseTool):
    name: str = "neuromem_search"
    description: str = "..."
    args_schema: type[BaseModel] = SearchInput
    _neuromem: Any = None  # Private, set via __init__
    _k: int = 5

    def __init__(self, neuromem, k: int = 5, **kwargs):
        super().__init__(**kwargs)
        self._neuromem = neuromem
        self._k = k
```

Check how CrewAI's `BaseTool` handles custom attributes — read the actual source or docs. The Pydantic v2 model may need `model_config = ConfigDict(arbitrary_types_allowed=True)`.

#### 1b. CrewAI StorageBackend (optional, advanced)

Implement CrewAI's `StorageBackend` protocol so NeuroMem can serve as CrewAI's built-in memory backend:

```python
class NeuroMemCrewStorage:
    """CrewAI StorageBackend that delegates to NeuroMem."""

    def __init__(self, neuromem):
        self.neuromem = neuromem

    def save(self, records: list) -> None: ...
    def search(self, query_embedding, ...) -> list: ...
    def delete(self, ...) -> int: ...
    def update(self, record) -> None: ...
    def get_record(self, record_id) -> Any: ...
    def list_records(self, ...) -> list: ...
    def count(self, ...) -> int: ...
    def reset(self, ...) -> None: ...
```

**Important**: This is a deeper integration. Read CrewAI's `StorageBackend` protocol carefully before implementing. The `MemoryRecord` type from CrewAI may need mapping to/from NeuroMem's `MemoryItem`. Only implement this if the protocol is stable — if it's still changing rapidly, skip it and just ship the tools.

### Exports
```python
__all__ = [
    "NeuroMemSearchTool",
    "NeuroMemStoreTool",
    "NeuroMemConsolidateTool",
    "NeuroMemContextTool",
    "create_neuromem_tools",
    "NeuroMemCrewStorage",  # if implemented
]
```

### Usage Example (for README/docstring)
```python
from neuromem import NeuroMem
from neuromem.adapters.crewai import create_neuromem_tools
from crewai import Agent, Task, Crew

memory = NeuroMem.from_config("neuromem.yaml", user_id="user_123")
tools = create_neuromem_tools(memory, k=5)

agent = Agent(
    role="Research Assistant",
    goal="Help the user with context-aware research",
    tools=tools,
)

task = Task(
    description="Find what the user previously decided about the database schema",
    agent=agent,
)

crew = Crew(agents=[agent], tasks=[task])
result = crew.kickoff()
```

---

## Adapter 2: AutoGen / AG2 (`neuromem/adapters/autogen.py`)

**Package**: `ag2>=0.8.0` (Python >=3.10). Also importable as `autogen` or `pyautogen`.
**Integration Points**: Tool registration functions + Teachability-style capability

### What to Build

#### 2a. Tool Registration Functions

Create functions that register NeuroMem operations as AG2 tools on a `ConversableAgent`:

**`register_neuromem_tools(neuromem, caller, executor, k=5)`**

Registers 4 tool functions on the caller (proposes) and executor (runs):

```python
def register_neuromem_tools(
    neuromem,
    caller,       # ConversableAgent — the LLM agent that proposes tool calls
    executor,     # ConversableAgent — the agent that executes tools
    k: int = 5,
) -> None:
    """Register all NeuroMem tools with AutoGen agents.

    Usage:
        register_neuromem_tools(memory, assistant, user_proxy, k=5)
    """
```

Inside, use `autogen.register_function()` (the standalone function) to register:

1. **`search_memory(query: str, k: int = 5) -> str`**
   - Calls `neuromem.retrieve()`, returns formatted results
   - Description: "Search NeuroMem for relevant memories, past decisions, and context"

2. **`store_memory(content: str, response: str = "Acknowledged") -> str`**
   - Calls `neuromem.observe()`, returns confirmation
   - Description: "Store important information as a persistent memory"

3. **`list_memories(memory_type: str = "", limit: int = 20) -> str`**
   - Calls `neuromem.list()`, returns formatted list
   - Description: "List stored memories with optional type filter (episodic, semantic, procedural)"

4. **`consolidate_memories() -> str`**
   - Calls `neuromem.consolidate()`, returns status
   - Description: "Consolidate episodic memories into stable knowledge"

**Important**: AG2's `register_function` requires:
```python
from autogen import register_function

register_function(
    func,
    caller=caller_agent,
    executor=executor_agent,
    name="function_name",
    description="Description for LLM",
)
```

The function must have type annotations and a docstring. AG2 infers the parameter schema from type hints.

#### 2b. NeuroMemCapability Class

Create a `Teachability`-style capability that auto-injects memory context:

```python
class NeuroMemCapability:
    """AG2 capability that adds persistent memory to any ConversableAgent.

    Usage:
        capability = NeuroMemCapability(memory, k=5)
        capability.add_to_agent(assistant)
    """

    def __init__(self, neuromem, k: int = 5):
        self.neuromem = neuromem
        self.k = k

    def add_to_agent(self, agent) -> None:
        """Add memory capability to an AutoGen agent."""
        # Register a process_last_received_message hook
        agent.register_hook(
            hookable_method="process_last_received_message",
            hook=self._enrich_with_memory,
        )

    def _enrich_with_memory(self, message: str) -> str:
        """Hook that prepends relevant memories to incoming messages."""
        try:
            memories = self.neuromem.retrieve(query=message, task_type="chat", k=self.k)
            if memories:
                context = "\n".join([f"- {m.content}" for m in memories])
                return f"[Relevant context from memory:\n{context}]\n\n{message}"
        except Exception:
            pass
        return message
```

**Important**: Check if AG2 still supports `register_hook("process_last_received_message", ...)`. The Teachability contrib module uses this pattern. Read the AG2 docs or source to confirm the hook API.

### Exports
```python
__all__ = [
    "register_neuromem_tools",
    "NeuroMemCapability",
]
```

### Usage Example
```python
from neuromem import NeuroMem
from neuromem.adapters.autogen import register_neuromem_tools, NeuroMemCapability
from autogen import ConversableAgent

memory = NeuroMem.from_config("neuromem.yaml", user_id="user_123")

assistant = ConversableAgent("assistant", llm_config={...})
user_proxy = ConversableAgent("user_proxy", human_input_mode="NEVER")

# Option A: Register as callable tools
register_neuromem_tools(memory, caller=assistant, executor=user_proxy, k=5)

# Option B: Auto-inject context into every message
capability = NeuroMemCapability(memory, k=5)
capability.add_to_agent(assistant)

user_proxy.initiate_chat(assistant, message="What did we decide about the API design?")
```

---

## Adapter 3: DSPy (`neuromem/adapters/dspy.py`)

**Package**: `dspy>=3.0.0` (Python >=3.10)
**Integration Points**: Custom `Retrieve` subclass + `Tool` wrappers for `ReAct`

### What to Build

#### 3a. NeuroMemRetriever (Retrieve subclass)

```python
import dspy
from dspy.primitives.prediction import Prediction

class NeuroMemRetriever(dspy.Retrieve):
    """DSPy retriever backed by NeuroMem's brain-inspired memory system.

    Can be used as a drop-in replacement for any DSPy retriever.
    Supports configuring as the global retriever via dspy.settings.configure(rm=...).

    Usage:
        retriever = NeuroMemRetriever(neuromem, k=5)
        dspy.settings.configure(rm=retriever)

        # Or use directly in a module:
        class MyModule(dspy.Module):
            def __init__(self):
                self.retrieve = NeuroMemRetriever(memory, k=5)
    """

    def __init__(self, neuromem, k: int = 5):
        super().__init__(k=k)
        self.neuromem = neuromem

    def forward(self, query: str, k: int | None = None, **kwargs) -> Prediction:
        k = k if k is not None else self.k
        try:
            results = self.neuromem.retrieve(query=query, task_type="chat", k=k)
            passages = [r.content for r in results]
        except Exception:
            passages = []
        return Prediction(passages=passages)
```

**Important**: Verify that `dspy.Retrieve` still has the same base class API. Check if it's `dspy.Retrieve` or `dspy.retrievers.Retrieve` or `dspy.retrievers.retrieve.Retrieve`. Read the DSPy docs.

#### 3b. Tool Functions for ReAct

Create tool functions that DSPy's `ReAct` module can use:

```python
def create_neuromem_tools(neuromem, k: int = 5) -> list:
    """Create NeuroMem tools for DSPy ReAct agents.

    Usage:
        tools = create_neuromem_tools(memory)
        react = dspy.ReAct("question -> answer", tools=tools)
    """

    def search_memory(query: str, k: int = 5) -> str:
        """Search NeuroMem for relevant memories and context."""
        results = neuromem.retrieve(query=query, task_type="chat", k=k)
        if not results:
            return "No relevant memories found."
        return "\n".join([f"[{r.memory_type.value}] {r.content}" for r in results])

    def store_memory(content: str, response: str = "Acknowledged") -> str:
        """Store important information as a persistent memory."""
        neuromem.observe(content, response)
        return f"Memory stored: {content[:100]}..."

    def get_context(query: str) -> str:
        """Get graph-expanded context with related memories and entity connections."""
        results = neuromem.retrieve_with_context(query=query, task_type="chat", k=k)
        parts = []
        for r in results:
            parts.append(f"[{r.memory_type.value}] {r.content}")
            expanded = r.metadata.get("expanded_context")
            if expanded:
                parts.append(f"  Related: {expanded}")
        return "\n".join(parts) if parts else "No context found."

    return [search_memory, store_memory, get_context]
```

DSPy auto-wraps plain callables into `dspy.Tool` instances. The function's `__name__`, docstring, and type hints define the tool schema.

#### 3c. MemoryAugmented Module (pre-built RAG module)

```python
class MemoryAugmentedQA(dspy.Module):
    """Pre-built DSPy module that retrieves NeuroMem context before answering.

    Usage:
        qa = MemoryAugmentedQA(memory, k=5)
        result = qa(question="What database did we choose?")
        print(result.answer)
    """

    def __init__(self, neuromem, k: int = 5):
        super().__init__()
        self.retrieve = NeuroMemRetriever(neuromem, k=k)
        self.generate = dspy.ChainOfThought("context, question -> answer")

    def forward(self, question: str) -> dspy.Prediction:
        context = self.retrieve(question).passages
        return self.generate(context=context, question=question)
```

### Exports
```python
__all__ = [
    "NeuroMemRetriever",
    "MemoryAugmentedQA",
    "create_neuromem_tools",
]
```

### Usage Example
```python
from neuromem import NeuroMem
from neuromem.adapters.dspy import NeuroMemRetriever, MemoryAugmentedQA, create_neuromem_tools
import dspy

memory = NeuroMem.from_config("neuromem.yaml", user_id="user_123")
lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

# Option A: As global retriever
retriever = NeuroMemRetriever(memory, k=5)
dspy.settings.configure(rm=retriever)

# Option B: Pre-built RAG module
qa = MemoryAugmentedQA(memory, k=5)
result = qa(question="What did we decide about the API schema?")

# Option C: Tools for ReAct
tools = create_neuromem_tools(memory)
react = dspy.ReAct("question -> answer", tools=tools)
result = react(question="Search my memories for database decisions")
```

---

## Adapter 4: Haystack (`neuromem/adapters/haystack.py`)

**Package**: `haystack-ai>=2.20.0` (Python >=3.10)
**Integration Points**: Custom `@component` retriever + writer

### What to Build

#### 4a. NeuroMemRetriever Component

```python
from haystack import component, Document

@component
class NeuroMemRetriever:
    """Haystack component that retrieves documents from NeuroMem.

    Usage in a pipeline:
        pipeline.add_component("retriever", NeuroMemRetriever(memory, top_k=5))
    """

    def __init__(self, neuromem, top_k: int = 5):
        self.neuromem = neuromem
        self.top_k = top_k

    @component.output_types(documents=list[Document])
    def run(self, query: str, top_k: int | None = None) -> dict[str, list[Document]]:
        k = top_k or self.top_k
        try:
            results = self.neuromem.retrieve(query=query, task_type="chat", k=k)
            documents = [
                Document(
                    content=r.content,
                    meta={
                        "memory_id": r.id,
                        "memory_type": r.memory_type.value,
                        "salience": r.salience,
                        "confidence": r.confidence,
                        "tags": r.tags,
                        "created_at": r.created_at.isoformat(),
                        "strength": r.strength,
                    },
                )
                for r in results
            ]
        except Exception:
            documents = []
        return {"documents": documents}
```

**Important**: Verify the `@component` decorator API. Check if it's `from haystack import component` or `from haystack.core.component import component`. Read the Haystack docs.

#### 4b. NeuroMemWriter Component

```python
@component
class NeuroMemWriter:
    """Haystack component that stores documents as NeuroMem memories.

    Usage in a pipeline:
        pipeline.add_component("writer", NeuroMemWriter(memory))
    """

    def __init__(self, neuromem, template: str | None = None):
        self.neuromem = neuromem
        self.template = template

    @component.output_types(memories_written=int)
    def run(self, documents: list[Document]) -> dict[str, int]:
        count = 0
        for doc in documents:
            try:
                user_input = doc.content
                response = doc.meta.get("response", "Stored from Haystack pipeline")
                self.neuromem.observe(user_input, response, template=self.template)
                count += 1
            except Exception:
                pass
        return {"memories_written": count}
```

#### 4c. NeuroMemContextRetriever Component (with graph expansion)

```python
@component
class NeuroMemContextRetriever:
    """Haystack component that retrieves graph-expanded context from NeuroMem.

    Returns documents with expanded_context in metadata.
    """

    def __init__(self, neuromem, top_k: int = 5):
        self.neuromem = neuromem
        self.top_k = top_k

    @component.output_types(documents=list[Document])
    def run(self, query: str, top_k: int | None = None) -> dict[str, list[Document]]:
        k = top_k or self.top_k
        try:
            results = self.neuromem.retrieve_with_context(query=query, task_type="chat", k=k)
            documents = [
                Document(
                    content=r.content,
                    meta={
                        "memory_id": r.id,
                        "memory_type": r.memory_type.value,
                        "confidence": r.confidence,
                        "expanded_context": r.metadata.get("expanded_context", ""),
                    },
                )
                for r in results
            ]
        except Exception:
            documents = []
        return {"documents": documents}
```

### Exports
```python
__all__ = [
    "NeuroMemRetriever",
    "NeuroMemWriter",
    "NeuroMemContextRetriever",
]
```

### Usage Example
```python
from neuromem import NeuroMem
from neuromem.adapters.haystack import NeuroMemRetriever, NeuroMemWriter
from haystack import Pipeline
from haystack.components.generators import OpenAIGenerator
from haystack.components.builders import PromptBuilder

memory = NeuroMem.from_config("neuromem.yaml", user_id="user_123")

# RAG pipeline with NeuroMem
pipeline = Pipeline()
pipeline.add_component("retriever", NeuroMemRetriever(memory, top_k=5))
pipeline.add_component("prompt", PromptBuilder(
    template="Context:\n{% for doc in documents %}- {{ doc.content }}\n{% endfor %}\nQuestion: {{ query }}"
))
pipeline.add_component("llm", OpenAIGenerator(model="gpt-4o-mini"))
pipeline.connect("retriever.documents", "prompt.documents")
pipeline.connect("prompt.prompt", "llm.prompt")

result = pipeline.run({"retriever": {"query": "database decisions"}, "prompt": {"query": "What did we decide?"}})
```

---

## Adapter 5: Semantic Kernel (`neuromem/adapters/semantic_kernel.py`)

**Package**: `semantic-kernel>=1.30.0` (Python >=3.10)
**Integration Points**: `KernelPlugin` with `@kernel_function` methods

### What to Build

#### 5a. NeuroMemPlugin Class

```python
from typing import Annotated

class NeuroMemPlugin:
    """Semantic Kernel plugin exposing NeuroMem memory operations.

    Usage:
        plugin = NeuroMemPlugin(memory, k=5)
        kernel.add_plugin(plugin, plugin_name="neuromem")
    """

    def __init__(self, neuromem, k: int = 5):
        self._neuromem = neuromem
        self._k = k
```

**Important**: Import `kernel_function` from `semantic_kernel.functions`. Check the exact import path — it may be `semantic_kernel.functions.kernel_function_decorator.kernel_function` or `semantic_kernel.functions.kernel_function`. Read the SK docs.

Methods decorated with `@kernel_function`:

**`search_memory`**
```python
@kernel_function(name="search_memory", description="Search NeuroMem for relevant memories and context")
def search_memory(
    self,
    query: Annotated[str, "The search query"],
    k: Annotated[int, "Number of results to return"] = 5,
) -> Annotated[str, "Formatted search results"]:
    results = self._neuromem.retrieve(query=query, task_type="chat", k=k)
    if not results:
        return "No relevant memories found."
    return "\n".join([f"[{r.memory_type.value}] (conf:{r.confidence:.2f}) {r.content}" for r in results])
```

**`store_memory`**
```python
@kernel_function(name="store_memory", description="Store important information as a persistent memory")
def store_memory(
    self,
    content: Annotated[str, "The content to remember"],
    response: Annotated[str, "The assistant's response"] = "Acknowledged",
    template: Annotated[str, "Memory template: preference, decision, fact, goal, or empty"] = "",
) -> Annotated[str, "Confirmation"]:
    self._neuromem.observe(content, response, template=template or None)
    return f"Memory stored: {content[:100]}..."
```

**`list_memories`**
```python
@kernel_function(name="list_memories", description="List stored memories with optional type filter")
def list_memories(
    self,
    memory_type: Annotated[str, "Filter: episodic, semantic, procedural, or empty for all"] = "",
    limit: Annotated[int, "Maximum number of results"] = 20,
) -> Annotated[str, "Formatted memory list"]:
    results = self._neuromem.list(memory_type=memory_type or None, limit=limit)
    if not results:
        return "No memories found."
    lines = [f"[{r.id[:8]}] [{r.memory_type.value}] {r.content[:80]}..." for r in results]
    return f"Found {len(results)} memories:\n" + "\n".join(lines)
```

**`consolidate_memories`**
```python
@kernel_function(name="consolidate_memories", description="Consolidate episodic memories into stable knowledge")
def consolidate_memories(self) -> Annotated[str, "Consolidation result"]:
    self._neuromem.consolidate()
    return "Memory consolidation complete."
```

**`get_context`**
```python
@kernel_function(name="get_context", description="Get graph-expanded context with related memories")
def get_context(
    self,
    query: Annotated[str, "The query to get context for"],
    k: Annotated[int, "Number of results"] = 8,
) -> Annotated[str, "Context with related memories"]:
    results = self._neuromem.retrieve_with_context(query=query, task_type="chat", k=k)
    parts = []
    for r in results:
        parts.append(f"[{r.memory_type.value}] {r.content}")
        expanded = r.metadata.get("expanded_context")
        if expanded:
            parts.append(f"  → Related: {expanded}")
    return "\n".join(parts) if parts else "No context found."
```

#### 5b. Helper Function

```python
def create_neuromem_plugin(neuromem, k: int = 5, plugin_name: str = "neuromem"):
    """Create a Semantic Kernel KernelPlugin from NeuroMem.

    Usage:
        kernel = Kernel()
        plugin = create_neuromem_plugin(memory)
        kernel.add_plugin(plugin, plugin_name="neuromem")
    """
    from semantic_kernel.functions import KernelPlugin

    instance = NeuroMemPlugin(neuromem, k=k)
    return KernelPlugin.from_object(
        plugin_name=plugin_name,
        plugin_instance=instance,
        description="Brain-inspired memory system with episodic, semantic, and procedural memory layers",
    )
```

**Important**: Verify `KernelPlugin.from_object()` signature. It might be a classmethod. Check SK docs.

### Exports
```python
__all__ = [
    "NeuroMemPlugin",
    "create_neuromem_plugin",
]
```

### Usage Example
```python
from neuromem import NeuroMem
from neuromem.adapters.semantic_kernel import create_neuromem_plugin
from semantic_kernel import Kernel

memory = NeuroMem.from_config("neuromem.yaml", user_id="user_123")
kernel = Kernel()

plugin = create_neuromem_plugin(memory, k=5)
kernel.add_plugin(plugin, plugin_name="neuromem")

# Use with automatic function calling
result = await kernel.invoke(
    plugin_name="neuromem",
    function_name="search_memory",
    query="What database did we choose?",
)
```

---

## Updates to Existing Files

### `neuromem/__init__.py` — Add Factory Methods

Add these classmethods to the `NeuroMem` class (follow the existing `for_langchain` pattern exactly):

```python
@classmethod
def for_crewai(cls, user_id: str, config_path: str = "neuromem.yaml"):
    """Quick initialization for CrewAI integration.

    Usage:
        memory = NeuroMem.for_crewai(user_id="user_123")
        from neuromem.adapters.crewai import create_neuromem_tools
        tools = create_neuromem_tools(memory)
    """
    return cls.from_config(config_path, user_id)

@classmethod
def for_autogen(cls, user_id: str, config_path: str = "neuromem.yaml"):
    """Quick initialization for AutoGen (AG2) integration."""
    return cls.from_config(config_path, user_id)

@classmethod
def for_dspy(cls, user_id: str, config_path: str = "neuromem.yaml"):
    """Quick initialization for DSPy integration."""
    return cls.from_config(config_path, user_id)

@classmethod
def for_haystack(cls, user_id: str, config_path: str = "neuromem.yaml"):
    """Quick initialization for Haystack integration."""
    return cls.from_config(config_path, user_id)

@classmethod
def for_semantic_kernel(cls, user_id: str, config_path: str = "neuromem.yaml"):
    """Quick initialization for Semantic Kernel integration."""
    return cls.from_config(config_path, user_id)
```

### `neuromem/adapters/__init__.py` — Add Lazy Imports

Follow the exact pattern used for LangChain/LangGraph/LiteLLM:

```python
# CrewAI
try:
    from neuromem.adapters.crewai import (
        NeuroMemSearchTool,
        NeuroMemStoreTool,
        NeuroMemConsolidateTool,
        NeuroMemContextTool,
        create_neuromem_tools as create_crewai_tools,
    )
    _CREWAI_AVAILABLE = True
except ImportError:
    _CREWAI_AVAILABLE = False

# AutoGen
try:
    from neuromem.adapters.autogen import (
        register_neuromem_tools,
        NeuroMemCapability,
    )
    _AUTOGEN_AVAILABLE = True
except ImportError:
    _AUTOGEN_AVAILABLE = False

# DSPy
try:
    from neuromem.adapters.dspy import (
        NeuroMemRetriever as DSPyRetriever,
        MemoryAugmentedQA,
        create_neuromem_tools as create_dspy_tools,
    )
    _DSPY_AVAILABLE = True
except ImportError:
    _DSPY_AVAILABLE = False

# Haystack
try:
    from neuromem.adapters.haystack import (
        NeuroMemRetriever as HaystackRetriever,
        NeuroMemWriter,
        NeuroMemContextRetriever,
    )
    _HAYSTACK_AVAILABLE = True
except ImportError:
    _HAYSTACK_AVAILABLE = False

# Semantic Kernel
try:
    from neuromem.adapters.semantic_kernel import (
        NeuroMemPlugin,
        create_neuromem_plugin,
    )
    _SEMANTIC_KERNEL_AVAILABLE = True
except ImportError:
    _SEMANTIC_KERNEL_AVAILABLE = False
```

Add all to `__all__`.

### `pyproject.toml` — Add Optional Dependencies

```toml
[project.optional-dependencies]
# ... existing entries ...
crewai = [
    "crewai>=1.10.0",
]
autogen = [
    "ag2>=0.8.0",
]
dspy = [
    "dspy>=3.0.0",
]
haystack = [
    "haystack-ai>=2.20.0",
]
semantic-kernel = [
    "semantic-kernel>=1.30.0",
]

# Update 'all' to include new adapters
all = [
    # ... existing entries ...
    "crewai>=1.10.0",
    "ag2>=0.8.0",
    "dspy>=3.0.0",
    "haystack-ai>=2.20.0",
    "semantic-kernel>=1.30.0",
]
```

---

## Testing

Create test files using pytest. Mock the `NeuroMem` instance to avoid needing real embeddings/storage.

### Test Pattern (same for all adapters)

```python
import pytest
from unittest.mock import MagicMock, patch
from neuromem.core.types import MemoryItem, MemoryType
from datetime import datetime


@pytest.fixture
def mock_neuromem():
    """Create a mock NeuroMem instance."""
    nm = MagicMock()
    nm.retrieve.return_value = [
        MemoryItem(
            id="mem-001",
            user_id="test",
            content="User prefers Python type annotations",
            embedding=[0.1] * 10,
            memory_type=MemoryType.PROCEDURAL,
            salience=0.8,
            confidence=0.9,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            decay_rate=0.01,
            reinforcement=3,
            inferred=False,
            editable=True,
            tags=["preference", "python"],
            metadata={},
            strength=0.85,
        ),
    ]
    nm.observe.return_value = None
    nm.list.return_value = nm.retrieve.return_value
    nm.consolidate.return_value = None
    nm.retrieve_with_context.return_value = nm.retrieve.return_value
    return nm
```

### Per-Adapter Tests

#### `tests/test_crewai_adapter.py`
```python
def test_search_tool_run(mock_neuromem):
def test_store_tool_run(mock_neuromem):
def test_consolidate_tool_run(mock_neuromem):
def test_context_tool_run(mock_neuromem):
def test_create_tools_returns_four(mock_neuromem):
def test_search_tool_handles_empty_results(mock_neuromem):
def test_search_tool_handles_exception(mock_neuromem):
def test_store_tool_handles_exception(mock_neuromem):
```

#### `tests/test_autogen_adapter.py`
```python
def test_register_tools(mock_neuromem):
def test_capability_enriches_message(mock_neuromem):
def test_capability_handles_retrieval_failure(mock_neuromem):
def test_capability_no_results(mock_neuromem):
```

#### `tests/test_dspy_adapter.py`
```python
def test_retriever_forward(mock_neuromem):
def test_retriever_returns_prediction(mock_neuromem):
def test_retriever_handles_exception(mock_neuromem):
def test_create_tools_returns_three(mock_neuromem):
def test_memory_augmented_qa_init(mock_neuromem):
```

#### `tests/test_haystack_adapter.py`
```python
def test_retriever_run(mock_neuromem):
def test_retriever_returns_documents(mock_neuromem):
def test_retriever_handles_exception(mock_neuromem):
def test_writer_run(mock_neuromem):
def test_writer_counts_written(mock_neuromem):
def test_context_retriever_run(mock_neuromem):
```

#### `tests/test_semantic_kernel_adapter.py`
```python
def test_plugin_search_memory(mock_neuromem):
def test_plugin_store_memory(mock_neuromem):
def test_plugin_list_memories(mock_neuromem):
def test_plugin_consolidate(mock_neuromem):
def test_plugin_get_context(mock_neuromem):
def test_create_plugin(mock_neuromem):
```

**Important**: For each test, mock the framework's dependencies if the framework itself isn't installed. Use `pytest.importorskip("crewai")` to skip tests when the framework package is not available:

```python
crewai = pytest.importorskip("crewai")
```

---

## Implementation Order

1. **CrewAI adapter** (`crewai.py`) — Most straightforward (BaseTool subclasses)
2. **DSPy adapter** (`dspy.py`) — Clean Retrieve subclass pattern
3. **Haystack adapter** (`haystack.py`) — Clean @component pattern
4. **AutoGen adapter** (`autogen.py`) — register_function + hook capability
5. **Semantic Kernel adapter** (`semantic_kernel.py`) — @kernel_function + KernelPlugin
6. **Update `__init__.py`** — Factory methods
7. **Update `adapters/__init__.py`** — Lazy imports
8. **Update `pyproject.toml`** — Optional dependencies
9. **Tests** — All 5 test files
10. **Verify** — `pip install -e ".[crewai,dspy,haystack]"` and run tests

---

## Quality Checklist

- [ ] Each adapter follows the existing pattern (constructor with neuromem + k, try/except on all memory ops)
- [ ] Each adapter has a factory function (e.g., `create_neuromem_tools()` or `create_neuromem_plugin()`)
- [ ] `NeuroMem` class has `for_{framework}()` classmethod for each adapter
- [ ] `adapters/__init__.py` has try/except lazy imports for all 5 adapters
- [ ] `pyproject.toml` has optional dependency group for each framework
- [ ] All tests pass with mocked NeuroMem (no real API calls)
- [ ] Tests skip gracefully when framework package is not installed
- [ ] No modifications to existing adapter files (langchain.py, langgraph.py, litellm.py)
- [ ] No modifications to core NeuroMem files (except __init__.py factory methods)
- [ ] Black + ruff pass on all new code
- [ ] Type annotations on all function signatures
- [ ] Docstrings with usage examples on all public classes/functions
- [ ] Error handling: memory failures never crash the host framework

---

## Key Reminders

1. **Read the framework docs before coding** — APIs change frequently. Verify import paths, class names, and method signatures against the actual installed package, not just this prompt.
   - CrewAI: https://docs.crewai.com
   - AG2: https://docs.ag2.ai
   - DSPy: https://dspy.ai
   - Haystack: https://docs.haystack.deepset.ai
   - Semantic Kernel: https://learn.microsoft.com/en-us/semantic-kernel/

2. **Follow existing adapter patterns exactly** — read `adapters/litellm.py` (simpler) and `adapters/langchain.py` (richer) before writing anything.

3. **Memory operations are always non-critical** — wrap in try/except, never let a memory failure crash the user's agent/pipeline.

4. **Pydantic v2 compatibility** — CrewAI and Semantic Kernel use Pydantic v2. Use `model_config = ConfigDict(arbitrary_types_allowed=True)` when storing NeuroMem instances as model fields.

5. **Test without real dependencies** — use `pytest.importorskip()` and mock everything. Tests should pass even if the framework isn't installed (they just skip).
