"""
NeuroMem MCP Server package.

Exposes NeuroMem's brain-inspired memory system via the Model Context Protocol (MCP).
Compatible with Claude Code, Cline, Cursor, Codex CLI, Gemini CLI, and more.

Usage:
    python -m neuromem.mcp                          # stdio transport (default)
    python -m neuromem.mcp --transport http          # HTTP transport
    python -m neuromem.mcp --transport http --port 8000
"""

from neuromem.mcp.server import create_server

__all__ = ["create_server"]
