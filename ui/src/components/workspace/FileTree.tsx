import { useMemo, useState } from 'react'
import useSWR from 'swr'
import clsx from 'clsx'
import { api, type MemoryRecord } from '@/lib/api'

/**
 * Obsidian-like vault tree — three top-level groups:
 *   - Knowledge Base    (memories with metadata.source_id, grouped by source)
 *   - Conversations     (organic episodic memories)
 *   - Working Memory    (PFC slots — read from /api/brain/state)
 *
 * Drop a file anywhere in the workspace and it appears under
 * Knowledge Base as a new collapsible group.
 */

interface Props {
  activeId: string | null
  onOpen: (id: string) => void
}

interface KbGroup {
  source_id: string
  title: string
  chunks: MemoryRecord[]
  rootId: string | null
}

export default function FileTree({ activeId, onOpen }: Props) {
  const { data: memData } = useSWR('/memories', () => api.listMemories(500), {
    refreshInterval: 5000,
  })
  const { data: brainData } = useSWR('/brain', api.brain, { refreshInterval: 1500 })

  const grouped = useMemo(() => groupMemories(memData?.items ?? []), [memData])
  const wmIds = brainData?.working_memory_ids ?? []

  return (
    <div className="flex h-full flex-col gap-1 overflow-auto p-3 text-sm">
      <Group title="Knowledge Base" defaultOpen count={grouped.kb.length}>
        {grouped.kb.map((g) => (
          <KbGroupItem key={g.source_id} group={g} activeId={activeId} onOpen={onOpen} />
        ))}
        {grouped.kb.length === 0 && (
          <div className="px-3 py-2 text-xs text-zinc-500 italic">
            Drop a PDF / DOCX / XLSX / MD here
          </div>
        )}
      </Group>

      <Group
        title="Conversations"
        defaultOpen
        count={grouped.conversations.length}
      >
        {grouped.conversations.slice(0, 100).map((m) => (
          <Leaf key={m.id} m={m} activeId={activeId} onOpen={onOpen} />
        ))}
      </Group>

      <Group title="Working Memory (PFC)" count={wmIds.length}>
        {wmIds.length === 0 ? (
          <div className="px-3 py-2 text-xs text-zinc-500 italic">
            empty — slot capacity 4
          </div>
        ) : (
          wmIds.map((id) => (
            <button
              key={id}
              onClick={() => onOpen(id)}
              className="w-full truncate px-3 py-1 text-left text-xs text-zinc-300 hover:bg-zinc-900"
            >
              ⏵ {id.slice(0, 8)}
            </button>
          ))
        )}
      </Group>
    </div>
  )
}

function Group({
  title,
  defaultOpen = false,
  count,
  children,
}: {
  title: string
  defaultOpen?: boolean
  count?: number
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="mb-1">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between rounded px-2 py-1 text-[11px] uppercase tracking-wide text-zinc-400 hover:bg-zinc-900"
      >
        <span>
          {open ? '▾' : '▸'} {title}
        </span>
        {typeof count === 'number' && (
          <span className="text-zinc-600">{count}</span>
        )}
      </button>
      {open && <div className="ml-1">{children}</div>}
    </div>
  )
}

function KbGroupItem({
  group,
  activeId,
  onOpen,
}: {
  group: KbGroup
  activeId: string | null
  onOpen: (id: string) => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between rounded px-2 py-1 text-xs text-zinc-200 hover:bg-zinc-900"
      >
        <span className="truncate">
          {open ? '📂' : '📁'} {group.title}
        </span>
        <span className="text-[10px] text-zinc-500">{group.chunks.length}</span>
      </button>
      {open && (
        <div className="ml-3 border-l border-zinc-800 pl-2">
          {group.rootId && (
            <Leaf
              m={
                {
                  id: group.rootId,
                  content: '[document root]',
                  memory_type: 'semantic',
                } as MemoryRecord
              }
              activeId={activeId}
              onOpen={onOpen}
              icon="📄"
            />
          )}
          {group.chunks.map((m) => (
            <Leaf key={m.id} m={m} activeId={activeId} onOpen={onOpen} icon="·" />
          ))}
        </div>
      )}
    </div>
  )
}

function Leaf({
  m,
  activeId,
  onOpen,
  icon = '·',
}: {
  m: MemoryRecord
  activeId: string | null
  onOpen: (id: string) => void
  icon?: string
}) {
  return (
    <button
      key={m.id}
      onClick={() => onOpen(m.id)}
      className={clsx(
        'w-full truncate rounded px-2 py-1 text-left text-xs hover:bg-zinc-900',
        activeId === m.id ? 'bg-zinc-900 text-zinc-100' : 'text-zinc-300',
      )}
    >
      <span className="text-zinc-600">{icon}</span>{' '}
      {m.content.slice(0, 50) || m.id}
    </button>
  )
}

function groupMemories(items: MemoryRecord[]): {
  kb: KbGroup[]
  conversations: MemoryRecord[]
} {
  const kbMap = new Map<string, KbGroup>()
  const conversations: MemoryRecord[] = []

  for (const m of items) {
    const sourceId =
      typeof m.metadata?.source_id === 'string' ? m.metadata.source_id : null
    if (!sourceId) {
      conversations.push(m)
      continue
    }
    let g = kbMap.get(sourceId)
    if (!g) {
      g = {
        source_id: sourceId,
        title: pickTitle(m),
        chunks: [],
        rootId: null,
      }
      kbMap.set(sourceId, g)
    }
    if (m.metadata?.kind === 'document_root') {
      g.rootId = m.id
      g.title = pickTitle(m)
    } else {
      g.chunks.push(m)
    }
  }

  const kb = [...kbMap.values()].sort((a, b) => a.title.localeCompare(b.title))
  return { kb, conversations }
}

function pickTitle(m: MemoryRecord): string {
  const raw = (m.metadata?.source_path as string) ?? ''
  if (raw) return raw.split('/').pop() ?? raw
  return m.content.replace(/^\[document\]\s*/, '').slice(0, 40) || m.id
}
