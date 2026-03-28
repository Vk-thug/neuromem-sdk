# Phase 1: NeuroMem MCP Server — Implementation Prompt

> Copy-paste this entire prompt into a new Claude Code session to implement the MCP server.

---

## Objective

Build an MCP (Model Context Protocol) server for NeuroMem SDK that exposes the brain-inspired memory system to **every major coding agent and AI platform**: Claude Code, Cline, Cursor, OpenAI Codex CLI, Gemini CLI, Windsurf, GitHub Copilot, Claude.ai, ChatGPT, and Google AI Studio.

**One MCP server = instant access to 10+ platforms.**

---

## Context

NeuroMem SDK (`neuromem-sdk` v0.2.0) is a brain-inspired memory system with:
- 4 memory types: episodic, semantic, procedural, affective
- Ebbinghaus forgetting curves (strength = e^(-decay * time))
- LLM-driven consolidation (episodic -> semantic)
- Graph-augmented retrieval with entity extraction + RRF merge
- Multi-hop query decomposition
- Multiple storage backends: PostgreSQL+pgvector, Qdrant, SQLite, in-memory
- Existing adapters: LangChain, LangGraph, LiteLLM

The MCP server wraps the existing `NeuroMem` facade class. Do NOT rewrite core logic — just expose it via MCP tools/resources/prompts.

---

## Technical Requirements

### MCP Python SDK
- Package: `mcp` (latest: 1.26.0+, requires Python 3.10+)
- Use the **FastMCP** high-level API (`from mcp.server.fastmcp import FastMCP`)
- Docs: https://modelcontextprotocol.io/docs/sdk and https://gofastmcp.com
- **IMPORTANT**: Read the actual `mcp` package docs before coding. Do NOT guess the API.

### Transport Support
- **stdio** (default) — for local coding agents (Claude Code, Cline, Cursor, Codex, Gemini CLI, Copilot)
- **Streamable HTTP** — for cloud platforms (Claude.ai, ChatGPT, Google AI Studio)
- Both transports from a single entry point via CLI argument

### Python Version
- MCP module requires Python 3.10+ (this is fine — it's an optional extra)
- Core NeuroMem SDK stays at 3.9+ (no changes to existing code)

---

## File Structure

Create these files:

```
neuromem/mcp/
├── __init__.py          # Package init, exports create_server()
├── server.py            # FastMCP server definition with all tools/resources/prompts
├── __main__.py          # Entry point: python -m neuromem.mcp [--transport stdio|http] [--port 8000]
└── types.py             # Pydantic models for MCP tool inputs/outputs
```

Plus updates to:
- `pyproject.toml` — add `mcp` optional dependency + console script entry point
- `neuromem/__init__.py` — add `for_mcp()` classmethod (follows existing pattern)

---

## Detailed Specifications

### 1. MCP Tools (12 tools)

Each tool maps to an existing NeuroMem public API method. Use Pydantic models for typed inputs.

#### `store_memory`
- **Maps to**: `NeuroMem.observe(user_input, assistant_output, template)`
- **Input**: `content: str` (required), `assistant_response: str` (optional, default "Acknowledged"), `template: str | None` (optional — decision/preference/fact/goal/feedback)
- **Output**: `{"status": "stored", "turn_count": int}`
- **Description**: "Store a memory from a user-assistant interaction. NeuroMem automatically detects memory type, extracts entities, and indexes for retrieval."

#### `search_memories`
- **Maps to**: `NeuroMem.retrieve(query, task_type, k)`
- **Input**: `query: str` (required), `task_type: str = "chat"`, `k: int = 8`
- **Output**: List of `{"id": str, "content": str, "memory_type": str, "salience": float, "confidence": float, "tags": list, "created_at": str, "strength": float}`
- **Description**: "Semantic search across all memory layers with multi-hop query decomposition, graph-augmented retrieval, and brain-inspired ranking."

#### `search_advanced`
- **Maps to**: `NeuroMem.search(query_string, k)`
- **Input**: `query_string: str` (required), `k: int = 10`
- **Output**: Same format as `search_memories`
- **Description**: "Advanced search with structured query syntax. Supports: type:semantic tag:preference confidence:>0.8 after:2024-01-01 'exact phrase'"

#### `get_context`
- **Maps to**: `NeuroMem.retrieve_with_context(query, task_type, k)`
- **Input**: `query: str` (required), `task_type: str = "chat"`, `k: int = 8`
- **Output**: Same as search + `expanded_context` field from metadata
- **Description**: "Retrieve memories with automatic graph-based context expansion. Related memories are attached as expanded context (like Obsidian transclusion)."

#### `get_memory`
- **Maps to**: `controller.get_memory_by_id(memory_id)` — you'll need to add this thin wrapper if it doesn't exist, checking all backends
- **Input**: `memory_id: str` (required)
- **Output**: Single memory dict or error
- **Description**: "Get a specific memory by its ID."

#### `list_memories`
- **Maps to**: `NeuroMem.list(memory_type, limit)`
- **Input**: `memory_type: str | None = None` (episodic/semantic/procedural), `limit: int = 50`
- **Output**: List of memory dicts
- **Description**: "List all memories, optionally filtered by type."

#### `update_memory`
- **Maps to**: `NeuroMem.update(memory_id, content)`
- **Input**: `memory_id: str` (required), `content: str` (required)
- **Output**: `{"status": "updated", "memory_id": str}`
- **Description**: "Update the content of an existing memory."

#### `delete_memory`
- **Maps to**: `NeuroMem.forget(memory_id)`
- **Input**: `memory_id: str` (required)
- **Output**: `{"status": "deleted", "memory_id": str}`
- **Description**: "Permanently delete a memory."

#### `consolidate`
- **Maps to**: `NeuroMem.consolidate()`
- **Input**: None
- **Output**: `{"status": "completed", "message": str}`
- **Description**: "Trigger memory consolidation — promotes recurring episodic patterns into stable semantic knowledge, applies forgetting curves, and merges similar facts."

#### `get_stats`
- **Maps to**: `NeuroMem.list()` counts + health check
- **Input**: None
- **Output**: `{"total_memories": int, "by_type": {"episodic": int, "semantic": int, "procedural": int}, "user_id": str, "storage_backend": str}`
- **Description**: "Get memory system statistics and health status."

#### `find_by_tags`
- **Maps to**: `NeuroMem.find_by_tags(tag_prefix, limit)`
- **Input**: `tag_prefix: str` (required), `limit: int = 50`
- **Output**: List of memory dicts
- **Description**: "Find memories by hierarchical tag prefix (e.g., 'topic:ai' matches topic:ai/memory)."

#### `get_graph`
- **Maps to**: `NeuroMem.get_graph()`
- **Input**: None
- **Output**: `{"nodes": [...], "edges": [...]}`
- **Description**: "Export the memory relationship graph showing entities and their connections."

### 2. MCP Resources (3 resources)

#### `neuromem://memories/recent`
- Returns last 20 memories across all types as formatted text
- Use `@mcp.resource("neuromem://memories/recent")`

#### `neuromem://memories/stats`
- Returns memory counts by type, total count, user_id
- Use `@mcp.resource("neuromem://memories/stats")`

#### `neuromem://config`
- Returns current NeuroMem configuration summary (storage type, embedding model, decay settings)
- Use `@mcp.resource("neuromem://config")`

### 3. MCP Prompts (2 prompts)

#### `memory_context`
- **Args**: `query: str`
- Retrieves relevant memories and formats them as a context prompt
- Returns: "Based on stored memories:\n\n{formatted memories}\n\nUse this context to inform your response."

#### `memory_summary`
- **Args**: `topic: str | None = None`
- If topic: searches for related memories and summarizes
- If no topic: provides overall memory system summary
- Returns formatted summary text

---

## Implementation Details

### Server Initialization (Lifespan Pattern)

Use FastMCP's lifespan to manage NeuroMem instance lifecycle:

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

@asynccontextmanager
async def neuromem_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Initialize NeuroMem on server start, cleanup on stop."""
    config_path = os.environ.get("NEUROMEM_CONFIG", "neuromem.yaml")
    user_id = os.environ.get("NEUROMEM_USER_ID", "default")

    memory = NeuroMem.from_config(config_path, user_id)
    try:
        yield {"memory": memory, "user_id": user_id}
    finally:
        memory.close()

mcp = FastMCP(
    "neuromem",
    instructions="NeuroMem is a brain-inspired memory system...",
    lifespan=neuromem_lifespan
)
```

Access the NeuroMem instance inside tools via FastMCP's `Context`:

```python
from mcp.server.fastmcp import Context

@mcp.tool()
async def search_memories(query: str, k: int = 8, ctx: Context) -> list[dict]:
    memory = ctx.request_context.lifespan_context["memory"]
    # ... use memory.retrieve()
```

**IMPORTANT**: Read the FastMCP docs to confirm the exact `ctx` API. The context access pattern may differ — check https://gofastmcp.com for the current API. Do NOT assume the above code is correct.

### Async Bridging

NeuroMem's core is synchronous. MCP tools are async. Bridge with:

```python
import asyncio

@mcp.tool()
async def search_memories(query: str, k: int = 8, ctx: Context) -> list[dict]:
    memory = get_memory_from_ctx(ctx)
    results = await asyncio.to_thread(memory.retrieve, query=query, k=k)
    return [serialize_memory(m) for m in results]
```

### Memory Serialization

Create a `serialize_memory(item: MemoryItem) -> dict` helper that converts MemoryItem to JSON-safe dict:
- Convert datetime fields to ISO 8601 strings
- Exclude `embedding` field (too large for MCP responses)
- Include: id, content, memory_type (as string), salience, confidence, tags, created_at, last_accessed, strength, reinforcement, metadata
- Handle `expanded_context` from metadata if present

### User Scoping

Support per-tool user_id override (optional parameter on relevant tools):
- Default: `NEUROMEM_USER_ID` env var (set at server start)
- Override: pass `user_id` parameter to individual tools
- If user_id differs from the initialized instance's user_id, create a new NeuroMem instance (cache them)

For v1, keep it simple: single user_id from env var. Multi-user can come later.

### Error Handling

- Wrap each tool in try/except
- Return structured error: `{"error": str, "tool": str}`
- Log errors via neuromem's logger
- Never crash the MCP server on a tool error

---

## Entry Point (`__main__.py`)

```
Usage:
  python -m neuromem.mcp                          # stdio transport (default)
  python -m neuromem.mcp --transport http          # HTTP transport
  python -m neuromem.mcp --transport http --port 8000  # HTTP on custom port
  python -m neuromem.mcp --transport sse           # SSE transport (legacy)

Environment Variables:
  NEUROMEM_CONFIG     Path to neuromem.yaml (default: ./neuromem.yaml)
  NEUROMEM_USER_ID    Default user ID (default: "default")
  OPENAI_API_KEY      Required for embeddings
```

Use `argparse` for CLI arguments. Call `mcp.run(transport=...)` with the appropriate transport.

---

## pyproject.toml Changes

Add these to `[project.optional-dependencies]`:

```toml
mcp = [
    "mcp>=1.26.0",
    "pydantic>=2.0.0",
]
```

Add `mcp` to the `all` extras list too.

Add a console script entry point:

```toml
[project.scripts]
neuromem-mcp = "neuromem.mcp.__main__:main"
```

---

## NeuroMem Facade Addition

Add `for_mcp()` classmethod to `neuromem/__init__.py` (follows existing `for_langchain`, `for_langgraph`, `for_litellm` pattern):

```python
@classmethod
def for_mcp(cls, user_id: str = "default", config_path: str = "neuromem.yaml"):
    """
    Quick initialization for MCP server integration.

    Usage:
        python -m neuromem.mcp
        # Or: neuromem-mcp
    """
    return cls.from_config(config_path, user_id)
```

---

## Testing

Create `tests/test_mcp.py` with:

1. **Unit tests** — test each tool function directly (mock NeuroMem instance)
2. **Serialization tests** — test `serialize_memory()` with various MemoryItem states
3. **Integration test** — start MCP server via stdio, send JSON-RPC messages, verify responses

Test tool naming:
```python
def test_store_memory_tool():
def test_search_memories_tool():
def test_search_advanced_tool():
def test_get_context_tool():
def test_get_memory_tool():
def test_list_memories_tool():
def test_update_memory_tool():
def test_delete_memory_tool():
def test_consolidate_tool():
def test_get_stats_tool():
def test_find_by_tags_tool():
def test_get_graph_tool():
def test_serialize_memory():
def test_serialize_memory_with_expanded_context():
def test_server_lifespan():
```

---

## Client Configuration Examples

After building, document how to connect from each platform:

### Claude Code
```bash
claude mcp add neuromem -- python -m neuromem.mcp
```

Or in `.mcp.json`:
```json
{
  "mcpServers": {
    "neuromem": {
      "command": "python",
      "args": ["-m", "neuromem.mcp"],
      "env": {
        "NEUROMEM_CONFIG": "./neuromem.yaml",
        "NEUROMEM_USER_ID": "vikram",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

### Cline (VS Code)
In `cline_mcp_settings.json`:
```json
{
  "mcpServers": {
    "neuromem": {
      "command": "python",
      "args": ["-m", "neuromem.mcp"],
      "env": {
        "NEUROMEM_CONFIG": "./neuromem.yaml",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

### Cursor
Settings > Features > MCP > Add Server:
```json
{
  "neuromem": {
    "command": "python",
    "args": ["-m", "neuromem.mcp"],
    "env": { "NEUROMEM_CONFIG": "./neuromem.yaml" }
  }
}
```

### OpenAI Codex CLI
In `.mcp.json`:
```json
{
  "mcpServers": {
    "neuromem": {
      "command": "python",
      "args": ["-m", "neuromem.mcp"],
      "env": { "NEUROMEM_CONFIG": "./neuromem.yaml" }
    }
  }
}
```

### Gemini CLI
In `~/.gemini/extensions/neuromem/gemini-extension.json`:
```json
{
  "name": "neuromem",
  "version": "0.2.0",
  "description": "Brain-inspired memory for AI agents",
  "mcpServers": {
    "neuromem": {
      "command": "python",
      "args": ["-m", "neuromem.mcp"],
      "env": { "NEUROMEM_CONFIG": "${workspacePath}/neuromem.yaml" }
    }
  }
}
```

### Claude.ai / ChatGPT (Remote HTTP)
Start server:
```bash
python -m neuromem.mcp --transport http --port 8000
```
Then add `http://localhost:8000/mcp` (or deployed URL) as a custom connector.

---

## Implementation Order

1. **`neuromem/mcp/types.py`** — Pydantic models for tool I/O + `serialize_memory()` helper
2. **`neuromem/mcp/server.py`** — FastMCP server with all 12 tools, 3 resources, 2 prompts
3. **`neuromem/mcp/__init__.py`** — Export `create_server()`
4. **`neuromem/mcp/__main__.py`** — CLI entry point with argparse
5. **`neuromem/__init__.py`** — Add `for_mcp()` classmethod
6. **`pyproject.toml`** — Add `mcp` extra + console script
7. **`tests/test_mcp.py`** — Tests
8. **Verify** — `python -m neuromem.mcp` starts without error, `claude mcp add` connects

---

## Quality Checklist

- [ ] All 12 tools work and return typed responses
- [ ] All 3 resources return data
- [ ] Both prompts generate useful context
- [ ] stdio transport works (`python -m neuromem.mcp`)
- [ ] HTTP transport works (`python -m neuromem.mcp --transport http`)
- [ ] `neuromem-mcp` console script works
- [ ] Error handling: no tool crashes the server
- [ ] MemoryItem serialization excludes embeddings
- [ ] Datetimes are ISO 8601 strings in output
- [ ] Tests pass with `pytest tests/test_mcp.py`
- [ ] No changes to existing core NeuroMem code (only new files + pyproject.toml + facade method)
- [ ] `pip install neuromem-sdk[mcp]` installs all dependencies
- [ ] Black + ruff pass on new code

---

## Key Reminders

1. **Read the `mcp` package docs first** — https://gofastmcp.com and https://modelcontextprotocol.io/docs/sdk. The FastMCP API may have changed. Verify `Context` access patterns, `lifespan` signature, and `mcp.run()` transport options.
2. **Do NOT modify existing NeuroMem core files** except adding `for_mcp()` to `__init__.py` and updating `pyproject.toml`.
3. **Keep it simple** — single user_id from env var, no auth layer, no multi-tenant. These come in Phase 2.
4. **Follow existing patterns** — look at how `adapters/langchain.py` wraps NeuroMem. The MCP server does the same thing but over JSON-RPC instead of Python function calls.
5. **Tool descriptions matter** — MCP clients show these to the LLM. Write clear, specific descriptions that help the LLM choose the right tool.
