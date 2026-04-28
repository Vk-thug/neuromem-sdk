"""
Pluggable parser registry — mirrors the shape used by
``neuromem.core.cross_encoder_reranker.register_provider``. Same
ergonomics: register a factory by name, look up by file suffix.

Why a registry rather than a hard-coded if/elif: third-party packages
(or downstream products) can ship their own parser for a custom format
(``.eml`` mailboxes, ``.ipynb`` notebooks, ``.epub`` books) without
forking NeuroMem.
"""

from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path
from typing import Callable, Dict, Optional

from neuromem.core.ingest.types import FileParser

_lock = threading.RLock()
_factories: Dict[str, Callable[[], FileParser]] = {}
_suffix_to_name: Dict[str, str] = {}


def register_parser(
    name: str, factory: Callable[[], FileParser], *, suffixes: Optional[tuple] = None
) -> None:
    """Register a parser factory under ``name``.

    ``suffixes`` overrides the parser instance's declared suffixes (used
    by tests / multi-format parsers). Subsequent registrations REPLACE —
    last-wins, so users can override built-ins by re-registering with
    the same name.
    """
    with _lock:
        _factories[name] = factory
        try:
            instance_suffixes = suffixes or factory().suffixes
        except Exception:
            # Lazy parsers (e.g. Docling) may raise at construction when
            # their optional deps aren't installed. Fall back to the
            # explicit ``suffixes`` argument; if absent, we cannot
            # populate the suffix index — registration is still useful
            # for explicit ``parser_for_name`` lookup.
            instance_suffixes = suffixes or ()
        for suffix in instance_suffixes:
            _suffix_to_name[suffix.lower()] = name


def parser_for_path(path: str) -> Optional[FileParser]:
    """Return a parser instance that handles ``path``'s suffix, or
    ``None`` if no parser is registered for it."""
    suffix = Path(path).suffix.lower()
    with _lock:
        name = _suffix_to_name.get(suffix)
        if name is None:
            return None
        factory = _factories.get(name)
    if factory is None:
        return None
    return factory()


def parser_for_name(name: str) -> Optional[FileParser]:
    """Return a parser instance by registered name."""
    with _lock:
        factory = _factories.get(name)
    return factory() if factory else None


def supported_suffixes() -> tuple:
    """All file suffixes a registered parser handles."""
    with _lock:
        return tuple(sorted(_suffix_to_name.keys()))


def compute_source_id(path: str) -> str:
    """Stable id for a source file. SHA1 of ``abspath + mtime`` so a
    re-upload of the same file at the same mtime collides — the
    ingester uses this as a dedupe key."""
    abs_path = os.path.abspath(path)
    try:
        mtime = os.path.getmtime(abs_path)
    except OSError:
        mtime = 0
    digest = hashlib.sha1(f"{abs_path}|{mtime}".encode("utf-8")).hexdigest()
    return digest[:16]


__all__ = [
    "compute_source_id",
    "parser_for_name",
    "parser_for_path",
    "register_parser",
    "supported_suffixes",
]
