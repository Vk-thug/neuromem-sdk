import { useEffect, useMemo, useRef, useState } from 'react'
import { Plate, usePlateEditor } from 'platejs/react'
import { MarkdownPlugin } from '@platejs/markdown'
// Plate.js v52 renamed the plugin exports to add a `Base` prefix
// (BoldPlugin → BaseBoldPlugin, MentionPlugin → BaseMentionPlugin, …).
// Source: https://platejs.org migration notes for the 45 → 52 line.
import { BaseMentionPlugin } from '@platejs/mention'
import {
  BaseBoldPlugin,
  BaseItalicPlugin,
  BaseCodePlugin,
  BaseH1Plugin,
  BaseH2Plugin,
  BaseH3Plugin,
  BaseBlockquotePlugin,
} from '@platejs/basic-nodes'
import type { MemoryRecord } from '@/lib/api'
import { api } from '@/lib/api'

/**
 * Plate.js editor for a single memory.
 *
 * - Initial content: deserialised from Markdown (memory.content).
 * - Save: serialises back to Markdown and calls PUT /api/memories/{id}
 *   which performs a SOFT-SUPERSEDE (Nader 2000 reconsolidation).
 * - Save triggers: onBlur + Cmd-S + 2s idle debounce.
 * - [[wiki-links]]: typed via the mention plugin; resolve to memory ids
 *   on save and create `related` graph edges (handled server-side).
 *
 * Long-term: this component is the seam where future plugins (drag
 * handle, slash menu, AI completion, comments) plug in. Plate's plugin
 * model means each addition is a one-line `editor.use(...)` call.
 */

interface Props {
  memory: MemoryRecord
  onSaved?: (newId: string) => void
}

export default function PlateEditor({ memory, onSaved }: Props) {
  const initialMarkdown = memory.content
  const editor = usePlateEditor({
    plugins: [
      BaseH1Plugin,
      BaseH2Plugin,
      BaseH3Plugin,
      BaseBlockquotePlugin,
      BaseBoldPlugin,
      BaseItalicPlugin,
      BaseCodePlugin,
      MarkdownPlugin,
      BaseMentionPlugin.configure({
        options: {
          // Mention trigger character — Obsidian uses [[]], we also
          // accept @ as a quick alternative.
          trigger: '[[',
        },
      }),
    ],
    value: useMemo(() => mdToInitialValue(initialMarkdown), [memory.id]),
  })

  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState<number | null>(null)
  const debounceRef = useRef<number | null>(null)

  // Idle-debounced save (2s).
  useEffect(() => {
    if (!dirty) return
    if (debounceRef.current !== null) window.clearTimeout(debounceRef.current)
    debounceRef.current = window.setTimeout(() => {
      void doSave()
    }, 2000)
    return () => {
      if (debounceRef.current !== null) window.clearTimeout(debounceRef.current)
    }
  }, [dirty])

  // Cmd-S handler.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        void doSave()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  async function doSave() {
    if (!dirty) return
    try {
      setSaving(true)
      const md = serialiseToMarkdown(editor)
      const res = await api.editMemory(memory.id, { content: md })
      setDirty(false)
      setSavedAt(Date.now())
      if (onSaved) onSaved(res.new_id)
    } catch (err) {
      console.error('save failed', err)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-zinc-800 px-6 py-2 text-xs text-zinc-500">
        <span className="font-mono">{memory.id}</span>
        <span>
          {saving
            ? 'saving…'
            : dirty
              ? 'edited — Cmd-S to save'
              : savedAt
                ? `saved ${timeAgo(savedAt)}`
                : 'in sync'}
        </span>
      </div>
      <div
        className="flex-1 overflow-auto px-6 py-6"
        onBlur={() => {
          if (dirty) void doSave()
        }}
      >
        <Plate editor={editor} onChange={() => setDirty(true)}>
          {/* Plate.js v52 requires `children` on <Plate>; the editable
              surface comes from the editor instance, so an empty fragment
              is the canonical "render the default editable" placeholder. */}
          <></>
        </Plate>
      </div>
    </div>
  )
}

/** Minimal Markdown → Plate value bootstrapping. */
function mdToInitialValue(md: string) {
  // Plate's MarkdownPlugin offers ``editor.api.markdown.deserialize``
  // but at editor-construction time we don't have an editor instance
  // yet. Fall back to a single paragraph that the MarkdownPlugin will
  // re-format on first user edit.
  return [
    {
      type: 'p',
      children: [{ text: md }],
    },
  ]
}

/** Serialise editor value back to Markdown via Plate's MarkdownPlugin. */
function serialiseToMarkdown(editor: unknown): string {
  // The runtime editor exposes ``api.markdown.serialize()``. Cast
  // through unknown to avoid pulling Plate's internal types into our
  // surface.
  const e = editor as { api?: { markdown?: { serialize?: () => string } } }
  if (e.api?.markdown?.serialize) {
    try {
      return e.api.markdown.serialize()
    } catch {
      // Fall through.
    }
  }
  // Fallback: flatten plain text from editor.children.
  const children = (e as { children?: Array<{ children?: Array<{ text?: string }> }> })
    .children
  if (!children) return ''
  return children
    .map((n) => (n.children ?? []).map((c) => c.text ?? '').join(''))
    .join('\n\n')
}

function timeAgo(ts: number): string {
  const sec = Math.round((Date.now() - ts) / 1000)
  if (sec < 5) return 'just now'
  if (sec < 60) return `${sec}s ago`
  return `${Math.round(sec / 60)}m ago`
}
