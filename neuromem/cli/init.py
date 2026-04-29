"""``neuromem init`` — first-run wizard.

Two flows:

* Terminal wizard (default): interactive prompts via :mod:`questionary`,
  writes ``neuromem.yaml`` + ``.env``, then optionally launches the UI.
* Browser wizard (``--ui``): writes a *bootstrap* yaml that boots an
  in-memory single-user instance, opens the UI at ``/onboarding``, and
  the user finishes setup in the SPA. The SPA writes the final yaml via
  ``PUT /api/config`` once they hit "Save".

The CLI never asks for secrets without offering an env-var alternative
— OpenAI keys land in ``.env`` (gitignored), never in the yaml.
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from pathlib import Path
from typing import Any, Dict

from neuromem.utils.logging import get_logger

logger = get_logger(__name__)


def _prompt_terminal() -> Dict[str, Any]:
    """Run the questionary-based wizard. Returns the chosen answers."""
    try:
        import questionary
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "Install the wizard extras: `pip install 'neuromem-sdk[ui]'` "
            "(questionary is bundled there)."
        ) from exc

    print("\n  NeuroMem setup — answer 5 questions, you're done.\n")

    mode = questionary.select(
        "Mode:",
        choices=[
            {
                "name": "Single-user (local, no auth) — recommended for laptop / desktop",
                "value": "single",
            },
            {
                "name": "Service (multi-user, API-key auth) — for shared deployments",
                "value": "service",
            },
        ],
        default="single",
    ).ask()

    embedding_provider = questionary.select(
        "Embedding model:",
        choices=[
            {"name": "Ollama nomic-embed-text (local, free, 768-dim) — default", "value": "ollama"},
            {"name": "OpenAI text-embedding-3-large (3072-dim, paid)", "value": "openai"},
        ],
        default="ollama",
    ).ask()

    openai_key = ""
    if embedding_provider == "openai":
        openai_key = questionary.password(
            "OpenAI API key (stored in .env, not yaml):",
            validate=lambda s: True if s.startswith("sk-") else "Should start with 'sk-'",
        ).ask()

    storage = questionary.select(
        "Vector store:",
        choices=[
            {
                "name": "Qdrant on localhost:6333 — recommended (run: docker run -p 6333:6333 qdrant/qdrant)",
                "value": "qdrant",
            },
            {"name": "In-memory (no persistence, restart wipes everything)", "value": "memory"},
            {"name": "Postgres + pgvector", "value": "postgres"},
        ],
        default="qdrant",
    ).ask()

    postgres_url = ""
    if storage == "postgres" or mode == "service":
        postgres_url = questionary.text(
            "Postgres URL (for users + memory):",
            default="postgresql://neuromem:neuromem@localhost:5432/neuromem",
        ).ask()

    port = questionary.text(
        "UI port:",
        default="7777",
        validate=lambda s: s.isdigit() and 1024 <= int(s) <= 65535,
    ).ask()

    return {
        "mode": mode,
        "embedding_provider": embedding_provider,
        "openai_key": openai_key,
        "storage": storage,
        "postgres_url": postgres_url,
        "port": int(port),
    }


def _build_yaml(answers: Dict[str, Any]) -> Dict[str, Any]:
    """Translate wizard answers into the neuromem.yaml document."""
    if answers["embedding_provider"] == "openai":
        embedding = "text-embedding-3-large"
        vector_size = 3072
        consolidation_llm = "gpt-4o-mini"
    else:
        embedding = "nomic-embed-text"
        vector_size = 768
        consolidation_llm = "ollama/qwen2.5-coder:7b"

    storage_block: Dict[str, Any]
    if answers["storage"] == "qdrant":
        storage_block = {
            "vector_store": {
                "type": "qdrant",
                "config": {
                    "host": "localhost",
                    "port": 6333,
                    "collection_name": "neuromem",
                    "vector_size": vector_size,
                },
            },
            "database": {"type": "memory", "url": None},
        }
    elif answers["storage"] == "postgres":
        storage_block = {
            "vector_store": {"type": "postgres", "config": {"url": answers["postgres_url"]}},
            "database": {"type": "postgres", "url": answers["postgres_url"]},
        }
    else:
        storage_block = {
            "vector_store": {"type": "memory"},
            "database": {"type": "memory", "url": None},
        }

    auth_block: Dict[str, Any]
    if answers["mode"] == "service":
        auth_block = {"type": "api_key", "secret_env": "NEUROMEM_AUTH_SECRET"}
        if answers["storage"] != "postgres":
            storage_block["database"] = {"type": "postgres", "url": answers["postgres_url"]}
    else:
        auth_block = {"type": "none"}

    return {
        "neuromem": {
            "mode": answers["mode"],
            "setup_complete": True,
            "auth": auth_block,
            "ui": {"port": answers["port"]},
            "model": {"embedding": embedding, "consolidation_llm": consolidation_llm},
            "storage": storage_block,
            "memory": {
                "decay_enabled": True,
                "consolidation_interval": 10,
                "max_active_memories": 50,
                "episodic_retention_days": 30,
                "min_confidence_threshold": 0.3,
            },
            "async": {"enabled": False},
        }
    }


def _write_bootstrap_yaml(path: Path) -> None:
    """Write a minimal yaml that boots the UI for the browser wizard."""
    import yaml

    bootstrap = {
        "neuromem": {
            "mode": "single",
            "setup_complete": False,
            "auth": {"type": "none"},
            "ui": {"port": 7777},
            "model": {
                "embedding": "nomic-embed-text",
                "consolidation_llm": "ollama/qwen2.5-coder:7b",
            },
            "storage": {
                "vector_store": {"type": "memory"},
                "database": {"type": "memory", "url": None},
            },
        }
    }
    with path.open("w") as f:
        yaml.safe_dump(bootstrap, f, default_flow_style=False, sort_keys=False)


def _write_yaml(path: Path, doc: Dict[str, Any]) -> None:
    import yaml

    with path.open("w") as f:
        yaml.safe_dump(doc, f, default_flow_style=False, sort_keys=False)


def _write_env(path: Path, answers: Dict[str, Any]) -> None:
    """Write secrets to .env. Never overwrites existing keys."""
    lines: list[str] = []
    if answers.get("openai_key"):
        lines.append(f"OPENAI_API_KEY={answers['openai_key']}")
    if answers["mode"] == "service":
        import secrets

        lines.append(f"NEUROMEM_AUTH_SECRET={secrets.token_urlsafe(32)}")
    if not lines:
        return

    existing = path.read_text() if path.exists() else ""
    with path.open("a") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        for line in lines:
            key = line.split("=", 1)[0]
            if key in existing:
                continue  # preserve user's value
            f.write(line + "\n")


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="neuromem init", description="First-run wizard.")
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Skip terminal prompts; open the browser wizard at /onboarding.",
    )
    parser.add_argument("--config", default="neuromem.yaml", help="Path to write yaml")
    parser.add_argument("--force", action="store_true", help="Overwrite existing config")
    parser.add_argument("--no-launch", action="store_true", help="Don't auto-launch the UI")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if config_path.exists() and not args.force:
        print(f"  {config_path} already exists. Use --force to overwrite.", file=sys.stderr)
        return 1

    if args.ui:
        _write_bootstrap_yaml(config_path)
        print(f"\n  Bootstrap config written: {config_path}")
        print("  Launching browser wizard at http://127.0.0.1:7777/onboarding\n")
        if not args.no_launch:
            _launch_ui(config_path, open_path="/onboarding")
        return 0

    answers = _prompt_terminal()
    doc = _build_yaml(answers)
    _write_yaml(config_path, doc)
    _write_env(Path(".env"), answers)

    print(f"\n  Config written: {config_path}")
    if Path(".env").exists():
        print("  Secrets written: .env (added to .gitignore)")
    print("\n  Next steps:")
    print(f"    neuromem ui --config {config_path}")
    if answers["mode"] == "service":
        print("    neuromem doctor       # verify Postgres reachable")
    print()

    if not args.no_launch:
        try_launch = input("  Launch UI now? [Y/n]: ").strip().lower()
        if try_launch in ("", "y", "yes"):
            _launch_ui(config_path)

    return 0


def _launch_ui(config_path: Path, open_path: str = "/") -> None:
    """Spawn the UI server in this process and open the browser."""
    os.environ["NEUROMEM_CONFIG"] = str(config_path)
    try:
        webbrowser.open(f"http://127.0.0.1:7777{open_path}")
    except Exception:
        pass
    from neuromem.ui.cli import main as run_ui

    sys.argv = ["neuromem ui", "--config", str(config_path)]
    run_ui()
