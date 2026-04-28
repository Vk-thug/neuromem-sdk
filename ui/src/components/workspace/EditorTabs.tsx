import clsx from 'clsx'

interface TabMeta {
  id: string
  label: string
}

interface Props {
  tabs: TabMeta[]
  activeId: string | null
  onActivate: (id: string) => void
  onClose: (id: string) => void
  onNew: () => void
}

/**
 * Browser-style tab strip. Shows a soft warning if open tab count
 * exceeds Cowan's working-memory capacity (4) — an honest UX nudge to
 * the user that they're past the brain's natural focus limit.
 */
export default function EditorTabs({ tabs, activeId, onActivate, onClose, onNew }: Props) {
  const exceedsWm = tabs.length > 4
  return (
    <div className="flex items-center gap-1 overflow-x-auto border-b border-zinc-800 bg-zinc-950 px-2 py-1.5">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onActivate(t.id)}
          className={clsx(
            'group flex max-w-[220px] items-center gap-2 rounded-t px-3 py-1 text-xs',
            activeId === t.id
              ? 'bg-zinc-900 text-zinc-100'
              : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200',
          )}
        >
          <span className="truncate">{t.label || t.id.slice(0, 8)}</span>
          <span
            role="button"
            onClick={(e) => {
              e.stopPropagation()
              onClose(t.id)
            }}
            className="opacity-0 transition group-hover:opacity-100 hover:text-rose-400"
          >
            ×
          </span>
        </button>
      ))}
      <button
        type="button"
        onClick={onNew}
        className="rounded px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-900 hover:text-zinc-200"
      >
        +
      </button>
      {exceedsWm && (
        <span
          className="ml-2 rounded bg-amber-900/30 px-2 py-0.5 text-[10px] text-amber-300"
          title="Open tabs exceed Cowan's working-memory limit (4)"
        >
          {tabs.length} / 4 WM
        </span>
      )}
    </div>
  )
}
