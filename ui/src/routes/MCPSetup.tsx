import useSWR from 'swr'
import { useState } from 'react'
import { api } from '@/lib/api'

const CLIENT_LABELS: Record<string, string> = {
  claude_ai: 'Claude.ai (web)',
  gemini_chat: 'Gemini chat (web)',
  chatgpt: 'ChatGPT (web)',
  mcp_json: 'Cursor / Antigravity / VS Code MCP',
  claude_code: 'Claude Code (stdio)',
}

export default function MCPSetup() {
  const { data } = useSWR('/mcp-config', api.mcpConfig, { refreshInterval: 5000 })
  const [copied, setCopied] = useState<string | null>(null)

  if (!data) return <div className="p-8 text-zinc-400">Loading…</div>

  return (
    <div className="overflow-auto p-6">
      <header className="mb-4">
        <h1 className="text-sm font-semibold text-zinc-100">MCP setup</h1>
        <div className="text-xs text-zinc-500">
          {data.tunnel
            ? `Tunnel live · config saved at ${data.public_url_path}`
            : data.hint}
        </div>
      </header>

      {!data.tunnel && (
        <div className="mb-6 rounded border border-amber-900/60 bg-amber-950/30 p-4 text-xs text-amber-200">
          To enable web-chat clients (Claude.ai / Gemini / ChatGPT), run:
          <pre className="mt-2 rounded bg-zinc-900 p-2 font-mono text-amber-200">
            python -m neuromem.mcp --transport http --port 7799 --public
          </pre>
          The tunnel will write a JSON config and this panel will refresh
          automatically.
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        {Object.entries(data.blobs).map(([client, blob]) => (
          <div
            key={client}
            className="rounded border border-zinc-800 bg-zinc-950 p-4"
          >
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-zinc-100">
                {CLIENT_LABELS[client] ?? client}
              </h2>
              <button
                type="button"
                onClick={() => {
                  void navigator.clipboard.writeText(JSON.stringify(blob, null, 2))
                  setCopied(client)
                  window.setTimeout(() => setCopied(null), 1500)
                }}
                className="rounded bg-zinc-800 px-2 py-1 text-[11px] text-zinc-300 hover:bg-zinc-700"
              >
                {copied === client ? 'copied!' : 'copy JSON'}
              </button>
            </div>
            <pre className="overflow-auto rounded bg-zinc-900 p-3 text-[11px] text-zinc-300">
              {JSON.stringify(blob, null, 2)}
            </pre>
          </div>
        ))}
      </div>
    </div>
  )
}
