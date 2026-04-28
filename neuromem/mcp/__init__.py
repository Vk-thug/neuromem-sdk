"""
NeuroMem MCP Server package.

Exposes NeuroMem's brain-inspired memory system via the Model Context Protocol (MCP).
Compatible with Claude Code, Cline, Cursor, Codex CLI, Gemini CLI, Antigravity, and more.

Usage:
    python -m neuromem.mcp                            # stdio transport (default)
    python -m neuromem.mcp --transport http            # HTTP transport
    python -m neuromem.mcp --transport http --port 8000
    python -m neuromem.mcp --transport http --public   # cloudflared tunnel for web-chat clients

The ``create_server`` symbol is lazy-imported so callers that only need the
tunnel helper (``neuromem.mcp.tunnel``) don't need ``mcp`` / ``FastMCP``
installed.
"""

from typing import TYPE_CHECKING, Any

__all__ = ["create_server"]


def __getattr__(name: str) -> Any:
    if name == "create_server":
        from neuromem.mcp.server import create_server as _cs

        return _cs
    raise AttributeError(f"module 'neuromem.mcp' has no attribute {name!r}")


if TYPE_CHECKING:  # pragma: no cover
    from neuromem.mcp.server import create_server  # noqa: F401
