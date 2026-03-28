"""
Entry point for running NeuroMem MCP server.

Usage:
    python -m neuromem.mcp                              # stdio (default)
    python -m neuromem.mcp --transport http              # HTTP transport
    python -m neuromem.mcp --transport http --port 8000  # HTTP on custom port
    python -m neuromem.mcp --transport sse               # SSE (legacy)

Environment Variables:
    NEUROMEM_CONFIG     Path to neuromem.yaml (default: ./neuromem.yaml)
    NEUROMEM_USER_ID    Default user ID (default: "default")
    OPENAI_API_KEY      Required for embeddings
"""

import argparse

from neuromem.mcp.server import create_server


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="neuromem-mcp",
        description="NeuroMem MCP Server — brain-inspired memory for AI agents",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to for HTTP/SSE transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP/SSE transport (default: 8000)",
    )

    args = parser.parse_args()

    server = create_server()

    if args.transport == "stdio":
        server.run(transport="stdio")
    elif args.transport == "http":
        server.run(transport="http", host=args.host, port=args.port)
    elif args.transport == "sse":
        server.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
