"""
``neuromem ui`` CLI launcher.

Usage::

    neuromem ui                              # 127.0.0.1:7777, default config
    neuromem ui --port 8888
    neuromem ui --config ./prod.yaml
    neuromem ui --user user_42
    neuromem ui --verbose                    # show uvicorn access logs

Spawns uvicorn with the FastAPI app from :mod:`neuromem.ui.server`.
Static SPA bundle (built by ``cd ui && npm run build``) is served from
the same origin.

User identity resolution (Strategy B — mint + warn + persist):

1. ``--user <id>`` flag wins outright.
2. Otherwise, read ``neuromem.user.id`` from yaml.
3. If yaml lacks ``user.id`` (legacy v0.4.6-and-earlier installs), mint a
   new UUID, persist it to yaml, and print a warning so the user knows
   their old ``user_id="default"`` data is now orphaned.
4. ``NEUROMEM_USER_ID`` env var as a final override (CI, Docker).

The literal string ``"default"`` is never used — the v0.4.6 user-store
validator rejects it on POST /api/memories.
"""

from __future__ import annotations

import argparse
import os
import uuid
from pathlib import Path
from typing import Optional

from neuromem.utils.logging import get_logger

logger = get_logger(__name__)


def _quiet_uvicorn_log_config() -> dict:
    """Suppress uvicorn.access INFO spam; keep uvicorn.error at INFO so
    bind failures still surface. Mirrors the n8n / inngest dev-server
    log volume — banner + ready line, no per-request noise.
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(message)s",
                "use_colors": None,
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "WARNING", "propagate": False},
            "uvicorn.error": {"level": "WARNING"},
            "uvicorn.access": {"handlers": ["default"], "level": "WARNING", "propagate": False},
        },
    }


def _resolve_user_id(config_path: str, cli_user: Optional[str]) -> str:
    """Resolve the active user_id following Strategy B.

    Order of precedence:
        1. ``--user`` flag (only if non-empty and not the literal "default")
        2. yaml ``neuromem.user.id``
        3. ``NEUROMEM_USER_ID`` env var (still rejected if "default")
        4. Mint + persist + warn
    """
    if cli_user and cli_user != "default":
        return cli_user

    yaml_user = _read_yaml_user_id(config_path)
    if yaml_user:
        return yaml_user

    env_user = os.environ.get("NEUROMEM_USER_ID")
    if env_user and env_user != "default":
        return env_user

    minted = str(uuid.uuid4())
    _persist_user_id(config_path, minted)
    print(
        "  ⚠  Legacy yaml detected — minted user.id="
        f"{minted}\n"
        "     Old memories under user_id='default' (if any) are orphaned.\n"
        f"     Set NEUROMEM_USER_ID={minted} in any legacy scripts.\n"
    )
    return minted


def _read_yaml_user_id(config_path: str) -> Optional[str]:
    path = Path(config_path)
    if not path.exists():
        return None
    try:
        from neuromem.config_schema import ConfigService

        cfg = ConfigService(path).load()
        uid = cfg.user.id
        return uid if uid and uid != "default" else None
    except Exception:
        return None


def _persist_user_id(config_path: str, user_id: str) -> None:
    """Add ``neuromem.user.id`` to yaml without rewriting other keys.

    Going through ``ConfigService.update`` would materialize every
    schema default (auth.secret_env, async queue sizes, etc.) into the
    user's yaml — turning a 10-line file into a 60-line file on every
    launch. Instead we do a minimal yaml-level merge that preserves
    exactly what the user wrote.
    """
    path = Path(config_path)
    if not path.exists():
        return
    try:
        import yaml

        with path.open("r") as f:
            doc = yaml.safe_load(f) or {}
        nm = doc.setdefault("neuromem", {})
        user = nm.setdefault("user", {})
        user["id"] = user_id
        with path.open("w") as f:
            yaml.safe_dump(doc, f, default_flow_style=False, sort_keys=False)
    except Exception as exc:
        logger.warning("Could not persist user.id to %s: %s", path, exc)


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
        default=None,
        help="User ID for memory scoping (default: read from yaml, mint UUID if absent)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=7777, help="Bind port (default: 7777)")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn auto-reload (development).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show uvicorn per-request access logs (default: quiet).",
    )

    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "uvicorn is required for the UI. Install with `pip install 'neuromem-sdk[ui]'`."
        ) from exc

    user_id = _resolve_user_id(args.config, args.user)

    # Pin the resolved identity into env so the in-process MCP lifespan
    # (mcp/server.py reads NEUROMEM_USER_ID) doesn't fall back to the
    # legacy literal "default". Same for the config path — the MCP
    # sub-app builds its own NeuroMem from yaml, and we want it to use
    # the exact same yaml the UI just loaded.
    os.environ["NEUROMEM_USER_ID"] = user_id
    os.environ["NEUROMEM_CONFIG"] = args.config

    from neuromem import NeuroMem
    from neuromem.ui.server import create_app

    memory = NeuroMem.from_config(args.config, user_id=user_id)
    app = create_app(memory)

    print()
    print(f"  NeuroMem  →  http://{args.host}:{args.port}")
    print(f"  MCP       →  http://{args.host}:{args.port}/mcp")
    print()
    print("  Press Ctrl+C to stop.")
    print()

    if args.verbose:
        print(f"  Config:        {args.config}")
        print(f"  User:          {user_id}")
        print(f"  Brain:         {'enabled' if memory.controller.brain else 'disabled'}")
        print()

    log_config = None if args.verbose else _quiet_uvicorn_log_config()
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_config=log_config,
        access_log=args.verbose,
    )


if __name__ == "__main__":
    main()
