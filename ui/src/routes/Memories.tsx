import { useState } from 'react'
import useSWR from 'swr'
import { api, type MemoryRecord } from '../lib/api.ts'

const TYPE_PILL: Record<string, string> = {
  episodic: 'bg-blue-900/40 text-blue-300',
  semantic: 'bg-amber-900/40 text-amber-300',
  procedural: 'bg-emerald-900/40 text-emerald-300',
  affective: 'bg-rose-900/40 text-rose-300',
  working: 'bg-zinc-700 text-zinc-200',
}

export default function Memories() {
  const { data, error, isLoading } = useSWR('/memories', () => api.listMemories(200))
  const [selected, setSelected] = useState<MemoryRecord | null>(null)
  const [filter, setFilter] = useState('')

  if (error) return <div className="p-8 text-rose-400">Failed: {String(error)}</div>
  if (isLoading) return <div className="p-8 text-zinc-400">Loading…</div>

  const items = (data?.items ?? []).filter((m) =>
    filter ? m.content.toLowerCase().includes(filter.toLowerCase()) : true,
  )

  return (
    <div className="grid h-screen grid-cols-[1fr_420px]">
      <div className="overflow-hidden border-r border-zinc-800">
        <div className="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
          <div>
            <div className="text-sm text-zinc-500">{items.length} memories</div>
          </div>
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter…"
            className="w-56 rounded border border-zinc-700 bg-zinc-900 px-3 py-1 text-sm"
          />
        </div>
        <ul className="overflow-auto" style={{ height: 'calc(100vh - 65px)' }}>
          {items.map((m) => (
            <li
              key={m.id}
              onClick={() => setSelected(m)}
              className={`cursor-pointer border-b border-zinc-900 px-6 py-3 hover:bg-zinc-900 ${
                selected?.id === m.id ? 'bg-zinc-900' : ''
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`rounded px-2 py-0.5 text-[10px] uppercase ${
                    TYPE_PILL[m.memory_type] ?? 'bg-zinc-800 text-zinc-300'
                  }`}
                >
                  {m.memory_type}
                </span>
                <span className="text-xs text-zinc-500">salience {m.salience.toFixed(2)}</span>
                {m.metadata?.flashbulb ? (
                  <span className="text-xs text-rose-400">⚡ flashbulb</span>
                ) : null}
              </div>
              <div className="mt-1 line-clamp-2 text-sm text-zinc-200">{m.content}</div>
            </li>
          ))}
        </ul>
      </div>
      <aside className="overflow-auto bg-zinc-950 p-6">
        {selected ? (
          <Detail item={selected} />
        ) : (
          <div className="text-sm text-zinc-500">Select a memory.</div>
        )}
      </aside>
    </div>
  )
}

function Detail({ item }: { item: MemoryRecord }) {
  const { data: explanation } = useSWR(['explain', item.id], () => api.explainMemory(item.id))
  return (
    <div>
      <div className="mb-3 text-xs text-zinc-500">{item.id}</div>
      <h2 className="mb-2 font-mono text-sm leading-relaxed text-zinc-100">{item.content}</h2>
      <dl className="mt-4 grid grid-cols-[120px_1fr] gap-y-1 text-xs">
        <dt className="text-zinc-500">type</dt>
        <dd className="text-zinc-200">{item.memory_type}</dd>
        <dt className="text-zinc-500">salience</dt>
        <dd className="text-zinc-200">{item.salience.toFixed(3)}</dd>
        <dt className="text-zinc-500">confidence</dt>
        <dd className="text-zinc-200">{item.confidence.toFixed(3)}</dd>
        <dt className="text-zinc-500">reinforcement</dt>
        <dd className="text-zinc-200">{item.reinforcement}</dd>
        <dt className="text-zinc-500">created</dt>
        <dd className="text-zinc-200">{item.created_at}</dd>
        <dt className="text-zinc-500">tags</dt>
        <dd className="text-zinc-200">{item.tags?.join(', ') || '—'}</dd>
      </dl>
      <h3 className="mt-6 mb-2 text-xs uppercase tracking-wide text-zinc-500">explain()</h3>
      <pre className="overflow-auto rounded bg-zinc-900 p-3 text-[11px] text-zinc-300">
        {JSON.stringify(explanation ?? {}, null, 2)}
      </pre>
    </div>
  )
}
