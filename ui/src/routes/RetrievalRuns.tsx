import { useEffect, useState } from 'react'
import useSWR from 'swr'
import clsx from 'clsx'
import { api, type RetrievalRun, type RetrievalStage } from '@/lib/api'

const STATUS_COLOR: Record<string, string> = {
  completed: 'text-emerald-400',
  errored: 'text-rose-400',
  fallback: 'text-amber-400',
  running: 'text-zinc-400',
}

/**
 * Inngest-style timeline of every ``retrieve()`` call. Each row is one
 * run; click for the per-stage trace. Subscribes to /api/retrievals/stream
 * via SSE so live runs append in real time.
 */
export default function RetrievalRuns() {
  const { data, mutate } = useSWR('/retrievals', () => api.retrievals(200), {
    refreshInterval: 5000,
  })
  const [selected, setSelected] = useState<RetrievalRun | null>(null)

  useEffect(() => {
    const es = new EventSource('/api/retrievals/stream')
    es.addEventListener('run', () => mutate())
    return () => es.close()
  }, [mutate])

  return (
    <div className="grid h-screen grid-cols-[1fr_540px]">
      <div className="overflow-hidden border-r border-zinc-800">
        <header className="border-b border-zinc-800 px-6 py-3">
          <h1 className="text-sm font-semibold text-zinc-100">Retrieval runs</h1>
          <div className="text-xs text-zinc-500">
            {data?.count ?? 0} captured · live SSE stream
          </div>
        </header>
        <ul className="overflow-auto" style={{ height: 'calc(100vh - 65px)' }}>
          {(data?.runs ?? []).map((r) => (
            <li
              key={r.id}
              onClick={() => setSelected(r)}
              className={clsx(
                'cursor-pointer border-b border-zinc-900 px-6 py-3 hover:bg-zinc-900',
                selected?.id === r.id && 'bg-zinc-900',
              )}
            >
              <div className="flex items-center gap-3 text-xs">
                <span className={STATUS_COLOR[r.status] ?? 'text-zinc-400'}>
                  {r.status}
                </span>
                <span className="text-zinc-500">
                  {r.elapsed_ms ? `${r.elapsed_ms.toFixed(1)} ms` : '—'}
                </span>
                <span className="text-zinc-500">k={r.k}</span>
                <span className="text-zinc-500">{r.task_type}</span>
              </div>
              <div className="mt-1 text-sm text-zinc-200 line-clamp-1">{r.query}</div>
            </li>
          ))}
        </ul>
      </div>
      <aside className="overflow-auto bg-zinc-950 p-6">
        {selected ? (
          <RunDetail run={selected} />
        ) : (
          <div className="text-sm text-zinc-500">Select a run.</div>
        )}
      </aside>
    </div>
  )
}

function RunDetail({ run }: { run: RetrievalRun }) {
  return (
    <div>
      <div className="mb-3 text-xs text-zinc-500">{run.id}</div>
      <h2 className="mb-3 text-sm leading-relaxed text-zinc-100">{run.query}</h2>
      <dl className="grid grid-cols-[110px_1fr] gap-y-1 text-xs">
        <dt className="text-zinc-500">status</dt>
        <dd className={STATUS_COLOR[run.status]}>{run.status}</dd>
        <dt className="text-zinc-500">elapsed</dt>
        <dd>{run.elapsed_ms?.toFixed(1)} ms</dd>
        <dt className="text-zinc-500">confidence</dt>
        <dd>{run.confidence.toFixed(3)}</dd>
        <dt className="text-zinc-500">abstained</dt>
        <dd>{run.abstained ? 'yes' : 'no'}</dd>
      </dl>

      <h3 className="mt-6 mb-2 text-xs uppercase tracking-wide text-zinc-500">
        Stages ({run.stages.length})
      </h3>
      <ol className="space-y-2">
        {run.stages.map((s, i) => (
          <StageRow key={i} stage={s} />
        ))}
      </ol>

      <h3 className="mt-6 mb-2 text-xs uppercase tracking-wide text-zinc-500">
        Final results
      </h3>
      <pre className="overflow-auto rounded bg-zinc-900 p-3 text-[11px] text-zinc-300">
        {JSON.stringify(run.final_results, null, 2)}
      </pre>
    </div>
  )
}

function StageRow({ stage }: { stage: RetrievalStage }) {
  const [open, setOpen] = useState(false)
  return (
    <li className="rounded border border-zinc-800 bg-zinc-950">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-3 py-2 text-left text-xs hover:bg-zinc-900"
      >
        <span className="font-mono text-zinc-200">{stage.name}</span>
        <span className="text-zinc-500">
          {stage.candidate_count} cands · {stage.elapsed_ms.toFixed(1)} ms
        </span>
      </button>
      {open && (
        <div className="border-t border-zinc-800 px-3 py-2">
          <pre className="overflow-auto text-[11px] text-zinc-300">
            {JSON.stringify(
              { top_candidates: stage.top_candidates, notes: stage.notes },
              null,
              2,
            )}
          </pre>
        </div>
      )}
    </li>
  )
}
