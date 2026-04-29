import useSWR from 'swr'
import ForceGraph3DView from '@/components/ForceGraph3D'
import { REGIONS } from '@/components/brain/regions'
import { api } from '../lib/api.ts'

export default function Graph3D() {
  const { data, error, isLoading } = useSWR('/graph/3d', api.graph3d)

  if (error) return <div className="p-8 text-rose-400">Failed: {String(error)}</div>
  if (isLoading || !data) return <div className="p-8 text-zinc-400">Loading…</div>

  return (
    <div className="grid h-screen grid-rows-[auto_1fr]">
      <header className="flex items-center justify-between border-b border-zinc-800 px-6 py-3">
        <div>
          <h1 className="text-sm font-semibold text-zinc-100">
            Brain mode (3D anatomical)
          </h1>
          <div className="text-xs text-zinc-500">
            {data.nodes.length} memories anchored to {data.regions.length} brain regions ·
            drag to rotate · scroll to zoom
          </div>
        </div>
        <BrainLegend />
      </header>
      <div className="relative bg-[#0a0a0c]">
        <ForceGraph3DView data={data} />
      </div>
    </div>
  )
}

function BrainLegend() {
  return (
    <div className="grid grid-cols-1 gap-y-1 text-[11px]">
      {(Object.keys(REGIONS) as (keyof typeof REGIONS)[]).map((r) => {
        const g = REGIONS[r]
        return (
          <div key={r} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: g.color }} />
            <span className="text-zinc-300">{g.label}</span>
          </div>
        )
      })}
    </div>
  )
}
