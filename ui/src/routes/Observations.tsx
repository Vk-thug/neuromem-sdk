import { useEffect } from 'react'
import useSWR from 'swr'
import { api } from '@/lib/api'

export default function Observations() {
  const { data, mutate } = useSWR('/observations', () => api.observations(300), {
    refreshInterval: 5000,
  })

  useEffect(() => {
    const es = new EventSource('/api/observations/stream')
    es.addEventListener('observation', () => mutate())
    return () => es.close()
  }, [mutate])

  return (
    <div className="h-screen overflow-hidden">
      <header className="border-b border-zinc-800 px-6 py-3">
        <h1 className="text-sm font-semibold text-zinc-100">Observation feed</h1>
        <div className="text-xs text-zinc-500">
          {data?.count ?? 0} events · live SSE stream
        </div>
      </header>
      <ul className="overflow-auto" style={{ height: 'calc(100vh - 65px)' }}>
        {(data?.events ?? []).map((e) => (
          <li key={e.id} className="border-b border-zinc-900 px-6 py-3">
            <div className="flex flex-wrap items-center gap-3 text-[11px]">
              <span className="text-zinc-500">
                {new Date(e.timestamp * 1000).toLocaleTimeString()}
              </span>
              {e.template ? (
                <span className="rounded bg-zinc-800 px-2 py-0.5 text-zinc-300">
                  {e.template}
                </span>
              ) : null}
              {typeof e.salience === 'number' ? (
                <span className="text-zinc-500">salience {e.salience.toFixed(2)}</span>
              ) : null}
              {typeof e.emotional_weight === 'number' && e.emotional_weight > 0 ? (
                <span className="text-rose-300">
                  emotion {e.emotional_weight.toFixed(2)}
                </span>
              ) : null}
              {e.flashbulb ? <span className="text-rose-400">⚡ flashbulb</span> : null}
              {e.entities.length ? (
                <span className="text-zinc-500">entities: {e.entities.join(', ')}</span>
              ) : null}
            </div>
            <div className="mt-1 grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-[10px] uppercase tracking-wide text-zinc-500">user</div>
                <div className="text-zinc-200">{e.user_text}</div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wide text-zinc-500">
                  assistant
                </div>
                <div className="text-zinc-300">{e.assistant_text}</div>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
