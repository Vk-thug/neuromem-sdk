/**
 * Thin wrappers around the FastAPI /api/* surface.
 *
 * The dev server proxies /api → :7777 (see vite.config.ts), so we use
 * relative paths everywhere — works in both dev and production builds
 * without env-var juggling.
 */

const base = ''

async function get<T>(path: string): Promise<T> {
  const r = await fetch(base + path)
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json() as Promise<T>
}

export interface MemoryRecord {
  id: string
  user_id: string
  content: string
  memory_type: string
  salience: number
  confidence: number
  created_at: string
  last_accessed: string
  reinforcement: number
  inferred: boolean
  belief_state?: number
  tags: string[]
  metadata: Record<string, unknown>
}

export interface GraphEdge {
  source_id: string
  target_id: string
  link_type: string
  strength: number
  created_at: string
  metadata: Record<string, unknown>
}

export interface GraphNode {
  id: string
  label?: string
  memory_type?: string
  salience?: number
  reinforcement?: number
  content_excerpt?: string
  tags?: string[]
  flashbulb?: boolean
  emotional_weight?: number
  region?:
    | 'hippocampus'
    | 'neocortex'
    | 'basal_ganglia'
    | 'amygdala'
    | 'prefrontal_cortex'
  orphan?: boolean
}

export interface Graph2D {
  nodes: GraphNode[]
  edges: GraphEdge[]
  node_count: number
  edge_count: number
}

export interface Graph3D extends Graph2D {
  regions: string[]
}

export interface RetrievalStage {
  name: string
  elapsed_ms: number
  candidate_count: number
  top_candidates: { memory_id?: string; score?: number; content_excerpt?: string }[]
  notes: Record<string, unknown>
}

export interface RetrievalRun {
  id: string
  user_id: string
  query: string
  task_type: string
  k: number
  started_at: number
  finished_at: number | null
  elapsed_ms: number | null
  status: string
  error: string | null
  stages: RetrievalStage[]
  final_results: Record<string, unknown>[]
  abstained: boolean
  abstention_reason: string | null
  confidence: number
}

export interface ObservationEvent {
  id: string
  user_id: string
  timestamp: number
  user_text: string
  assistant_text: string
  template?: string | null
  salience?: number | null
  emotional_weight?: number | null
  flashbulb: boolean
  tags: string[]
  entities: string[]
  written_memory_ids: string[]
}

export interface BrainState {
  enabled: boolean
  working_memory_ids?: string[]
  td_values?: Record<string, unknown>
  schemas?: Record<string, unknown>
}

export interface McpConfig {
  tunnel: boolean
  hint?: string
  public_url_path?: string
  blobs: Record<string, unknown>
}

export interface IngestStage {
  name: string
  elapsed_ms: number
  chunk_index: number | null
  notes: Record<string, unknown>
}

export interface IngestJob {
  id: string
  user_id: string
  source_path: string
  source_id: string
  parser_name: string
  started_at: number
  finished_at: number | null
  elapsed_ms: number | null
  status: 'running' | 'completed' | 'errored' | 'cancelled'
  error: string | null
  parsed_chunks: number
  written_chunks: number
  written_memory_ids: string[]
  written_verbatim_chunk_ids: string[]
  stages: IngestStage[]
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json() as Promise<T>
}

async function putJson<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json() as Promise<T>
}

export const api = {
  health: () => get<Record<string, unknown>>('/api/health'),
  listMemories: (limit = 50) =>
    get<{ items: MemoryRecord[]; count: number }>(`/api/memories?limit=${limit}`),
  getMemory: (id: string) => get<MemoryRecord>(`/api/memories/${encodeURIComponent(id)}`),
  explainMemory: (id: string) =>
    get<Record<string, unknown>>(`/api/memories/${encodeURIComponent(id)}/explain`),
  search: (query: string, k = 8) =>
    postJson<{ items: MemoryRecord[]; confidence: number; abstained: boolean }>(
      '/api/memories/search',
      { query, k },
    ),
  addMemory: (payload: {
    content: string
    memory_type?: string
    salience?: number
    tags?: string[]
    belief_state?: number
    template?: string
    metadata?: Record<string, unknown>
  }) => postJson<{ status: string }>('/api/memories', payload),
  editMemory: (id: string, payload: {
    content: string
    salience?: number
    tags?: string[]
    belief_state?: number
    metadata?: Record<string, unknown>
  }) =>
    putJson<{ status: string; old_id: string; new_id: string }>(
      `/api/memories/${encodeURIComponent(id)}`,
      payload,
    ),
  deleteMemory: (id: string) =>
    fetch(`/api/memories/${encodeURIComponent(id)}`, { method: 'DELETE' }).then(
      (r) => r.json() as Promise<{ status: string; id: string }>,
    ),
  graph2d: () => get<Graph2D>('/api/graph/2d'),
  graph3d: () => get<Graph3D>('/api/graph/3d'),
  egoGraph: (id: string, depth = 2) =>
    get<{ center: string; nodes: GraphNode[]; edges: GraphEdge[] }>(
      `/api/graph/ego/${encodeURIComponent(id)}?depth=${depth}`,
    ),
  retrievals: (limit = 50) =>
    get<{ runs: RetrievalRun[]; count: number }>(`/api/retrievals?limit=${limit}`),
  retrieval: (id: string) => get<RetrievalRun>(`/api/retrievals/${encodeURIComponent(id)}`),
  observations: (limit = 100) =>
    get<{ events: ObservationEvent[]; count: number }>(`/api/observations?limit=${limit}`),
  brain: () => get<BrainState>('/api/brain/state'),
  mcpConfig: () => get<McpConfig>('/api/mcp-config'),
  ingestJobs: (limit = 50) =>
    get<{ jobs: IngestJob[]; count: number }>(`/api/ingest?limit=${limit}`),
  ingestJob: (id: string) => get<IngestJob>(`/api/ingest/${encodeURIComponent(id)}`),
  cancelIngest: (id: string) =>
    fetch(`/api/ingest/${encodeURIComponent(id)}`, { method: 'DELETE' }).then(
      (r) => r.json() as Promise<{ status: string; id: string }>,
    ),
  parserSuffixes: () => get<{ suffixes: string[] }>('/api/ingest/parsers'),
  uploadFile: async (file: File, alsoEpisodic = false) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('also_episodic', String(alsoEpisodic))
    const r = await fetch('/api/ingest/file', { method: 'POST', body: fd })
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
    return r.json() as Promise<{
      status: string
      filename: string
      tmp_path: string
      also_episodic: boolean
    }>
  },

  // ---- Config (v0.4.2) -------------------------------------------------
  getConfig: () =>
    get<{
      path: string
      exists: boolean
      mode: 'single' | 'service'
      setup_complete: boolean
      config: Record<string, unknown>
    }>('/api/config'),
  putConfig: (patch: Record<string, unknown>) =>
    putJson<{
      ok: true
      config: Record<string, unknown>
      restart_required: string[]
    }>('/api/config', { patch }),
  validateConfig: (patch: Record<string, unknown>) =>
    postJson<{ ok: true } | { detail: string }>('/api/config/validate', { patch }),
  testConnection: (req: {
    target: 'ollama' | 'qdrant' | 'postgres'
    host?: string
    port?: number
    url?: string
  }) =>
    postJson<{ ok: boolean; message: string }>('/api/config/test-connection', req),
}
