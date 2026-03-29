"""
Self-hosted Inngest workflow server for NeuroMem.

Provides a FastAPI application that serves all NeuroMem workflow
functions and can be run standalone or embedded in an existing app.

Usage (standalone):
    python -m neuromem.workflows.server --config neuromem.yaml --user-id user_123

Usage (programmatic):
    from neuromem import NeuroMem
    from neuromem.workflows.server import create_workflow_app

    memory = NeuroMem.from_config("neuromem.yaml", user_id="user_123")
    app = create_workflow_app(memory)
    # Run: INNGEST_DEV=1 uvicorn app:app --port 8000
"""

from typing import Any, List, Optional

try:
    import inngest
    import inngest.fast_api

    INNGEST_AVAILABLE = True
except ImportError:
    INNGEST_AVAILABLE = False

try:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from neuromem.utils.logging import get_logger

logger = get_logger(__name__)


def create_workflow_app(
    neuromem_instance: Any = None,
    functions: Optional[List[Any]] = None,
    app_id: str = "neuromem",
    is_production: bool = False,
    serve_path: str = "/api/inngest",
) -> Any:
    """
    Create a FastAPI application with Inngest workflow endpoints.

    Args:
        neuromem_instance: Initialized NeuroMem instance.
            Required if functions is None.
        functions: Pre-created Inngest functions (from create_neuromem_workflows).
            If None, creates them from neuromem_instance.
        app_id: Inngest application identifier
        is_production: Enable production mode
        serve_path: URL path for Inngest endpoint

    Returns:
        FastAPI application instance

    Raises:
        ImportError: If FastAPI or Inngest are not installed

    Example:
        >>> from neuromem import NeuroMem
        >>> from neuromem.workflows.server import create_workflow_app
        >>>
        >>> memory = NeuroMem.from_config("neuromem.yaml", user_id="user_123")
        >>> app = create_workflow_app(memory)
        >>>
        >>> # Start: INNGEST_DEV=1 uvicorn module:app --port 8000
        >>> # Dev server: npx inngest-cli@latest dev -u http://127.0.0.1:8000/api/inngest --no-discovery
    """
    if not INNGEST_AVAILABLE:
        raise ImportError(
            "Inngest is not installed. Install with: pip install neuromem-sdk[inngest]"
        )
    if not FASTAPI_AVAILABLE:
        raise ImportError(
            "FastAPI is not installed. Install with: pip install neuromem-sdk[inngest]"
        )

    # Create or use provided functions
    if functions is None:
        if neuromem_instance is None:
            raise ValueError("Either neuromem_instance or functions must be provided")

        from neuromem.workflows.client import create_neuromem_workflows

        functions = create_neuromem_workflows(
            neuromem_instance, app_id=app_id, is_production=is_production
        )

    from neuromem.workflows.client import get_inngest_client

    client = get_inngest_client(app_id=app_id, is_production=is_production)

    # Create FastAPI app
    app = FastAPI(
        title="NeuroMem Workflow Server",
        description="Inngest-powered durable workflows for NeuroMem memory operations",
        version="0.2.0",
    )

    # Health endpoint
    @app.get("/health")
    def health() -> dict:
        return {
            "status": "healthy",
            "service": "neuromem-workflows",
            "functions_registered": len(functions),
        }

    # List registered functions
    @app.get("/workflows")
    def list_workflows() -> dict:
        fn_list = []
        for fn in functions:
            fn_info = {"id": getattr(fn, "id", str(fn))}
            fn_list.append(fn_info)
        return {"functions": fn_list, "count": len(fn_list)}

    # Manual trigger endpoint — send events programmatically
    @app.post("/trigger/{event_name}")
    async def trigger_event(event_name: str, data: dict = None) -> dict:
        """Trigger a NeuroMem workflow event manually."""
        if data is None:
            data = {}
        try:
            event_ids = client.send_sync(inngest.Event(name=event_name, data=data))
            return {"status": "triggered", "event_name": event_name, "event_ids": event_ids}
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "error": str(e)[:200]},
            )

    # Register Inngest endpoint
    inngest.fast_api.serve(app, client, functions)

    logger.info(
        "NeuroMem workflow server created",
        extra={
            "functions": len(functions),
            "serve_path": serve_path,
        },
    )

    return app


def run_server(
    config_path: str = "neuromem.yaml",
    user_id: str = "default",
    host: str = "0.0.0.0",
    port: int = 8000,
    app_id: str = "neuromem",
) -> None:
    """
    Run the workflow server standalone.

    Args:
        config_path: Path to neuromem.yaml
        user_id: User ID for the NeuroMem instance
        host: Server host
        port: Server port
        app_id: Inngest application identifier
    """
    import uvicorn
    from neuromem import NeuroMem

    logger.info(
        "Starting NeuroMem workflow server",
        extra={"config_path": config_path, "user_id": user_id, "port": port},
    )

    memory = NeuroMem.from_config(config_path, user_id=user_id)
    app = create_workflow_app(memory, app_id=app_id)

    uvicorn.run(app, host=host, port=port)


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NeuroMem Workflow Server")
    parser.add_argument("--config", default="neuromem.yaml", help="Config file path")
    parser.add_argument("--user-id", default="default", help="User ID")
    parser.add_argument("--host", default="0.0.0.0", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument("--app-id", default="neuromem", help="Inngest app ID")
    args = parser.parse_args()

    run_server(
        config_path=args.config,
        user_id=args.user_id,
        host=args.host,
        port=args.port,
        app_id=args.app_id,
    )
