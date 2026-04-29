/**
 * /settings — edit any config field anytime.
 *
 * Reads /api/config, lets the user edit groups (Mode, Model, Storage,
 * Memory, Async, Auth), shows a JSON diff before save, and badges
 * "restart required" fields with an amber pill after save.
 */

import { useEffect, useMemo, useState } from 'react'
import clsx from 'clsx'
import { api } from '../lib/api.ts'

type AnyDoc = Record<string, any>

function setPath(doc: AnyDoc, path: string[], value: unknown): AnyDoc {
  if (path.length === 0) return value as AnyDoc
  const [head, ...rest] = path
  return { ...doc, [head]: setPath((doc as AnyDoc)?.[head] ?? {}, rest, value) }
}

function diff(before: AnyDoc, after: AnyDoc, prefix = ''): { path: string; before: unknown; after: unknown }[] {
  const out: { path: string; before: unknown; after: unknown }[] = []
  const keys = new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})])
  for (const k of keys) {
    const b = (before as AnyDoc)?.[k]
    const a = (after as AnyDoc)?.[k]
    const path = prefix ? `${prefix}.${k}` : k
    const bothObj = b && a && typeof b === 'object' && typeof a === 'object' && !Array.isArray(b) && !Array.isArray(a)
    if (bothObj) {
      out.push(...diff(b as AnyDoc, a as AnyDoc, path))
    } else if (JSON.stringify(b) !== JSON.stringify(a)) {
      out.push({ path, before: b, after: a })
    }
  }
  return out
}

export default function Settings() {
  const [doc, setDoc] = useState<AnyDoc | null>(null)
  const [original, setOriginal] = useState<AnyDoc | null>(null)
  const [restartRequired, setRestartRequired] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.getConfig().then((r) => {
      setDoc(r.config)
      setOriginal(r.config)
    })
  }, [])

  const changes = useMemo(
    () => (doc && original ? diff(original, doc) : []),
    [doc, original],
  )

  if (!doc || !original) return <div className="p-10 text-sm text-zinc-500">Loading…</div>

  const set = (path: string[], v: unknown) => setDoc((prev) => (prev ? setPath(prev, path, v) : prev))

  async function save() {
    if (!doc) return
    setErr('')
    setSaving(true)
    try {
      const r = await api.putConfig(doc)
      setRestartRequired(r.restart_required)
      setOriginal(doc)
    } catch (e) {
      setErr(String(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="px-10 py-8">
      <header className="mb-6 flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Settings</h1>
          <p className="text-sm text-zinc-500">Live edit of neuromem.yaml. Saves go through schema validation.</p>
        </div>
        <div className="flex items-center gap-3">
          {changes.length > 0 && <span className="text-xs text-amber-300">{changes.length} unsaved changes</span>}
          <button
            disabled={saving || changes.length === 0}
            onClick={save}
            className="rounded bg-emerald-500 px-4 py-2 text-sm font-medium text-zinc-950 disabled:opacity-40"
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </header>

      {err && <div className="mb-4 rounded bg-red-900/30 px-3 py-2 text-sm text-red-200">{err}</div>}
      {restartRequired.length > 0 && (
        <div className="mb-4 rounded border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-200">
          Restart NeuroMem for these to take effect: <code>{restartRequired.join(', ')}</code>
        </div>
      )}

      <div className="grid grid-cols-2 gap-6">
        <Section title="Mode & Auth">
          <Selector
            label="mode"
            value={String(doc.mode)}
            options={['single', 'service']}
            onChange={(v) => set(['mode'], v)}
            restartRequired
          />
          <Selector
            label="auth.type"
            value={String(doc.auth?.type ?? 'none')}
            options={['none', 'api_key', 'jwt']}
            onChange={(v) => set(['auth', 'type'], v)}
            restartRequired
          />
        </Section>

        <Section title="Model">
          <Text
            label="model.embedding"
            value={String(doc.model?.embedding ?? '')}
            onChange={(v) => set(['model', 'embedding'], v)}
            restartRequired
          />
          <Text
            label="model.consolidation_llm"
            value={String(doc.model?.consolidation_llm ?? '')}
            onChange={(v) => set(['model', 'consolidation_llm'], v)}
          />
        </Section>

        <Section title="Vector store">
          <Selector
            label="storage.vector_store.type"
            value={String(doc.storage?.vector_store?.type ?? 'memory')}
            options={['qdrant', 'postgres', 'sqlite', 'memory']}
            onChange={(v) => set(['storage', 'vector_store', 'type'], v)}
            restartRequired
          />
          {doc.storage?.vector_store?.type === 'qdrant' && (
            <>
              <Text
                label="storage.vector_store.config.host"
                value={String(doc.storage?.vector_store?.config?.host ?? 'localhost')}
                onChange={(v) => set(['storage', 'vector_store', 'config', 'host'], v)}
                restartRequired
              />
              <Text
                label="storage.vector_store.config.port"
                value={String(doc.storage?.vector_store?.config?.port ?? 6333)}
                onChange={(v) => set(['storage', 'vector_store', 'config', 'port'], Number(v))}
                restartRequired
              />
            </>
          )}
        </Section>

        <Section title="Database">
          <Selector
            label="storage.database.type"
            value={String(doc.storage?.database?.type ?? 'memory')}
            options={['postgres', 'sqlite', 'memory']}
            onChange={(v) => set(['storage', 'database', 'type'], v)}
            restartRequired
          />
          <Text
            label="storage.database.url"
            value={String(doc.storage?.database?.url ?? '')}
            onChange={(v) => set(['storage', 'database', 'url'], v || null)}
            restartRequired
          />
        </Section>

        <Section title="Memory">
          <Text
            label="memory.consolidation_interval"
            value={String(doc.memory?.consolidation_interval ?? 10)}
            onChange={(v) => set(['memory', 'consolidation_interval'], Number(v))}
          />
          <Text
            label="memory.max_active_memories"
            value={String(doc.memory?.max_active_memories ?? 50)}
            onChange={(v) => set(['memory', 'max_active_memories'], Number(v))}
          />
          <Text
            label="memory.episodic_retention_days"
            value={String(doc.memory?.episodic_retention_days ?? 30)}
            onChange={(v) => set(['memory', 'episodic_retention_days'], Number(v))}
          />
          <Bool
            label="memory.decay_enabled"
            value={Boolean(doc.memory?.decay_enabled ?? true)}
            onChange={(v) => set(['memory', 'decay_enabled'], v)}
          />
        </Section>

        <Section title="Async">
          <Bool
            label="async.enabled"
            value={Boolean(doc.async?.enabled ?? false)}
            onChange={(v) => set(['async', 'enabled'], v)}
          />
        </Section>
      </div>

      {changes.length > 0 && (
        <div className="mt-8 rounded border border-zinc-800 bg-zinc-900/40 p-4">
          <div className="mb-2 text-xs uppercase tracking-wide text-zinc-500">Diff preview</div>
          <table className="w-full text-xs">
            <thead className="text-left text-zinc-500">
              <tr>
                <th className="pr-4">Path</th>
                <th className="pr-4">Before</th>
                <th>After</th>
              </tr>
            </thead>
            <tbody>
              {changes.map((c) => (
                <tr key={c.path} className="border-t border-zinc-800/60">
                  <td className="py-1 pr-4 font-mono text-zinc-300">{c.path}</td>
                  <td className="py-1 pr-4 text-rose-300">{JSON.stringify(c.before)}</td>
                  <td className="py-1 text-emerald-300">{JSON.stringify(c.after)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="mb-3 text-xs uppercase tracking-wide text-zinc-500">{title}</div>
      <div className="grid gap-3">{children}</div>
    </section>
  )
}

function Text({
  label,
  value,
  onChange,
  restartRequired,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  restartRequired?: boolean
}) {
  return (
    <label className="grid gap-1">
      <span className="flex items-center gap-2 text-xs text-zinc-400">
        <code>{label}</code>
        {restartRequired && <Badge>restart</Badge>}
      </span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm text-zinc-100"
      />
    </label>
  )
}

function Selector({
  label,
  value,
  options,
  onChange,
  restartRequired,
}: {
  label: string
  value: string
  options: string[]
  onChange: (v: string) => void
  restartRequired?: boolean
}) {
  return (
    <label className="grid gap-1">
      <span className="flex items-center gap-2 text-xs text-zinc-400">
        <code>{label}</code>
        {restartRequired && <Badge>restart</Badge>}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm text-zinc-100"
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  )
}

function Bool({
  label,
  value,
  onChange,
}: {
  label: string
  value: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <label className="flex items-center gap-2 text-xs text-zinc-400">
      <input type="checkbox" checked={value} onChange={(e) => onChange(e.target.checked)} />
      <code>{label}</code>
    </label>
  )
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span
      className={clsx(
        'rounded border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-amber-300',
      )}
    >
      {children}
    </span>
  )
}
