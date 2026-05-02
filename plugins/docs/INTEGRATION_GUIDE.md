# NeuroMem Integration Guide — All Platforms

NeuroMem's MCP server works with every major coding agent and AI platform.
**As of v0.4.7, MCP is mounted in-process by `neuromem ui`** — there's no
second process to manage. All MCP-aware clients point at the same URL:
`http://127.0.0.1:7777/mcp/`.

For the n8n-style 4-step first-run flow, see [QUICKSTART.md](./QUICKSTART.md).

## Prerequisites (all platforms)

```bash
pip install 'neuromem-sdk[ui,mcp]'      # 1. install
neuromem init                            # 2. wizard writes neuromem.yaml
neuromem ui                              # 3. starts UI + MCP at :7777
```

That's it. The wizard mints a UUID, auto-creates `~/.neuromem/` (if you
pick SQLite), and writes `mcp.enabled: true` so step 3 exposes both the
UI and the MCP endpoints.

`OPENAI_API_KEY` is only required if you switched the wizard's embedding
choice from Ollama to OpenAI.

---

## Platforms with full plugin bundles

### Claude Code
```bash
cd plugins/claude-code && claude plugin install .
```
Slash commands (`/remember`, `/recall`, `/forget`, `/memories`,
`/consolidate`), an auto-context skill, a memory-assistant agent, and
hooks. See [`plugins/claude-code/README.md`](../claude-code/README.md).

### Cursor
```bash
cp plugins/cursor/.cursor/mcp.json ~/.cursor/mcp.json
```
Config-only. Twelve MCP tools appear in the Cursor MCP panel. See
[`plugins/cursor/README.md`](../cursor/README.md).

### Antigravity
```bash
cp plugins/antigravity/.antigravity/mcp.json ~/.antigravity/mcp.json
```
Config-only. See [`plugins/antigravity/README.md`](../antigravity/README.md).

### Gemini CLI
```bash
cd plugins/gemini-cli && gemini extensions link .
```
TOML commands + GEMINI.md context file + MCP. See
[`plugins/gemini-cli/README.md`](../gemini-cli/README.md).

### OpenAI Codex CLI
```bash
cp -r plugins/codex-cli ~/.agents/plugins/neuromem
```
Skill-only. See [`plugins/codex-cli/README.md`](../codex-cli/README.md).

---

## MCP-only platforms (config snippet)

Drop this into your client's MCP settings (path varies by client):

```json
{
  "mcpServers": {
    "neuromem": {
      "type": "http",
      "url": "http://127.0.0.1:7777/mcp/"
    }
  }
}
```

Confirmed-working clients:

| Client | Settings location |
|---|---|
| Cline (VS Code) | `cline_mcp_settings.json` |
| Windsurf / Cascade | Settings → MCP Servers |
| GitHub Copilot (Agent Mode) | Repository or VS Code MCP config |
| Aider | `.aider.conf.yml` (community MCP support) |

---

## Cloud chat clients (Claude.ai, ChatGPT, Google AI Studio)

These can't reach `127.0.0.1` — expose the in-process MCP through a tunnel:

```bash
neuromem ui --public                  # cloudflared tunnel by default
```

This prints a public URL (e.g., `https://abc-def.trycloudflare.com/mcp/`)
plus a copy-pasteable connector config for Claude.ai, ChatGPT, and
Gemini chat. The tunnel writes `~/.neuromem/mcp-public.json` with the
matching connector blobs.

### Claude.ai
1. Settings → Connectors → Add Custom Connector
2. Name: "NeuroMem"
3. URL: paste the public URL from the banner
4. Works on web, iOS, and Android

### ChatGPT
1. Settings → Connectors → Advanced → Developer Mode
2. Add MCP server URL: paste the public URL
3. The 12 NeuroMem tools appear as actions

### Google AI Studio
Use the Google Gen AI SDK; pass the URL as an MCP tool provider.

---

## Standalone `neuromem-mcp` (Docker / headless)

If you can't run `neuromem ui` in your environment (Docker container,
agent-host without the UI extras, CI), fall back to the standalone
console script:

```bash
neuromem-mcp                                # stdio
neuromem-mcp --transport http --port 8000   # HTTP at /mcp
neuromem-mcp --transport http --public      # HTTP + cloudflared tunnel
```

Then point your client at the standalone URL or use the stdio config:

```json
{
  "mcpServers": {
    "neuromem": {
      "command": "python",
      "args": ["-m", "neuromem.mcp"],
      "env": {
        "NEUROMEM_CONFIG": "./neuromem.yaml",
        "NEUROMEM_USER_ID": "<uuid-from-yaml>"
      }
    }
  }
}
```

---

## Available MCP tools (12)

| Tool | Description |
|------|-------------|
| `store_memory` | Store a user-assistant interaction with auto-type detection |
| `search_memories` | Semantic search with multi-hop query decomposition |
| `search_advanced` | Structured query syntax (type:, tag:, confidence:>, dates) |
| `get_context` | Retrieve with graph-expanded context (related memories attached) |
| `get_memory` | Get a specific memory by ID |
| `list_memories` | List memories with optional type filter |
| `update_memory` | Update memory content |
| `delete_memory` | Delete a memory |
| `consolidate` | Trigger episodic-to-semantic consolidation |
| `get_stats` | Memory system statistics and health |
| `find_by_tags` | Hierarchical tag search |
| `get_graph` | Export entity-relationship knowledge graph |

## Storage backends (configure in `neuromem.yaml`)

| Backend | Best for | `database.type` | `vector_store.type` |
|---------|----------|-----------------|---------------------|
| In-Memory | Tests, throwaway dev | `memory` | `memory` |
| SQLite | Single-user local (default) | `sqlite` | `sqlite` |
| Qdrant | High-scale vector search | `sqlite`/`postgres` | `qdrant` |
| Postgres + pgvector | Production, multi-user service mode | `postgres` | `postgres` |

The wizard's recommended single-user combo is **Qdrant for vectors,
SQLite at `~/.neuromem/memory.db` for records.**

## Python SDK adapters

For Python apps that want to embed NeuroMem rather than call it over MCP,
the SDK ships native adapters under `neuromem.adapters.*`:

| Framework | Module | Pattern |
|---|---|---|
| LangChain | `neuromem.adapters.langchain` | `BaseChatMessageHistory` impl |
| LangGraph | `neuromem.adapters.langgraph` | Checkpointer-compatible store |
| CrewAI | `neuromem.adapters.crewai` | Long-term memory backend |
| AutoGen / ag2 | `neuromem.adapters.autogen` | `Memory` interface |
| DSPy | `neuromem.adapters.dspy` | Retriever + persistence |
| Haystack | `neuromem.adapters.haystack` | DocumentStore impl |
| Semantic Kernel | `neuromem.adapters.semantic_kernel` | `MemoryStoreBase` impl |
| LiteLLM | `neuromem.adapters.litellm` | Hook for chat completions |

Each is documented in `examples/integrations/`. Same `neuromem.yaml`
drives both the SDK adapters and the MCP server — no double config.
