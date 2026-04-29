/**
 * /onboarding — first-run wizard.
 *
 * Five steps: Mode → Embedding → Storage → Auth → Review. Each step
 * mutates a single ``patch`` object that's POSTed to /api/config on
 * "Finish". The header shows live progress; the right rail renders
 * the merged yaml so users see exactly what they're about to save.
 *
 * The wizard is gated on ``setup_complete=false`` (see App.tsx). Once
 * the user finishes, ``setup_complete`` flips to true and the gate
 * stops redirecting.
 */

import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import clsx from 'clsx'
import { api } from '@/lib/api'

type Mode = 'single' | 'service'
type EmbeddingProvider = 'ollama' | 'openai'
type Storage = 'memory' | 'qdrant' | 'postgres'

interface Answers {
  mode: Mode
  embedding: EmbeddingProvider
  openaiKey: string
  storage: Storage
  qdrantHost: string
  qdrantPort: number
  postgresUrl: string
  port: number
}

const DEFAULTS: Answers = {
  mode: 'single',
  embedding: 'ollama',
  openaiKey: '',
  storage: 'qdrant',
  qdrantHost: 'localhost',
  qdrantPort: 6333,
  postgresUrl: 'postgresql://neuromem:neuromem@localhost:5432/neuromem',
  port: 7777,
}

const STEPS = ['Mode', 'Embedding', 'Storage', 'Auth', 'Review'] as const

function buildPatch(a: Answers): Record<string, unknown> {
  const useOpenai = a.embedding === 'openai'
  const embedding = useOpenai ? 'text-embedding-3-large' : 'nomic-embed-text'
  const vectorSize = useOpenai ? 3072 : 768

  let vectorStore: Record<string, unknown>
  if (a.storage === 'qdrant') {
    vectorStore = {
      type: 'qdrant',
      config: {
        host: a.qdrantHost,
        port: a.qdrantPort,
        collection_name: 'neuromem',
        vector_size: vectorSize,
      },
    }
  } else if (a.storage === 'postgres') {
    vectorStore = { type: 'postgres', config: { url: a.postgresUrl } }
  } else {
    vectorStore = { type: 'memory' }
  }

  const databaseType =
    a.mode === 'service' || a.storage === 'postgres' ? 'postgres' : 'memory'
  const databaseUrl = databaseType === 'postgres' ? a.postgresUrl : null

  return {
    mode: a.mode,
    setup_complete: true,
    auth: a.mode === 'service'
      ? { type: 'api_key', secret_env: 'NEUROMEM_AUTH_SECRET' }
      : { type: 'none' },
    ui: { port: a.port, host: '127.0.0.1' },
    model: {
      embedding,
      consolidation_llm: useOpenai ? 'gpt-4o-mini' : 'ollama/qwen2.5-coder:7b',
    },
    storage: {
      vector_store: vectorStore,
      database: { type: databaseType, url: databaseUrl },
    },
  }
}

export default function Onboarding() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [a, setA] = useState<Answers>(DEFAULTS)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [testResult, setTestResult] = useState<Record<string, string>>({})

  const patch = useMemo(() => buildPatch(a), [a])

  const set = <K extends keyof Answers>(k: K, v: Answers[K]) =>
    setA((prev) => ({ ...prev, [k]: v }))

  async function testStorage() {
    setTestResult({})
    if (a.storage === 'qdrant') {
      const r = await api.testConnection({
        target: 'qdrant',
        host: a.qdrantHost,
        port: a.qdrantPort,
      })
      setTestResult({ qdrant: `${r.ok ? 'OK ' : 'FAIL '} ${r.message}` })
    } else if (a.storage === 'postgres') {
      const r = await api.testConnection({ target: 'postgres', url: a.postgresUrl })
      setTestResult({ postgres: `${r.ok ? 'OK ' : 'FAIL '} ${r.message}` })
    }
    if (a.embedding === 'ollama') {
      const r = await api.testConnection({ target: 'ollama' })
      setTestResult((prev) => ({ ...prev, ollama: `${r.ok ? 'OK ' : 'FAIL '} ${r.message}` }))
    }
  }

  async function finish() {
    setError('')
    setBusy(true)
    try {
      await api.putConfig(patch)
      navigate('/')
      window.location.reload()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  const canNext = (() => {
    if (step === 1 && a.embedding === 'openai' && !a.openaiKey) return false
    if (step === 2 && a.storage === 'postgres' && !a.postgresUrl) return false
    if (step === 3 && a.mode === 'service' && !a.postgresUrl) return false
    return true
  })()

  return (
    <div className="grid min-h-screen grid-cols-[1fr_420px] bg-zinc-950 text-zinc-100">
      <div className="flex flex-col px-12 py-10">
        <header className="mb-8">
          <div className="text-sm text-zinc-500">NeuroMem setup</div>
          <h1 className="text-2xl font-bold tracking-tight">Welcome.</h1>
        </header>

        <ol className="mb-8 flex gap-2">
          {STEPS.map((label, i) => (
            <li
              key={label}
              className={clsx(
                'flex-1 rounded px-3 py-1.5 text-xs',
                i === step
                  ? 'bg-zinc-100 text-zinc-900'
                  : i < step
                    ? 'bg-emerald-900/40 text-emerald-200'
                    : 'bg-zinc-900 text-zinc-500',
              )}
            >
              {i + 1}. {label}
            </li>
          ))}
        </ol>

        <div className="flex-1">
          {step === 0 && <StepMode value={a.mode} onChange={(v) => set('mode', v)} />}
          {step === 1 && (
            <StepEmbedding
              value={a.embedding}
              keyValue={a.openaiKey}
              onChange={(v) => set('embedding', v)}
              onKeyChange={(v) => set('openaiKey', v)}
            />
          )}
          {step === 2 && (
            <StepStorage
              storage={a.storage}
              qdrantHost={a.qdrantHost}
              qdrantPort={a.qdrantPort}
              postgresUrl={a.postgresUrl}
              testResult={testResult}
              onTest={testStorage}
              onChange={(field, value) => set(field, value as never)}
            />
          )}
          {step === 3 && <StepAuth mode={a.mode} postgresUrl={a.postgresUrl} onChangeUrl={(v) => set('postgresUrl', v)} />}
          {step === 4 && <StepReview answers={a} patch={patch} />}
        </div>

        {error && <div className="mb-3 rounded bg-red-900/30 px-3 py-2 text-sm text-red-200">{error}</div>}

        <div className="flex justify-between">
          <button
            className="rounded px-4 py-2 text-sm text-zinc-400 disabled:opacity-30"
            disabled={step === 0}
            onClick={() => setStep((s) => s - 1)}
          >
            Back
          </button>
          {step < STEPS.length - 1 ? (
            <button
              className="rounded bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-900 disabled:opacity-40"
              disabled={!canNext}
              onClick={() => setStep((s) => s + 1)}
            >
              Continue
            </button>
          ) : (
            <button
              className="rounded bg-emerald-500 px-4 py-2 text-sm font-medium text-zinc-950 disabled:opacity-40"
              disabled={busy}
              onClick={finish}
            >
              {busy ? 'Saving…' : 'Finish setup'}
            </button>
          )}
        </div>
      </div>

      <aside className="border-l border-zinc-800 bg-zinc-900/40 px-6 py-10">
        <div className="mb-3 text-xs uppercase tracking-wide text-zinc-500">
          neuromem.yaml preview
        </div>
        <pre className="whitespace-pre-wrap break-words text-[11px] leading-relaxed text-zinc-300">
          {JSON.stringify({ neuromem: patch }, null, 2)}
        </pre>
      </aside>
    </div>
  )
}

// ----------------------------- step components -----------------------------

function StepMode({ value, onChange }: { value: Mode; onChange: (m: Mode) => void }) {
  return (
    <div className="grid gap-3">
      <h2 className="text-lg font-semibold">How will you use NeuroMem?</h2>
      <Choice
        active={value === 'single'}
        title="Single user"
        sub="Local laptop or desktop. No auth. Recommended."
        onClick={() => onChange('single')}
      />
      <Choice
        active={value === 'service'}
        title="Service / multi-user"
        sub="Shared deployment with API-key auth. Requires Postgres."
        onClick={() => onChange('service')}
      />
    </div>
  )
}

function StepEmbedding({
  value,
  keyValue,
  onChange,
  onKeyChange,
}: {
  value: EmbeddingProvider
  keyValue: string
  onChange: (v: EmbeddingProvider) => void
  onKeyChange: (v: string) => void
}) {
  return (
    <div className="grid gap-3">
      <h2 className="text-lg font-semibold">Pick an embedding model</h2>
      <Choice
        active={value === 'ollama'}
        title="Ollama nomic-embed-text"
        sub="Local, free, 768-dim. Requires `ollama serve` running."
        onClick={() => onChange('ollama')}
      />
      <Choice
        active={value === 'openai'}
        title="OpenAI text-embedding-3-large"
        sub="3072-dim, paid. Higher quality."
        onClick={() => onChange('openai')}
      />
      {value === 'openai' && (
        <label className="grid gap-1 pt-3">
          <span className="text-xs text-zinc-400">OpenAI API key</span>
          <input
            type="password"
            placeholder="sk-..."
            value={keyValue}
            onChange={(e) => onKeyChange(e.target.value)}
            className="rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
          />
          <span className="text-[11px] text-zinc-500">
            Stored in <code>.env</code> on the server, never in yaml.
          </span>
        </label>
      )}
    </div>
  )
}

function StepStorage({
  storage,
  qdrantHost,
  qdrantPort,
  postgresUrl,
  testResult,
  onTest,
  onChange,
}: {
  storage: Storage
  qdrantHost: string
  qdrantPort: number
  postgresUrl: string
  testResult: Record<string, string>
  onTest: () => void
  onChange: (field: keyof Answers, value: unknown) => void
}) {
  return (
    <div className="grid gap-3">
      <h2 className="text-lg font-semibold">Where should memories live?</h2>
      <Choice
        active={storage === 'qdrant'}
        title="Qdrant (recommended)"
        sub="docker run -p 6333:6333 qdrant/qdrant"
        onClick={() => onChange('storage', 'qdrant')}
      />
      <Choice
        active={storage === 'memory'}
        title="In-memory"
        sub="No persistence — restart wipes everything."
        onClick={() => onChange('storage', 'memory')}
      />
      <Choice
        active={storage === 'postgres'}
        title="Postgres + pgvector"
        sub="Production-grade, slower than Qdrant."
        onClick={() => onChange('storage', 'postgres')}
      />

      {storage === 'qdrant' && (
        <div className="mt-3 grid grid-cols-2 gap-3">
          <Field label="Qdrant host" value={qdrantHost} onChange={(v) => onChange('qdrantHost', v)} />
          <Field label="Qdrant port" value={String(qdrantPort)} onChange={(v) => onChange('qdrantPort', Number(v))} />
        </div>
      )}
      {storage === 'postgres' && (
        <div className="mt-3">
          <Field label="Postgres URL" value={postgresUrl} onChange={(v) => onChange('postgresUrl', v)} />
        </div>
      )}

      <div className="mt-3 flex items-center gap-3">
        <button onClick={onTest} className="rounded border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300">
          Test connection
        </button>
        <div className="flex flex-col gap-0.5 text-xs text-zinc-400">
          {Object.entries(testResult).map(([k, v]) => (
            <span key={k}>
              <strong>{k}:</strong> {v}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

function StepAuth({
  mode,
  postgresUrl,
  onChangeUrl,
}: {
  mode: Mode
  postgresUrl: string
  onChangeUrl: (v: string) => void
}) {
  if (mode === 'single') {
    return (
      <div className="grid gap-3">
        <h2 className="text-lg font-semibold">Auth</h2>
        <p className="text-sm text-zinc-400">
          Single-user mode has no auth. The user_id is read from the{' '}
          <code>NEUROMEM_USER_ID</code> env var (defaults to <code>default</code>).
        </p>
        <p className="text-xs text-zinc-500">
          You can switch to service mode later from <code>/settings</code>.
        </p>
      </div>
    )
  }
  return (
    <div className="grid gap-3">
      <h2 className="text-lg font-semibold">Service-mode auth</h2>
      <p className="text-sm text-zinc-400">
        We'll generate a <code>NEUROMEM_AUTH_SECRET</code> and store it in <code>.env</code>.
        Each user gets an API key (created from the Users tab after setup).
      </p>
      <Field label="Postgres URL (for users + memory)" value={postgresUrl} onChange={onChangeUrl} />
    </div>
  )
}

function StepReview({ answers, patch }: { answers: Answers; patch: Record<string, unknown> }) {
  return (
    <div className="grid gap-3">
      <h2 className="text-lg font-semibold">Review</h2>
      <ul className="text-sm text-zinc-300">
        <li>Mode: <strong>{answers.mode}</strong></li>
        <li>Embedding: <strong>{answers.embedding}</strong></li>
        <li>Storage: <strong>{answers.storage}</strong></li>
        <li>UI port: <strong>{answers.port}</strong></li>
      </ul>
      <p className="text-xs text-zinc-500">
        Clicking "Finish setup" writes <code>neuromem.yaml</code> with the preview on the right.
      </p>
      <pre className="max-h-64 overflow-auto rounded bg-black/40 p-3 text-[11px] text-zinc-300">
        {JSON.stringify(patch, null, 2)}
      </pre>
    </div>
  )
}

function Choice({
  active,
  title,
  sub,
  onClick,
}: {
  active: boolean
  title: string
  sub: string
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        'rounded border px-4 py-3 text-left transition',
        active
          ? 'border-emerald-500 bg-emerald-500/10'
          : 'border-zinc-800 bg-zinc-900/40 hover:border-zinc-700',
      )}
    >
      <div className="text-sm font-medium text-zinc-100">{title}</div>
      <div className="text-xs text-zinc-400">{sub}</div>
    </button>
  )
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <label className="grid gap-1">
      <span className="text-xs text-zinc-400">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
      />
    </label>
  )
}

/** Hook that gates the whole app on /onboarding when setup_complete=false. */
export function useSetupGate() {
  const navigate = useNavigate()
  useEffect(() => {
    let cancelled = false
    api.getConfig().then((r) => {
      if (!cancelled && !r.setup_complete && window.location.pathname !== '/onboarding') {
        navigate('/onboarding')
      }
    })
    return () => {
      cancelled = true
    }
  }, [navigate])
}
