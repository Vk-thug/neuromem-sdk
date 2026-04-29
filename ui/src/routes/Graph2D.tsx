import useSWR from 'swr'
import CytoscapeGraph from '@/components/CytoscapeGraph'
import { api } from '../lib/api'

export default function Graph2D() {
  const { data, error, isLoading } = useSWR('/graph/2d', api.graph2d)

  if (error) return <div className="p-8 text-rose-400">Failed: {String(error)}</div>
  if (isLoading || !data) return <div className="p-8 text-zinc-400">Loading…</div>

  return (
    <div className="grid h-screen grid-rows-[auto_1fr]">
      <header className="flex items-center justify-between border-b border-zinc-800 px-6 py-3">
        <div>
          <h1 className="text-sm font-semibold text-zinc-100">Knowledge graph (2D)</h1>
          <div className="text-xs text-zinc-500">
            {data.node_count} nodes · {data.edge_count} edges · Obsidian-style force layout
          </div>
        </div>
        <Legend />
      </header>
      <div className="bg-zinc-950">
        <CytoscapeGraph data={data} />
      </div>
    </div>
  )
}

function Legend() {
  const items = [
    { label: 'Episodic', color: '#4f8cff' },
    { label: 'Semantic', color: '#f3b557' },
    { label: 'Procedural', color: '#5fc587' },
    { label: 'Affective', color: '#e74c5c' },
    { label: 'Working', color: '#dcdcdc' },
  ]
  return (
    <div className="flex gap-4 text-[11px]">
      {items.map((i) => (
        <div key={i.label} className="flex items-center gap-1">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: i.color }} />
          <span className="text-zinc-400">{i.label}</span>
        </div>
      ))}
    </div>
  )
}
