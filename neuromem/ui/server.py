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

    # Pre-load config so the MCP sub-app (if enabled) can be built BEFORE
    # FastAPI construction — its session manager's task group lives inside
    # the parent app's lifespan, so we have to know about it at that
    # moment.  Bug-fix v0.4.7: prior code mounted MCP after app creation
    # but never ran its lifespan, producing 500 "Task group is not
    # initialized" on every request.
    _mcp_app = None
    _mcp_session_manager = None
    _mcp_mount_path = "/mcp"
    try:
        from neuromem.config_schema import ConfigService as _CS
        import os as _os_pre

        _pre_cfg_path = _os_pre.environ.get("NEUROMEM_CONFIG", "neuromem.yaml")
        _pre_cfg = _CS(_pre_cfg_path).load_or_default()
    except Exception:
        _pre_cfg = None

    if _pre_cfg is not None and getattr(_pre_cfg, "mcp", None) and _pre_cfg.mcp.enabled:
        try:
            from neuromem.mcp.server import create_server as _create_mcp_server

            _mcp_pre = _create_mcp_server()
            if _pre_cfg.mcp.expose_as == "sse":
                _mcp_pre.settings.sse_path = "/"
                _mcp_app = _mcp_pre.sse_app()
            else:
                _mcp_pre.settings.streamable_http_path = "/"
                _mcp_app = _mcp_pre.streamable_http_app()
            _mcp_session_manager = _mcp_pre.session_manager
            _mcp_mount_path = _pre_cfg.mcp.mount_path
        except ImportError as _exc:
            logger.warning(
                "mcp.enabled=true but [mcp] extra not installed; skipping mount: %s", _exc
            )
        except Exception as _exc:  # pragma: no cover - defensive
            logger.warning("MCP pre-build failed: %s", _exc)

    if _mcp_session_manager is not None:
        from contextlib import asynccontextmanager as _acm

        @_acm
        async def _combined_lifespan(_app: FastAPI):
            # Run the FastMCP session manager for the lifetime of the
            # parent app. This is what lets every mounted MCP request
            # reuse the same task group / event loop.
            async with _mcp_session_manager.run():
                yield

        app = FastAPI(
            title="NeuroMem UI",
            version="0.4.7",
            description="Local brain-inspired memory dashboard.",
            lifespan=_combined_lifespan,
        )
    else:
        app = FastAPI(
            title="NeuroMem UI",
            version="0.4.7",
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

    # In-process MCP mount (v0.4.7). The sub-app + session manager were
    # pre-built above so the lifespan could be wired in at FastAPI
    # construction time. Here we just attach the mount and a courtesy
    # ``/mcp`` → ``/mcp/`` redirect route so URLs without a trailing slash
    # don't 404 (Starlette's Mount won't match a bare prefix).
    if _mcp_app is not None:
        from fastapi.responses import RedirectResponse as _Redirect

        _mp = _mcp_mount_path.rstrip("/")

        @app.get(_mp, include_in_schema=False)
        async def _mcp_slash_redirect():
            return _Redirect(url=f"{_mp}/", status_code=307)

        app.mount(_mp, _mcp_app)
        logger.info("MCP mounted in-process at %s/", _mp)

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
        from neuromem import __version__ as _nm_version

        controller = memory.controller
        graph = controller.graph
        return {
            "status": "ok",
            "version": _nm_version,
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
        try:
            memory.forget(memory_id)
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {"status": "deleted", "id": memory_id}

    @app.post("/api/memories")
    def add_memory(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Explicit add — wraps NeuroMem.observe with a one-sided
        observation. Used by the UI's 'New memory' button.

        Returns the new memory's id so the caller can immediately link,
        edit, or delete the record without an extra LIST round-trip.
        """
        raw_content = payload.get("content")
        if raw_content is None:
            raise HTTPException(status_code=400, detail="content is required")
        if not isinstance(raw_content, str):
            raise HTTPException(
                status_code=422,
                detail=f"content must be a string, got {type(raw_content).__name__}",
            )
        content = raw_content.strip()
        if not content:
            raise HTTPException(status_code=400, detail="content is required")
        metadata = dict(payload.get("metadata") or {})
        if payload.get("belief_state") is not None:
            metadata["belief_state"] = int(payload["belief_state"])

        # observe() requires a non-empty assistant_output. The UI's
        # "New memory" flow has nothing meaningful to fill in, so we
        # default to a placeholder rather than 500-ing.
        assistant_output = (payload.get("assistant_output") or "").strip() or "(observed)"

        try:
            memory.observe(
                user_input=content,
                assistant_output=assistant_output,
                template=payload.get("template"),
                metadata=metadata,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        # Best-effort id surfacing: list latest 1 by recency for this user.
        new_id: Optional[str] = None
        try:
            latest = memory.list(limit=1)
            if latest:
                new_id = getattr(latest[0], "id", None)
        except Exception:
            pass

        body: Dict[str, Any] = {"status": "added"}
        if new_id:
            body["id"] = new_id
        return body

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

        new_id = str(__import__("uuid").uuid4())
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

    @app.get("/api/retrievals/stream")
    async def stream_retrievals() -> StreamingResponse:
        return StreamingResponse(
            _sse_retrieval_stream(),
            media_type="text/event-stream",
        )

    @app.get("/api/retrievals/{run_id}")
    def get_retrieval(run_id: str) -> Dict[str, Any]:
        run = default_retrieval_log.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        return run.to_dict()

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
        """Ready-to-paste MCP config blobs for every supported client.

        v0.4.7: in-process MCP is the default, so we surface the local
        URL (read from the running yaml) for every client. Falls back to
        stdio command shape only for clients that demand a subprocess.
        Public-tunnel blobs (cloudflared) override the local URLs when
        ``~/.neuromem/mcp-public.json`` exists.
        """
        public_path = Path.home() / ".neuromem" / "mcp-public.json"
        if public_path.exists():
            return {
                "tunnel": True,
                "public_url_path": str(public_path),
                "blobs": json.loads(public_path.read_text()),
            }

        # Read live yaml so the URL reflects the actual port + mount path.
        try:
            from neuromem.config_schema import ConfigService as _CS
            import os as _os_mc

            _live = _CS(_os_mc.environ.get("NEUROMEM_CONFIG", "neuromem.yaml")).load_or_default()
            _ui = _live.ui
            _mp = (
                _live.mcp.mount_path
                if getattr(_live, "mcp", None) and _live.mcp.enabled
                else "/mcp"
            )
            local_url = f"http://{_ui.host}:{_ui.port}{_mp.rstrip('/')}/"
        except Exception:
            local_url = "http://127.0.0.1:7777/mcp/"

        http_blob = {"type": "http", "url": local_url}
        stdio_blob = {
            "command": "python",
            "args": ["-m", "neuromem.mcp"],
            "transport": "stdio",
        }

        return {
            "tunnel": False,
            "local_url": local_url,
            "hint": (
                f"In-process MCP is live at {local_url}. "
                "Run `neuromem ui --public` to expose it to web-chat clients via cloudflared."
            ),
            "blobs": {
                "claude_code": http_blob,
                "cursor": http_blob,
                "antigravity": http_blob,
                "gemini_cli": {"httpUrl": local_url},
                "codex_cli": http_blob,
                "cline": http_blob,
                "windsurf": http_blob,
                # Stdio fallback for hosts that can't dial localhost
                # (Docker without host-network, agent-host CLIs).
                "_stdio_fallback": stdio_blob,
            },
        }

    # ----- static SPA ---------------------------------------------------
    # SPA catch-all (v0.4.7 fix): every non-API GET that isn't a real
    # static asset must serve index.html so the React Router can hydrate.
    # The default ``StaticFiles(html=True)`` only resolves index.html on
    # directory matches — deep-links like /settings or /onboarding would
    # otherwise 404. We mount the static dir under a sub-path and add an
    # explicit catch-all GET that prefers a real file when one exists,
    # else falls back to index.html.

    # Favicon — return 204 if no asset, else serve from web/. Avoids the
    # noisy `GET /favicon.{svg,ico} 404` lines on every page load.
    from fastapi.responses import Response as _Response

    @app.get("/favicon.ico", include_in_schema=False)
    @app.get("/favicon.svg", include_in_schema=False)
    async def _favicon():
        for name in ("favicon.svg", "favicon.ico"):
            candidate = WEB_DIR / name
            if candidate.is_file():
                from fastapi.responses import FileResponse as _FR

                return _FR(candidate)
        return _Response(status_code=204)

    if WEB_DIR.exists() and any(WEB_DIR.iterdir()):
        from fastapi.responses import FileResponse as _FileResponse

        # Serve files at /assets/* etc directly (Vite emits hashed paths
        # under /assets/). Mounting at "/" still works as the primary
        # asset server; the catch-all below handles deep-link 404s.
        app.mount(
            "/assets",
            StaticFiles(directory=str(WEB_DIR / "assets")),
            name="spa-assets",
        )

        _index_html = WEB_DIR / "index.html"

        @app.get("/{full_path:path}", include_in_schema=False)
        async def _spa_catch_all(full_path: str):
            # Don't shadow API or MCP — those have explicit routes
            # registered before this catch-all, but FastAPI's matcher
            # walks routes in order and Mount catches its prefix, so
            # /api/* and /mcp/* never reach this handler.
            candidate = WEB_DIR / full_path
            if full_path and candidate.is_file():
                return _FileResponse(candidate)
            return _FileResponse(_index_html)

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
