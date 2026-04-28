import { NavLink, Route, Routes } from 'react-router-dom'
import clsx from 'clsx'
import Workspace from './routes/Workspace'
import Graph2D from './routes/Graph2D'
import Graph3D from './routes/Graph3D'
import RetrievalRuns from './routes/RetrievalRuns'
import Observations from './routes/Observations'
import BrainTelemetry from './routes/BrainTelemetry'
import MCPSetup from './routes/MCPSetup'

const NAV = [
  // Knowledge work — the Obsidian-like three-pane workspace.
  { to: '/', label: 'Workspace', end: true, group: 'work' },

  // Visualisations — different lenses on the same memory graph.
  { to: '/graph-2d', label: 'Graph (2D)', group: 'view' },
  { to: '/graph-3d', label: 'Brain (3D)', group: 'view' },

  // Operational dashboards — observe the SDK rather than edit memories.
  { to: '/retrievals', label: 'Retrieval runs', group: 'ops' },
  { to: '/observations', label: 'Observations', group: 'ops' },
  { to: '/brain', label: 'Brain telemetry', group: 'ops' },
  { to: '/mcp', label: 'MCP setup', group: 'ops' },
]

const GROUP_LABEL: Record<string, string> = {
  work: 'Knowledge',
  view: 'Visualise',
  ops: 'Operate',
}

export default function App() {
  const grouped = NAV.reduce<Record<string, typeof NAV>>((acc, n) => {
    ;(acc[n.group] ??= []).push(n)
    return acc
  }, {})

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 shrink-0 border-r border-zinc-800 bg-zinc-950 px-4 py-6">
        <div className="mb-6 select-none">
          <div className="text-lg font-bold tracking-tight text-zinc-100">NeuroMem</div>
          <div className="text-xs text-zinc-500">v0.4.0 · local</div>
        </div>
        <nav className="flex flex-col gap-3">
          {Object.entries(grouped).map(([group, items]) => (
            <div key={group} className="flex flex-col gap-1">
              <div className="px-3 text-[10px] uppercase tracking-wide text-zinc-600">
                {GROUP_LABEL[group]}
              </div>
              {items.map((n) => (
                <NavLink
                  key={n.to}
                  to={n.to}
                  end={n.end}
                  className={({ isActive }) =>
                    clsx(
                      'rounded px-3 py-1.5 text-sm transition',
                      isActive
                        ? 'bg-zinc-800 text-zinc-50'
                        : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200',
                    )
                  }
                >
                  {n.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Workspace />} />
          <Route path="/graph-2d" element={<Graph2D />} />
          <Route path="/graph-3d" element={<Graph3D />} />
          <Route path="/retrievals" element={<RetrievalRuns />} />
          <Route path="/observations" element={<Observations />} />
          <Route path="/brain" element={<BrainTelemetry />} />
          <Route path="/mcp" element={<MCPSetup />} />
        </Routes>
      </main>
    </div>
  )
}
