"""Storage backends module initialization."""

from neuromem.storage.base import MemoryBackend
from neuromem.storage.memory import InMemoryBackend

# Optional backends — only import if dependencies are installed
try:
    from neuromem.storage.postgres import PostgresBackend
except ImportError:
    PostgresBackend = None  # type: ignore

try:
    from neuromem.storage.sqlite import SQLiteBackend
except ImportError:
    SQLiteBackend = None  # type: ignore

try:
    from neuromem.storage.qdrant import QdrantStorage
except ImportError:
    QdrantStorage = None  # type: ignore

__all__ = [
    "MemoryBackend",
    "InMemoryBackend",
    "PostgresBackend",
    "SQLiteBackend",
    "QdrantStorage",
]
