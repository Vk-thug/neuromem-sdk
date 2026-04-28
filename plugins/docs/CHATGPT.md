# Connect NeuroMem to ChatGPT (web)

ChatGPT exposes MCP via the **Connectors** panel (also surfaced as
"Custom GPT MCP" for tailored GPTs). This guide connects your local
NeuroMem MCP to ChatGPT over HTTPS.

## 1. Install NeuroMem and a tunnel binary

```bash
pip install 'neuromem-sdk[mcp]'
brew install cloudflared
```

## 2. Start the public MCP server

```bash
python -m neuromem.mcp --transport http --port 7799 --public
```

Look for the **ChatGPT** section in the output:

```
─── ChatGPT (web) ─────────────────────────────────
Settings → Connectors → MCP → Add server. Paste:
{
  "name": "NeuroMem",
  "type": "mcp",
  "url": "https://random-words-1234.trycloudflare.com",
  "auth": "none",
  "description": "NeuroMem brain-inspired memory for AI agents"
}
```

## 3. Add the connector in ChatGPT

1. Open https://chatgpt.com.
2. Click your profile → **Settings** → **Connectors** → **MCP**.
3. Click **Add server**.
4. Paste the JSON blob from step 2.
5. Save. ChatGPT introspects the server and lists the 12 NeuroMem tools.

For a Custom GPT:
1. Edit the GPT → **Configure** → **Knowledge** → **Connectors**.
2. Enable the **NeuroMem** connector.
3. The Custom GPT can now call NeuroMem tools inside its action graph.

## 4. Verify

In a new chat:

> Search my NeuroMem memories for anything about Python preferences.

ChatGPT calls `neuromem.search_memories` and returns the matching items.

## Notes

- **`auth: "none"`** in the connector blob is correct for the public
  tunnel default. NeuroMem does not yet ship a tool-level auth layer.
  For sensitive memory pools, use a private cloudflared tunnel and
  configure ChatGPT's connector with a bearer token at the cloudflared
  layer.
- The connector URL is account-scoped: deletion in the ChatGPT
  Connectors panel removes only the connector record, not your local
  data.
- See [`CLAUDE_AI_WEB.md`](./CLAUDE_AI_WEB.md) for security notes.
