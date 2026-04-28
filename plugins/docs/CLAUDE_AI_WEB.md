# Connect NeuroMem to Claude.ai (web)

Claude.ai supports custom MCP integrations over HTTPS. This guide shows
how to expose your locally-running NeuroMem MCP server to Claude.ai
via Cloudflare Tunnel (preferred) or ngrok (fallback).

## 1. Install NeuroMem with the MCP extra

```bash
pip install 'neuromem-sdk[mcp]'
```

## 2. Install a tunnel binary (one-time)

NeuroMem supports two tunnel providers:

```bash
# Preferred — no signup required
brew install cloudflared              # macOS
winget install --id Cloudflare.cloudflared   # Windows
# Linux: https://pkg.cloudflare.com/index.html

# Or — ngrok fallback (requires free auth token)
brew install ngrok
ngrok config add-authtoken YOUR_TOKEN
```

## 3. Start the public MCP server

```bash
python -m neuromem.mcp --transport http --port 7799 --public
```

You'll see output like:

```
NeuroMem MCP tunnel is live at: https://random-words-1234.trycloudflare.com

─── Claude.ai (web) ────────────────────────────────────────
Settings → Integrations → Add custom MCP server. Paste:
{
  "name": "neuromem",
  "url": "https://random-words-1234.trycloudflare.com",
  "transport": "http",
  "description": "NeuroMem brain-inspired memory ..."
}
```

The same JSON is also written to `~/.neuromem/mcp-public.json`.

## 4. Connect Claude.ai

1. Open https://claude.ai.
2. Click your profile → **Settings** → **Integrations** → **MCP servers**.
3. Click **Add custom MCP server**.
4. Paste the URL from step 3 (`https://random-words-1234.trycloudflare.com`).
5. Save. Claude.ai introspects the server and shows the 12 NeuroMem tools.

## 5. Verify

In a new Claude.ai chat, ask:

> Use the neuromem MCP server to recall my preferences.

Claude.ai should call `neuromem.search_memories` with your query and
return results from your local NeuroMem instance.

## Notes

- **Tunnel URLs are public.** Anyone with the URL can call your local
  MCP server while the tunnel is live. NeuroMem currently has no
  per-tool authentication — treat the URL like a password and stop the
  server (`Ctrl+C`) when you're not using it.
- **The cloudflared free tier rotates URLs on every restart.** For a
  stable URL, configure a named cloudflared tunnel:
  https://developers.cloudflare.com/cloudflare-one/connections/connect-networks
- **Local storage is canonical.** All memories live on your machine in
  Qdrant (or the configured backend). The tunnel only carries MCP
  protocol traffic.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `cloudflared is not installed` | Run the install command from step 2. |
| `did not produce a public URL within 30.0s` | Check firewall; try `--tunnel-provider ngrok`. |
| Claude.ai says "MCP server unreachable" | Confirm `https://...trycloudflare.com` opens in a browser. |
| Tools list is empty | Ensure `NEUROMEM_USER_ID` is set in the shell that launched the server. |
