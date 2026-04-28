import useSWR from 'swr'
import { api } from '@/lib/api'

export default function BrainTelemetry() {
  const { data } = useSWR('/brain', api.brain, { refreshInterval: 1000 })

  if (!data) return <div className="p-8 text-zinc-400">Loading…</div>
  if (!data.enabled) {
    return (
      <div className="p-8">
        <h1 className="mb-3 text-sm font-semibold text-zinc-100">Brain telemetry</h1>
        <div className="rounded border border-zinc-800 bg-zinc-900 p-6 text-zinc-400">
          The brain layer is disabled. Set{' '}
          <code className="rounded bg-zinc-800 px-1">brain.enabled: true</code> in your{' '}
          <code className="rounded bg-zinc-800 px-1">neuromem.yaml</code> to enable
          working memory, TD learning, schema integration, and amygdala tagging.
        </div>
      </div>
    )
  }

  const wm = data.working_memory_ids ?? []
  return (
    <div className="grid h-screen grid-cols-3 gap-6 p-6 overflow-auto">
      <Section title="Working memory (Cowan 4)">
        <div className="grid grid-cols-2 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className={`rounded border p-3 text-xs ${
                wm[i]
                  ? 'border-zinc-100/40 bg-zinc-100/10'
                  : 'border-zinc-800 bg-zinc-900 text-zinc-600'
              }`}
            >
              <div className="text-[10px] uppercase tracking-wide text-zinc-500">
                slot {i + 1}
              </div>
              <div className="font-mono">{wm[i] ?? 'empty'}</div>
            </div>
          ))}
        </div>
      </Section>
      <Section title="TD values (basal ganglia)">
        <pre className="overflow-auto text-[11px] text-zinc-300">
          {JSON.stringify(data.td_values ?? {}, null, 2)}
        </pre>
      </Section>
      <Section title="Schema centroids (neocortex)">
        <pre className="overflow-auto text-[11px] text-zinc-300">
          {JSON.stringify(data.schemas ?? {}, null, 2)}
        </pre>
      </Section>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded border border-zinc-800 bg-zinc-950 p-4">
      <h2 className="mb-3 text-xs uppercase tracking-wide text-zinc-500">{title}</h2>
      {children}
    </section>
  )
}
