import useSWR from 'swr'
import { api } from '../../lib/api.ts'

/**
 * Right-pane "Linked mentions" view.
 *
 * Walks the ego-graph at depth 1 to surface incoming + outgoing edges,
 * grouped by link_type. Click any entry to open it in a new tab.
 *
 * Cognitive grounding: this is associative recall — partial cue (the
 * currently-open memory) → recalled neighbours via graph edges. The
 * incoming-edges list is "what other memories cite this one" (Obsidian's
 * "Linked mentions"). Outgoing edges are "what this memory cites".
 */

interface Props {
  memoryId: string
  onOpen: (id: string) => void
}

export default function BacklinksPanel({ memoryId, onOpen }: Props) {
  const { data } = useSWR(['ego', memoryId], () => api.egoGraph(memoryId, 1))
  if (!data) return <div className="p-3 text-xs text-zinc-500">loading…</div>

  const incoming = data.edges.filter((e) => e.target_id === memoryId)
  const outgoing = data.edges.filter((e) => e.source_id === memoryId)

  return (
    <div className="flex h-full flex-col gap-3 overflow-auto p-4 text-sm">
      <Section title="Incoming" count={incoming.length}>
        {incoming.length === 0 ? (
          <Empty>no backlinks yet</Empty>
        ) : (
          incoming.map((e, i) => (
            <LinkRow
              key={i}
              kind={e.link_type}
              label={data.nodes.find((n) => n.id === e.source_id)?.label ?? e.source_id}
              onClick={() => onOpen(e.source_id)}
            />
          ))
        )}
      </Section>
      <Section title="Outgoing" count={outgoing.length}>
        {outgoing.length === 0 ? (
          <Empty>no outgoing links</Empty>
        ) : (
          outgoing.map((e, i) => (
            <LinkRow
              key={i}
              kind={e.link_type}
              label={data.nodes.find((n) => n.id === e.target_id)?.label ?? e.target_id}
              onClick={() => onOpen(e.target_id)}
            />
          ))
        )}
      </Section>
    </div>
  )
}

function Section({
  title,
  count,
  children,
}: {
  title: string
  count: number
  children: React.ReactNode
}) {
  return (
    <section>
      <div className="mb-1 flex items-center justify-between text-[10px] uppercase tracking-wide text-zinc-500">
        <span>{title}</span>
        <span>{count}</span>
      </div>
      <div className="space-y-1">{children}</div>
    </section>
  )
}

const KIND_COLOR: Record<string, string> = {
  derived_from: 'text-zinc-400',
  related: 'text-blue-300',
  reinforces: 'text-emerald-300',
  contradicts: 'text-rose-300',
  supersedes: 'text-amber-300',
}

function LinkRow({
  kind,
  label,
  onClick,
}: {
  kind: string
  label: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-start gap-2 rounded px-2 py-1 text-left text-xs hover:bg-zinc-900"
    >
      <span className={`font-mono text-[10px] ${KIND_COLOR[kind] ?? 'text-zinc-500'}`}>
        {kind}
      </span>
      <span className="truncate text-zinc-200">{label}</span>
    </button>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="px-2 py-1 text-[11px] italic text-zinc-600">{children}</div>
}
