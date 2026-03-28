# NeuroMem Integration Guide — All Platforms

NeuroMem's MCP server works with every major coding agent and AI platform.

## Prerequisites (all platforms)

1. Install NeuroMem SDK with MCP support:
   ```bash
   pip install neuromem-sdk[mcp]
   ```

2. Create a `neuromem.yaml` config file (or copy from `examples/neuromem.yaml`)

3. Set your OpenAI API key:
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

4. Verify the MCP server starts:
   ```bash
   python -m neuromem.mcp
   # Should start without errors (ctrl+C to stop)
   ```

---

## Platforms with Full Plugin Support

### Claude Code
See `plugins/claude-code/README.md` — full plugin with commands, agent, skill, and hooks.

```bash
cd plugins/claude-code && claude plugin install .
```

### OpenAI Codex CLI
See `plugins/codex-cli/README.md` — plugin with skill and MCP.

```bash
cp -r plugins/codex-cli ~/.agents/plugins/neuromem
```

### Gemini CLI
See `plugins/gemini-cli/README.md` — extension with TOML commands and context.

```bash
cd plugins/gemini-cli && gemini extensions link .
```

---

## Platforms with MCP-Only Support

These platforms support MCP natively. Add the NeuroMem server to their config:

### Cline (VS Code Extension)

Open Cline settings and add to MCP servers, or edit `cline_mcp_settings.json`:
```json
{
  "mcpServers": {
    "neuromem": {
      "command": "python",
      "args": ["-m", "neuromem.mcp"],
      "env": {
        "NEUROMEM_CONFIG": "./neuromem.yaml",
        "OPENAI_API_KEY": "your-key-here"
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
    "env": {
      "NEUROMEM_CONFIG": "./neuromem.yaml",
      "OPENAI_API_KEY": "your-key-here"
    }
  }
}
```

### Windsurf / Cascade

Add via Windsurf Settings > MCP Servers:
```json
{
  "neuromem": {
    "command": "python",
    "args": ["-m", "neuromem.mcp"],
    "env": {
      "NEUROMEM_CONFIG": "./neuromem.yaml",
      "OPENAI_API_KEY": "your-key-here"
    }
  }
}
```

### GitHub Copilot (Agent Mode)

Add to your repository's MCP config or VS Code settings:
```json
{
  "mcpServers": {
    "neuromem": {
      "command": "python",
      "args": ["-m", "neuromem.mcp"],
      "env": {
        "NEUROMEM_CONFIG": "./neuromem.yaml",
        "OPENAI_API_KEY": "your-key-here"
      }
    }
  }
}
```
Note: Copilot coding agent only supports MCP tools (not resources or prompts).

### Aider

Community MCP support via mcpm-aider or direct configuration. See Aider docs for current MCP integration status.

---

## Cloud AI Platforms (Remote HTTP)

For Claude.ai, ChatGPT, and Google AI Studio, run the MCP server in HTTP mode:

```bash
python -m neuromem.mcp --transport http --port 8000
```

This starts a Streamable HTTP server at `http://localhost:8000/mcp`.

For production, deploy behind HTTPS (e.g., with nginx, Caddy, or a cloud provider).

### Claude.ai

1. Go to Settings > Connectors > Add Custom Connector
2. Enter name: "NeuroMem"
3. Enter MCP server URL: `https://your-server.com/mcp`
4. Works on web, iOS, and Android

### ChatGPT

1. Go to Settings > Connectors > Advanced > Developer Mode
2. Add MCP server URL: `https://your-server.com/mcp`
3. The 12 NeuroMem tools will appear as available actions

### Google AI Studio

Use the Google Gen AI SDK to connect:
```python
from google import genai
client = genai.Client()
# Connect MCP server as tool provider
```

---

## Available MCP Tools

All platforms get access to these 12 tools:

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

## Storage Backends

Configure in `neuromem.yaml`:

| Backend | Best For | Config |
|---------|----------|--------|
| In-Memory | Development, testing | `type: memory` |
| SQLite | Single-user local | `type: sqlite` |
| PostgreSQL + pgvector | Production | `type: postgres` |
| Qdrant | High-scale vector search | `type: qdrant` |
