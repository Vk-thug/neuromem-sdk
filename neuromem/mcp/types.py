"""
Pydantic models for MCP tool inputs/outputs and serialization helpers.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from neuromem.core.types import MemoryItem, MemoryType


def serialize_memory(item: MemoryItem) -> Dict[str, Any]:
    """
    Convert a MemoryItem to a JSON-safe dict for MCP responses.

    Excludes the embedding field (too large) and converts datetimes to ISO 8601.
    """
    memory_type = item.memory_type
    if isinstance(memory_type, MemoryType):
        memory_type = memory_type.value

    result: Dict[str, Any] = {
        "id": item.id,
        "content": item.content,
        "memory_type": memory_type,
        "salience": round(item.salience, 4),
        "confidence": round(item.confidence, 4),
        "tags": item.tags or [],
        "created_at": _format_datetime(item.created_at),
        "last_accessed": _format_datetime(item.last_accessed),
        "strength": round(item.strength, 4),
        "reinforcement": item.reinforcement,
        "decay_rate": round(item.decay_rate, 6),
        "inferred": item.inferred,
        "editable": item.editable,
    }

    # Include metadata (minus embedding-related keys)
    if item.metadata:
        cleaned = {k: v for k, v in item.metadata.items() if k != "embedding"}
        if cleaned:
            result["metadata"] = cleaned

    # Include expanded_context if present
    expanded = (item.metadata or {}).get("expanded_context")
    if expanded:
        result["expanded_context"] = expanded

    return result


def serialize_memory_list(items: List[MemoryItem]) -> List[Dict[str, Any]]:
    """Serialize a list of MemoryItems."""
    return [serialize_memory(item) for item in items]


def _format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime as ISO 8601 string, handling None."""
    if dt is None:
        return None
    return dt.isoformat()
