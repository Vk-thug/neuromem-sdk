import { useCallback, useEffect, useMemo, useState } from 'react'
import useSWR from 'swr'
import FileTree from '@/components/workspace/FileTree'
import EditorTabs from '@/components/workspace/EditorTabs'
import PlateEditor from '@/components/workspace/PlateEditor'
import BacklinksPanel from '@/components/workspace/BacklinksPanel'
import IngestOverlay from '@/components/workspace/IngestOverlay'
import { api, type MemoryRecord } from '../lib/api'
import { loadTabs, saveTabs } from '../lib/state/tabs'

/**
 * Three-pane Obsidian-like workspace:
 *
 *   FileTree (left)  ║  Tabs + Editor (centre)  ║  Backlinks (right)
 *
 * The full workspace is wrapped in IngestOverlay — drag a file
 * anywhere on the page to upload into the KB.
 */
export default function Workspace() {
  const { data: health } = useSWR('/health', api.health, { refreshInterval: 5000 })
  const userId = (health?.user_id as string | undefined) ?? 'default'

  const initial = useMemo(() => loadTabs(userId), [userId])
  const [openIds, setOpenIds] = useState<string[]>(initial.open)
  const [activeId, setActiveId] = useState<string | null>(initial.active)

  useEffect(() => {
    saveTabs(userId, { open: openIds, active: activeId })
  }, [userId, openIds, activeId])

  const openMemory = useCallback((id: string) => {
    setOpenIds((prev) => (prev.includes(id) ? prev : [...prev, id]))
    setActiveId(id)
  }, [])

  const closeTab = useCallback(
    (id: string) => {
      setOpenIds((prev) => {
        const next = prev.filter((p) => p !== id)
        setActiveId((active) => {
          if (active !== id) return active
          return next[next.length - 1] ?? null
        })
        return next
      })
    },
    [],
  )

  const newMemory = useCallback(async () => {
    const content = window.prompt('New memory content:')
    if (!content) return
    await api.addMemory({ content })
    // The list will refresh on its 5s SWR cycle; for snappy UX, we
    // could mutate the SWR cache here — keep it simple in v0.4.0.
  }, [])

  return (
    <>
      <IngestOverlay />
      <div
        className="grid h-screen"
        style={{ gridTemplateColumns: '260px 1fr 320px' }}
      >
        <aside className="overflow-hidden border-r border-zinc-800 bg-zinc-950">
          <FileTree activeId={activeId} onOpen={openMemory} />
        </aside>
        <main className="flex min-w-0 flex-col bg-zinc-950">
          <EditorTabs
            tabs={openIds.map((id) => ({ id, label: id.slice(0, 12) }))}
            activeId={activeId}
            onActivate={setActiveId}
            onClose={closeTab}
            onNew={newMemory}
          />
          <div className="min-h-0 flex-1">
            {activeId ? (
              <ActiveEditor memoryId={activeId} onSaved={openMemory} />
            ) : (
              <EmptyState onNew={newMemory} />
            )}
          </div>
        </main>
        <aside className="overflow-hidden border-l border-zinc-800 bg-zinc-950">
          {activeId ? (
            <BacklinksPanel memoryId={activeId} onOpen={openMemory} />
          ) : (
            <div className="p-4 text-xs text-zinc-500">
              Backlinks appear here when you open a memory.
            </div>
          )}
        </aside>
      </div>
    </>
  )
}

function ActiveEditor({
  memoryId,
  onSaved,
}: {
  memoryId: string
  onSaved: (id: string) => void
}) {
  const { data, isLoading, error, mutate } = useSWR<MemoryRecord>(
    ['memory', memoryId],
    () => api.getMemory(memoryId),
  )
  if (error)
    return <div className="p-6 text-rose-400">{`Failed: ${String(error)}`}</div>
  if (isLoading || !data)
    return <div className="p-6 text-xs text-zinc-500">loading…</div>
  return (
    <PlateEditor
      memory={data}
      onSaved={(newId) => {
        // Soft-supersede creates a new id; open the new one and refresh.
        onSaved(newId)
        void mutate()
      }}
    />
  )
}

function EmptyState({ onNew }: { onNew: () => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-12 text-center">
      <div className="text-5xl">🧠</div>
      <div className="text-sm text-zinc-300">
        Open a memory from the file tree, or:
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onNew}
          className="rounded border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-200 hover:bg-zinc-800"
        >
          New memory
        </button>
        <span className="rounded border border-zinc-800 bg-zinc-950 px-3 py-1.5 text-xs text-zinc-500">
          or drop a PDF / DOCX / MD anywhere on this window
        </span>
      </div>
    </div>
  )
}
