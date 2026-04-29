"""
FastAPI server for the NeuroMem local UI.

Mounts:
* ``/api/health``                        — basic liveness probe.
* ``/api/memories``                      — list + structured query.
* ``/api/memories/{id}``                 — get + update + delete.
* ``/api/memories/{id}/explain``         — retrieval-attribution trace.
* ``/api/graph/2d``                      — Cytoscape-shaped JSON.
* ``/api/graph/3d``                      — react-force-graph 3D shape with
                                            anatomical region assignments.
* ``/api/graph/ego/{id}``                — depth-N ego graph for one node.
* ``/api/retrievals``                    — list recent retrieval runs.
* ``/api/retrievals/{id}``               — full per-stage trace.
* ``/api/retrievals/stream``             — SSE stream of new runs.
* ``/api/observations``                  — list recent observe() events.
* ``/api/observations/stream``           — SSE stream of new events.
* ``/api/brain/state``                   — WM slots + TD values + schema
                                            centroids + decay snapshot.
* ``/api/mcp-config``                    — ready-to-paste blobs.

Static SPA bundle is served from ``neuromem/ui/web/`` at ``/``.

Construction:
    app = create_app(memory: NeuroMem)

The factory takes a fully-constructed ``NeuroMem`` so the UI can read the
in-process graph and brain state directly. This is the local-only design;
multi-tenant deployments would substitute a different factory.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional

try:
    from fastapi import (
        FastAPI,
        File,
        Form,
        HTTPException,
        Query,
        UploadFile,
    )
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse
    from fastapi.staticfiles import StaticFiles
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "neuromem.ui requires FastAPI. Install with `pip install 'neuromem-sdk[ui]'`."
    ) from exc

from neuromem.core.audit.ingest_log import (
    IngestJob,
    default_log as default_ingest_log,
)
from neuromem.core.audit.retrieval_log import (
    RetrievalRun,
    default_log as default_retrieval_log,
)
from neuromem.core.audit.observation_log import (
    ObservationEvent,
    default_log as default_observation_log,
)
from neuromem.core.types import BeliefState, MemoryItem, MemoryLink, MemoryType
from neuromem.utils.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from neuromem import NeuroMem

logger = get_logger(__name__)


WEB_DIR = Path(__file__).parent / "web"


def _memory_to_json(item: Any) -> Dict[str, Any]:
    """Strip embedding (huge) and emit UI-friendly memory record."""
    d = item.to_dict()
    d.pop("embedding", None)
    return d


# Map MemoryType -> 3D anatomical region. The UI's force-graph layout uses
# these to anchor nodes into anatomical clusters.
_REGION_FOR_TYPE = {
    MemoryType.EPISODIC.value: "hippocampus",
    MemoryType.SEMANTIC.value: "neocortex",
    MemoryType.PROCEDURAL.value: "basal_ganglia",
    MemoryType.AFFECTIVE.value: "amygdala",
    MemoryType.WORKING.value: "prefrontal_cortex",
}


def _region_for(item: Any) -> str:
    """Pick the anatomical region for a memory item (used by 3D layout)."""
    md = getattr(item, "metadata", {}) or {}
    if md.get("flashbulb"):
        return "amygdala"
    if md.get("store_type") == "verbatim_chunk":
        return "hippocampus"
    mt = item.memory_type
    mt_value = mt.value if hasattr(mt, "value") else str(mt)
    return _REGION_FOR_TYPE.get(mt_value, "neocortex")


def _serialize_memory_for_graph(item: Any) -> Dict[str, Any]:
    md = item.metadata or {}
    content = (item.content or "")[:140]
    return {
        "label": content[:60],
        "memory_type": (
            item.memory_type.value if hasattr(item.memory_type, "value") else str(item.memory_type)
        ),
        "salience": item.salience,
        "reinforcement": item.reinforcement,
        "content_excerpt": content,
        "tags": list(item.tags or []),
        "flashbulb": bool(md.get("flashbulb", False)),
        "emotional_weight": md.get("emotional_weight", 0.0),
    }


def create_app(memory: "NeuroMem") -> FastAPI:
    """Construct the FastAPI app bound to a live ``NeuroMem`` instance."""

    app = FastAPI(
        title="NeuroMem UI",
        version="0.4.0",
        description="Local brain-inspired memory dashboard.",
    )

    # CORS: vite dev server runs on 5173; production build is served from
    # the same origin. Both whitelisted.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:7777",
            "http://127.0.0.1:7777",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Enable audit logs the moment the UI server boots.
    default_retrieval_log.enable()
    default_observation_log.enable()
    default_ingest_log.enable()

    # Mount /api/config first so it wins over the static SPA mount at "/".
    from neuromem.ui.api.config_routes import build_router as _build_config_router

    app.include_router(_build_config_router())

    # Service mode (v0.4.2): swap UserManager to SqlUserStore, attach the
    # API-key middleware, and expose /api/users for key minting. Single-user
    # mode skips this entirely — no auth, no DB required for users.
    try:
        from neuromem.config_schema import ConfigService
        import os as _os

        _cfg_path = _os.environ.get("NEUROMEM_CONFIG", "neuromem.yaml")
        _cfg_doc = ConfigService(_cfg_path).load_or_default()
    except Exception as _exc:  # pragma: no cover - defensive
        logger.warning("config load failed during service-mode setup: %s", _exc)
        _cfg_doc = None

    if _cfg_doc is not None and _cfg_doc.mode == "service":
        from neuromem.ui.api.auth import (
            APIKeyAuthMiddleware,
            build_users_router,
            configure_user_backend_for_service_mode,
        )

        _db_url = _cfg_doc.storage.database.url
        if _db_url:
            configure_user_backend_for_service_mode(_db_url)
        app.add_middleware(APIKeyAuthMiddleware)
        app.include_router(build_users_router())
        logger.info("service mode active: API-key auth enabled, users router mounted")

    # KB ingester — lazy-init on first upload (heavy Docling import).
    _kb_ingester = {"instance": None}

    def _get_ingester():
        if _kb_ingester["instance"] is None:
            from neuromem.core.ingest.ingester import KnowledgeBaseIngester

            _kb_ingester["instance"] = KnowledgeBaseIngester(memory)
        return _kb_ingester["instance"]

    # ----- liveness ------------------------------------------------------

    @app.get("/api/health")
    def health() -> Dict[str, Any]:
        controller = memory.controller
        graph = controller.graph
        return {
            "status": "ok",
            "version": "0.4.0",
            "user_id": memory.user_id,
            "graph": {
                "nodes": graph.node_count,
                "edges": graph.edge_count,
            },
            "audit": {
                "retrieval_log_enabled": default_retrieval_log.enabled,
                "observation_log_enabled": default_observation_log.enabled,
            },
            "brain_enabled": controller.brain is not None,
        }

    # ----- memories ------------------------------------------------------

    @app.get("/api/memories")
    def list_memories(
        memory_type: Optional[str] = None,
        limit: int = Query(50, ge=1, le=1000),
    ) -> Dict[str, Any]:
        items = memory.list(memory_type=memory_type, limit=limit)
        return {"items": [_memory_to_json(i) for i in items], "count": len(items)}

    @app.get("/api/memories/{memory_id}")
    def get_memory(memory_id: str) -> Dict[str, Any]:
        backend = memory.controller.episodic.backend
        item = backend.get_by_id(memory_id)
        if item is None:
            raise HTTPException(status_code=404, detail="memory not found")
        return _memory_to_json(item)

    @app.get("/api/memories/{memory_id}/explain")
    def explain_memory(memory_id: str) -> Dict[str, Any]:
        try:
            return memory.explain(memory_id)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.delete("/api/memories/{memory_id}")
    def delete_memory(memory_id: str) -> Dict[str, str]:
        memory.forget(memory_id)
        return {"status": "deleted", "id": memory_id}

    @app.post("/api/memories")
    def add_memory(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Explicit add — wraps NeuroMem.observe with a one-sided
        observation. Used by the UI's 'New memory' button.
        """
        content = (payload.get("content") or "").strip()
        if not content:
            raise HTTPException(status_code=400, detail="content is required")
        metadata = dict(payload.get("metadata") or {})
        if payload.get("belief_state") is not None:
            metadata["belief_state"] = int(payload["belief_state"])
        memory.observe(
            user_input=content,
            assistant_output=payload.get("assistant_output", ""),
            template=payload.get("template"),
            metadata=metadata,
        )
        return {"status": "added"}

    @app.put("/api/memories/{memory_id}")
    def edit_memory(memory_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Soft-supersede edit (Nader 2000 reconsolidation-faithful):
        old memory marked deprecated, a NEW memory is created with new
        content and a ``supersedes`` graph link to the old one. The old
        memory remains retrievable but ranks below current siblings."""
        new_content = (payload.get("content") or "").strip()
        if not new_content:
            raise HTTPException(status_code=400, detail="content is required")

        backend = memory.controller.episodic.backend
        old = backend.get_by_id(memory_id)
        if old is None:
            raise HTTPException(status_code=404, detail="memory not found")

        # Deprecate the old memory in place.
        old_meta = dict(old.metadata or {})
        old_meta["deprecated"] = True
        old_meta["superseded_at"] = (
            __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        )
        old.metadata = old_meta
        backend.update(old)

        # Create the new trace.
        from neuromem.utils.embeddings import get_embedding

        new_id = __import__("uuid").uuid4().hex
        embedding_model = memory.config.model().get("embedding", "text-embedding-3-large")
        try:
            embedding = get_embedding(new_content, embedding_model)
        except Exception:
            embedding = old.embedding

        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        belief_state_raw = payload.get("belief_state")
        try:
            belief_state = (
                BeliefState(int(belief_state_raw))
                if belief_state_raw is not None
                else old.belief_state
            )
        except (ValueError, TypeError):
            belief_state = old.belief_state

        new_item = MemoryItem(
            id=new_id,
            user_id=old.user_id,
            content=new_content,
            embedding=embedding,
            memory_type=old.memory_type,
            salience=float(payload.get("salience", old.salience)),
            confidence=float(payload.get("confidence", old.confidence)),
            created_at=now,
            last_accessed=now,
            decay_rate=old.decay_rate,
            reinforcement=0,
            inferred=False,
            editable=True,
            tags=list(payload.get("tags") or old.tags),
            metadata={
                **(payload.get("metadata") or {}),
                "supersedes": memory_id,
                "edit_lineage_root": old.metadata.get("edit_lineage_root", memory_id),
            },
            belief_state=belief_state,
        )
        backend.upsert(new_item)

        # Graph link: new --supersedes--> old. Reuses the link type
        # already defined in core/graph.py LINK_TYPES since v0.2.0.
        memory.controller.graph.add_link(
            MemoryLink(
                source_id=new_id,
                target_id=memory_id,
                link_type="supersedes",
                strength=1.0,
                created_at=now,
                metadata={"reason": "user_edit"},
            )
        )
        return {"status": "edited", "old_id": memory_id, "new_id": new_id}

    @app.post("/api/memories/search")
    def search_memories(payload: Dict[str, Any]) -> Dict[str, Any]:
        query_text = payload.get("query", "")
        k = int(payload.get("k", 8))
        result = memory.retrieve(query=query_text, task_type="chat", k=k)
        return {
            "items": [_memory_to_json(i) for i in result],
            "confidence": getattr(result, "confidence", 1.0),
            "abstained": getattr(result, "abstained", False),
        }

    # ----- knowledge graph -----------------------------------------------

    @app.get("/api/graph/2d")
    def graph_2d() -> Dict[str, Any]:
        controller = memory.controller
        graph = controller.graph
        backend = controller.episodic.backend

        export = graph.export()
        node_records: List[Dict[str, Any]] = []
        for node_id in export["nodes"]:
            item = backend.get_by_id(node_id)
            if item is None:
                node_records.append({"id": node_id, "label": node_id, "orphan": True})
                continue
            record = {"id": node_id, **_serialize_memory_for_graph(item)}
            node_records.append(record)
        return {
            "nodes": node_records,
            "edges": export["edges"],
            "node_count": export["node_count"],
            "edge_count": export["edge_count"],
        }

    @app.get("/api/graph/3d")
    def graph_3d() -> Dict[str, Any]:
        controller = memory.controller
        graph = controller.graph
        backend = controller.episodic.backend

        export = graph.export()
        node_records: List[Dict[str, Any]] = []
        for node_id in export["nodes"]:
            item = backend.get_by_id(node_id)
            if item is None:
                node_records.append(
                    {"id": node_id, "label": node_id, "orphan": True, "region": "neocortex"}
                )
                continue
            record = {
                "id": node_id,
                "region": _region_for(item),
                **_serialize_memory_for_graph(item),
            }
            node_records.append(record)
        return {
            "nodes": node_records,
            "edges": export["edges"],
            "regions": list(_REGION_FOR_TYPE.values()),
        }

    @app.get("/api/graph/ego/{memory_id}")
    def ego_graph(memory_id: str, depth: int = Query(2, ge=1, le=4)) -> Dict[str, Any]:
        graph = memory.controller.graph
        related_ids = graph.get_related(memory_id, depth=depth)
        ids = {memory_id} | set(related_ids)
        backend = memory.controller.episodic.backend
        nodes = []
        for nid in ids:
            item = backend.get_by_id(nid)
            if item is None:
                continue
            nodes.append(
                {"id": nid, "region": _region_for(item), **_serialize_memory_for_graph(item)}
            )
        edges = []
        for nid in ids:
            for link in graph.get_links(nid):
                if link.target_id in ids:
                    edges.append(link.to_dict())
        return {"center": memory_id, "nodes": nodes, "edges": edges}

    # ----- retrieval inspector ------------------------------------------

    @app.get("/api/retrievals")
    def list_retrievals(limit: int = Query(50, ge=1, le=1000)) -> Dict[str, Any]:
        runs = default_retrieval_log.list(limit=limit)
        return {"runs": [r.to_dict() for r in runs], "count": len(runs)}

    @app.get("/api/retrievals/{run_id}")
    def get_retrieval(run_id: str) -> Dict[str, Any]:
        run = default_retrieval_log.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        return run.to_dict()

    @app.get("/api/retrievals/stream")
    async def stream_retrievals() -> StreamingResponse:
        return StreamingResponse(
            _sse_retrieval_stream(),
            media_type="text/event-stream",
        )

    # ----- observation feed ---------------------------------------------

    @app.get("/api/observations")
    def list_observations(limit: int = Query(100, ge=1, le=1000)) -> Dict[str, Any]:
        events = default_observation_log.list(limit=limit)
        return {"events": [e.to_dict() for e in events], "count": len(events)}

    @app.get("/api/observations/stream")
    async def stream_observations() -> StreamingResponse:
        return StreamingResponse(
            _sse_observation_stream(),
            media_type="text/event-stream",
        )

    # ----- brain telemetry ----------------------------------------------

    @app.get("/api/brain/state")
    def brain_state() -> Dict[str, Any]:
        controller = memory.controller
        if controller.brain is None:
            return {"enabled": False}
        brain = controller.brain
        try:
            wm_ids = brain.get_working_memory_ids()
        except Exception:
            wm_ids = []
        try:
            td_state = brain.td_learner.get_state() if hasattr(brain, "td_learner") else {}
        except Exception:
            td_state = {}
        try:
            schema_state = (
                brain.schema_integrator.get_state() if hasattr(brain, "schema_integrator") else {}
            )
        except Exception:
            schema_state = {}
        return {
            "enabled": True,
            "working_memory_ids": wm_ids,
            "td_values": td_state,
            "schemas": schema_state,
        }

    # ----- knowledge-base ingest ----------------------------------------

    @app.post("/api/ingest/file")
    async def ingest_file(
        file: UploadFile = File(...),
        also_episodic: bool = Form(False),
    ) -> Dict[str, Any]:
        """Multipart file upload. Spills the body to a temp file so
        Docling (which expects a path) can parse it. Returns the
        ``ingest_id`` immediately; ingestion runs in a background thread
        so the response is non-blocking.
        """
        import tempfile
        import threading

        suffix = Path(file.filename or "upload").suffix or ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        ingester = _get_ingester()

        def _run() -> None:
            try:
                ingester.ingest_file(tmp_path, also_episodic=also_episodic)
            except Exception:  # already logged + recorded by the ingester
                pass
            finally:
                try:
                    Path(tmp_path).unlink()
                except OSError:
                    pass

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return {
            "status": "queued",
            "filename": file.filename,
            "tmp_path": tmp_path,
            "also_episodic": also_episodic,
        }

    @app.get("/api/ingest")
    def list_ingest_jobs(limit: int = Query(50, ge=1, le=1000)) -> Dict[str, Any]:
        jobs = default_ingest_log.list(limit=limit)
        return {"jobs": [j.to_dict() for j in jobs], "count": len(jobs)}

    # IMPORTANT: this static route MUST be declared before
    # /api/ingest/{job_id} so FastAPI's path-matching gives it priority
    # over the dynamic id capture (otherwise "parsers" matches as a
    # job_id and never reaches this handler).
    @app.get("/api/ingest/parsers")
    def list_parsers() -> Dict[str, Any]:
        from neuromem.core.ingest.registry import supported_suffixes

        return {"suffixes": list(supported_suffixes())}

    @app.get("/api/ingest/{job_id}")
    def get_ingest_job(job_id: str) -> Dict[str, Any]:
        job = default_ingest_log.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job.to_dict()

    @app.delete("/api/ingest/{job_id}")
    def cancel_ingest_job(job_id: str) -> Dict[str, str]:
        ok = default_ingest_log.cancel(job_id)
        if not ok:
            raise HTTPException(status_code=404, detail="job not running")
        return {"status": "cancelled", "id": job_id}

    @app.get("/api/ingest/stream/{job_id}")
    async def stream_ingest_job(job_id: str) -> StreamingResponse:
        return StreamingResponse(_sse_ingest_stream(job_id), media_type="text/event-stream")

    # ----- MCP setup -----------------------------------------------------

    @app.get("/api/mcp-config")
    def mcp_config() -> Dict[str, Any]:
        public_path = Path.home() / ".neuromem" / "mcp-public.json"
        if public_path.exists():
            return {
                "tunnel": True,
                "public_url_path": str(public_path),
                "blobs": json.loads(public_path.read_text()),
            }
        return {
            "tunnel": False,
            "hint": (
                "Run `python -m neuromem.mcp --transport http --port 7799 --public` "
                "to expose this server to web-chat clients."
            ),
            "blobs": {
                "claude_code": {
                    "command": "python",
                    "args": ["-m", "neuromem.mcp"],
                    "transport": "stdio",
                },
            },
        }

    # ----- static SPA ---------------------------------------------------

    if WEB_DIR.exists() and any(WEB_DIR.iterdir()):
        app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="ui")
    else:

        @app.get("/")
        def _placeholder() -> Dict[str, str]:
            return {
                "status": "ok",
                "message": (
                    "NeuroMem UI backend is live. The frontend SPA is not built yet — "
                    "run `npm run build` inside the `ui/` directory to populate "
                    f"{WEB_DIR}."
                ),
            }

    return app


# ---------- SSE helpers ------------------------------------------------------


async def _sse_retrieval_stream() -> AsyncIterator[bytes]:
    """SSE stream that yields each completed retrieval run as JSON.

    Bridges the synchronous subscriber callback into asyncio via a
    bounded queue. Drops oldest events on slow consumers (back-pressure).
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    loop = asyncio.get_event_loop()

    def _on_run(run: RetrievalRun) -> None:
        try:
            loop.call_soon_threadsafe(queue.put_nowait, run)
        except Exception:
            pass

    unsubscribe = default_retrieval_log.subscribe(_on_run)
    try:
        yield b": connected\n\n"
        while True:
            run = await queue.get()
            payload = json.dumps(run.to_dict())
            chunk = "event: run\ndata: " + payload + "\n\n"
            yield chunk.encode("utf-8")
    finally:
        unsubscribe()


async def _sse_ingest_stream(job_id: str) -> AsyncIterator[bytes]:
    """SSE stream for one ingest job's progress.

    Subscribes to the global ingest log and filters events to the
    requested job. Emits a frame on every state transition so the UI
    progress bar updates smoothly through parse → embed → write → link.
    Stream ends when ``status`` reaches a terminal state.
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
    loop = asyncio.get_event_loop()

    def _on_job(job: IngestJob) -> None:
        if job.id != job_id:
            return
        try:
            loop.call_soon_threadsafe(queue.put_nowait, job)
        except Exception:
            pass

    unsubscribe = default_ingest_log.subscribe(_on_job)
    try:
        # Initial snapshot — caller may connect mid-job.
        snap = default_ingest_log.get(job_id)
        if snap is None:
            yield b'event: error\ndata: {"error":"job not found"}\n\n'
            return
        first = "event: progress\ndata: " + json.dumps(snap.to_dict()) + "\n\n"
        yield first.encode("utf-8")
        if snap.status not in ("running",):
            return

        while True:
            job = await queue.get()
            payload = json.dumps(job.to_dict())
            chunk = "event: progress\ndata: " + payload + "\n\n"
            yield chunk.encode("utf-8")
            if job.status in ("completed", "errored", "cancelled"):
                return
    finally:
        unsubscribe()


async def _sse_observation_stream() -> AsyncIterator[bytes]:
    queue: asyncio.Queue = asyncio.Queue(maxsize=500)
    loop = asyncio.get_event_loop()

    def _on_event(ev: ObservationEvent) -> None:
        try:
            loop.call_soon_threadsafe(queue.put_nowait, ev)
        except Exception:
            pass

    unsubscribe = default_observation_log.subscribe(_on_event)
    try:
        yield b": connected\n\n"
        while True:
            ev = await queue.get()
            payload = json.dumps(ev.to_dict())
            chunk = "event: observation\ndata: " + payload + "\n\n"
            yield chunk.encode("utf-8")
    finally:
        unsubscribe()


__all__ = ["create_app"]
