# Connect NeuroMem to Gemini chat (web)

Google's Gemini chat surfaces accept MCP servers as "connectors" via the
Workspace settings panel. This guide walks through exposing a local
NeuroMem MCP server to Gemini chat over HTTPS.

## 1. Install NeuroMem and a tunnel binary

```bash
pip install 'neuromem-sdk[mcp]'
brew install cloudflared          # macOS, see CLAUDE_AI_WEB.md for other platforms
```

## 2. Start the public MCP server

```bash
python -m neuromem.mcp --transport http --port 7799 --public
```

Look for the **Gemini chat** section in the output:

```
─── Gemini chat (web) ────────────────────────────────
Workspace settings → MCP connectors → Add. Paste:
{
  "mcpServers": {
    "neuromem": {
      "url": "https://random-words-1234.trycloudflare.com",
      "transport": "http"
    }
  }
}
```

## 3. Add the connector in Gemini

1. Open https://gemini.google.com.
2. Click the gear icon → **Workspace settings** → **MCP connectors**.
3. Click **Add connector**.
4. Paste the JSON blob from step 2.
5. Save. Gemini lists the 12 NeuroMem tools under your connectors.

## 4. Verify

Start a chat:

> List my NeuroMem memories tagged with `preference`.

Gemini should call `neuromem.find_by_tags` and surface the results.

## Notes

- The Gemini chat MCP integration is currently surfaced under the
  Workspace tier. If your account is consumer-only, the connectors
  panel may not be visible — use the Gemini CLI plugin
  (`plugins/gemini-cli/`) instead, which works for all account tiers
  via stdio MCP.
- See [`CLAUDE_AI_WEB.md`](./CLAUDE_AI_WEB.md) for security notes about
  exposing your local MCP via a public tunnel.
