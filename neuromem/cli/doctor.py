"""``neuromem doctor`` — health check for Ollama / Qdrant / Postgres."""

from __future__ import annotations

import argparse
import socket
import sys
from typing import Tuple


def _check_tcp(host: str, port: int, timeout: float = 2.0) -> Tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"reachable on {host}:{port}"
    except OSError as exc:
        return False, f"unreachable on {host}:{port} ({exc})"


def _check_ollama(host: str = "localhost", port: int = 11434) -> Tuple[bool, str]:
    return _check_tcp(host, port)


def _check_qdrant(host: str, port: int) -> Tuple[bool, str]:
    return _check_tcp(host, port)


def _check_postgres(url: str) -> Tuple[bool, str]:
    try:
        import psycopg2
    except ImportError:
        return False, "psycopg2 not installed (pip install 'neuromem-sdk[postgres]')"
    try:
        conn = psycopg2.connect(url, connect_timeout=3)
        conn.close()
        return True, "connected"
    except Exception as exc:
        return False, f"connect failed: {exc}"


def _check_sqlite(url: str) -> Tuple[bool, str]:
    import sqlite3
    from pathlib import Path

    raw = url
    if raw.startswith("sqlite:///"):
        raw = raw[len("sqlite:///") :]
    elif raw.startswith("sqlite://"):
        raw = raw[len("sqlite://") :]

    path = Path(raw).expanduser()
    try:
        conn = sqlite3.connect(str(path))
        conn.execute("SELECT 1")
        conn.close()
        return True, f"opened {path}"
    except Exception as exc:
        return False, f"open failed: {exc}"


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="neuromem doctor")
    parser.add_argument("--config", default="neuromem.yaml")
    args = parser.parse_args(argv)

    from neuromem.config_schema import ConfigService

    cfg = ConfigService(args.config).load()

    print("\n  NeuroMem doctor\n")
    print(f"  Mode:           {cfg.mode}")
    print(f"  Embedding:      {cfg.model.embedding}")
    print(f"  Vector store:   {cfg.storage.vector_store.type}")
    print()

    failures = 0

    if cfg.model.embedding.startswith(("nomic", "ollama/")) or any(
        cfg.model.consolidation_llm.startswith(p)
        for p in ("ollama/", "qwen", "llama", "mistral", "gpt-oss")
    ):
        ok, msg = _check_ollama()
        print(f"  Ollama:         {'OK ' if ok else 'FAIL '} {msg}")
        failures += 0 if ok else 1

    if cfg.storage.vector_store.type == "qdrant":
        host = cfg.storage.vector_store.config.get("host", "localhost")
        port = int(cfg.storage.vector_store.config.get("port", 6333))
        ok, msg = _check_qdrant(host, port)
        print(f"  Qdrant:         {'OK ' if ok else 'FAIL '} {msg}")
        failures += 0 if ok else 1

    db = cfg.storage.database
    if db and db.type == "postgres" and db.url:
        ok, msg = _check_postgres(db.url)
        print(f"  Postgres:       {'OK ' if ok else 'FAIL '} {msg}")
        failures += 0 if ok else 1

    if db and db.type == "sqlite" and db.url:
        ok, msg = _check_sqlite(db.url)
        print(f"  SQLite:         {'OK ' if ok else 'FAIL '} {msg}")
        failures += 0 if ok else 1

    print()
    if failures:
        print(f"  {failures} check(s) failed.\n", file=sys.stderr)
        return 1
    print("  All checks passed.\n")
    return 0
