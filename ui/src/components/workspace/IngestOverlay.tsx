import { useEffect, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import useSWR from 'swr'
import clsx from 'clsx'
import { api, type IngestJob } from '../../lib/api.ts'

/**
 * Full-workspace drag-drop overlay. Mounts at the workspace root and
 * intercepts drag events on document.body — so you can drop a file
 * anywhere, not just on a designated zone.
 *
 * Active uploads render as a stacked toast in the bottom-right with
 * live progress driven by SSE on /api/ingest/stream/{id}.
 */
export default function IngestOverlay() {
  const [dragging, setDragging] = useState(false)
  const [activeJobs, setActiveJobs] = useState<string[]>([])

  const onDrop = async (files: File[]) => {
    setDragging(false)
    for (const f of files) {
      try {
        await api.uploadFile(f)
        // The job is enqueued server-side; we poll the list endpoint
        // briefly to discover the job id, then subscribe to its SSE
        // stream.
        const recent = await api.ingestJobs(5)
        const newest = recent.jobs.find((j) => j.source_path.endsWith(f.name))
        if (newest) setActiveJobs((prev) => [...prev, newest.id])
      } catch (err) {
        console.error('upload failed', err)
      }
    }
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    noClick: true, // overlay is for drag only — click elsewhere doesn't open file picker
    onDragEnter: () => setDragging(true),
    onDragLeave: () => setDragging(false),
  })

  return (
    <div {...getRootProps()} className="contents">
      <input {...getInputProps()} />
      {(dragging || isDragActive) && (
        <div className="pointer-events-none fixed inset-0 z-40 flex items-center justify-center bg-blue-500/10 backdrop-blur-sm">
          <div className="rounded-lg border-2 border-dashed border-blue-400 bg-zinc-950/80 px-12 py-8 text-center">
            <div className="text-2xl">📄</div>
            <div className="mt-2 text-sm text-blue-200">
              Drop to ingest into your knowledge base
            </div>
            <div className="mt-1 text-[11px] text-zinc-400">
              PDF · DOCX · XLSX · PPTX · MD · HTML · PNG · JPG
            </div>
          </div>
        </div>
      )}
      <div className="pointer-events-none fixed bottom-4 right-4 z-40 flex flex-col gap-2">
        {activeJobs.map((id) => (
          <IngestProgressToast
            key={id}
            jobId={id}
            onDone={() =>
              setActiveJobs((prev) => prev.filter((p) => p !== id))
            }
          />
        ))}
      </div>
    </div>
  )
}

function IngestProgressToast({
  jobId,
  onDone,
}: {
  jobId: string
  onDone: () => void
}) {
  const [job, setJob] = useState<IngestJob | null>(null)

  useEffect(() => {
    const es = new EventSource(`/api/ingest/stream/${jobId}`)
    es.addEventListener('progress', (ev) => {
      try {
        const parsed = JSON.parse((ev as MessageEvent).data) as IngestJob
        setJob(parsed)
        if (
          parsed.status === 'completed' ||
          parsed.status === 'errored' ||
          parsed.status === 'cancelled'
        ) {
          es.close()
          window.setTimeout(onDone, 4000)
        }
      } catch {
        // ignore malformed frames
      }
    })
    es.onerror = () => {
      es.close()
      onDone()
    }
    return () => es.close()
  }, [jobId, onDone])

  // Fallback: SWR poll every 2s in case SSE is blocked.
  const { data } = useSWR(['ingest', jobId], () => api.ingestJob(jobId), {
    refreshInterval: job ? 0 : 2000,
  })
  const current = job ?? data ?? null
  if (!current) return null

  const filename = current.source_path.split('/').pop() ?? current.source_path
  const status = current.status
  const ratio = current.parsed_chunks
    ? Math.min(1, current.written_chunks / Math.max(1, current.parsed_chunks))
    : 0

  return (
    <div className="pointer-events-auto w-72 rounded border border-zinc-700 bg-zinc-950 p-3 text-xs shadow-lg">
      <div className="flex items-center justify-between">
        <span className="truncate font-mono text-zinc-200">{filename}</span>
        <span
          className={clsx(
            'ml-2 rounded px-1.5 py-0.5 text-[10px]',
            status === 'completed'
              ? 'bg-emerald-900/40 text-emerald-300'
              : status === 'errored'
                ? 'bg-rose-900/40 text-rose-300'
                : status === 'cancelled'
                  ? 'bg-zinc-800 text-zinc-400'
                  : 'bg-blue-900/40 text-blue-300',
          )}
        >
          {status}
        </span>
      </div>
      <div className="mt-2 h-1 overflow-hidden rounded bg-zinc-800">
        <div
          className={clsx(
            'h-full transition-all',
            status === 'errored' ? 'bg-rose-500' : 'bg-blue-500',
          )}
          style={{ width: `${Math.round(ratio * 100)}%` }}
        />
      </div>
      <div className="mt-1 flex items-center justify-between text-[10px] text-zinc-500">
        <span>
          {current.written_chunks} / {current.parsed_chunks || '?'} chunks
        </span>
        {status === 'running' && (
          <button
            type="button"
            onClick={() => api.cancelIngest(jobId).catch(() => undefined)}
            className="hover:text-rose-300"
          >
            cancel
          </button>
        )}
      </div>
      {current.error && (
        <div className="mt-1 truncate text-[10px] text-rose-300" title={current.error}>
          {current.error}
        </div>
      )}
    </div>
  )
}
