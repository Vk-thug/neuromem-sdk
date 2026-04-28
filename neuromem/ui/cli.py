"""
``neuromem ui`` CLI launcher.

Usage::

    neuromem ui                              # 127.0.0.1:7777, default config
    neuromem ui --port 8888
    neuromem ui --config ./prod.yaml
    neuromem ui --user user_42

Spawns uvicorn with the FastAPI app from :mod:`neuromem.ui.server`.
Static SPA bundle (built by ``cd ui && npm run build``) is served from
the same origin.
"""

from __future__ import annotations

import argparse
import os

from neuromem.utils.logging import get_logger

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="neuromem ui",
        description="NeuroMem local UI — knowledge graph, retrieval inspector, MCP setup.",
    )
    parser.add_argument(
        "--config",
        default=os.environ.get("NEUROMEM_CONFIG", "neuromem.yaml"),
        help="Path to neuromem.yaml (default: env NEUROMEM_CONFIG or ./neuromem.yaml)",
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("NEUROMEM_USER_ID", "default"),
        help="User ID for memory scoping (default: env NEUROMEM_USER_ID or 'default')",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=7777, help="Bind port (default: 7777)")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn auto-reload (development).",
    )

    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "uvicorn is required for the UI. Install with `pip install 'neuromem-sdk[ui]'`."
        ) from exc

    from neuromem import NeuroMem
    from neuromem.ui.server import create_app

    memory = NeuroMem.from_config(args.config, user_id=args.user)
    app = create_app(memory)

    print(f"\n  NeuroMem UI →  http://{args.host}:{args.port}\n")
    print(f"  Config:        {args.config}")
    print(f"  User:          {args.user}")
    print(f"  Brain:         {'enabled' if memory.controller.brain else 'disabled'}\n")

    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
