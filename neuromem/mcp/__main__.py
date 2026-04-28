"""
Entry point for running NeuroMem MCP server.

Usage:
    python -m neuromem.mcp                              # stdio (default)
    python -m neuromem.mcp --transport http              # HTTP transport
    python -m neuromem.mcp --transport http --port 8000  # HTTP on custom port
    python -m neuromem.mcp --transport sse               # SSE (legacy)
    python -m neuromem.mcp --transport http --public     # HTTP + cloudflared tunnel

Environment Variables:
    NEUROMEM_CONFIG     Path to neuromem.yaml (default: ./neuromem.yaml)
    NEUROMEM_USER_ID    Default user ID (default: "default")
    OPENAI_API_KEY      Required for embeddings
"""

import argparse
import threading


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
    parser.add_argument(
        "--public",
        action="store_true",
        help=(
            "v0.4.0: expose this MCP server to the public internet via "
            "cloudflared (or ngrok fallback) so web-chat clients (Claude.ai, "
            "Gemini chat, ChatGPT) can connect. Requires --transport http."
        ),
    )
    parser.add_argument(
        "--tunnel-provider",
        choices=["cloudflared", "ngrok"],
        default="cloudflared",
        help="Tunnel provider (default: cloudflared, ngrok as fallback)",
    )

    args = parser.parse_args()

    # Defer the heavy ``create_server`` import until after ``--help``
    # has already had a chance to short-circuit. This means the
    # console script entry point is importable even when the
    # optional ``[mcp]`` extra is not installed — running
    # ``neuromem-mcp --help`` works everywhere.
    try:
        from neuromem.mcp.server import create_server
    except ImportError as exc:
        parser.exit(
            status=2,
            message=(
                f"\nneuromem-mcp requires the [mcp] extra: "
                f"`pip install 'neuromem-sdk[mcp]'`. Cause: {exc}\n"
            ),
        )

    if args.public and args.transport != "http":
        parser.error("--public requires --transport http")

    server = create_server()

    # When --public is set, start the tunnel BEFORE binding the MCP server
    # so we can print connection instructions even if the MCP server later
    # blocks the main thread. The tunnel parses the URL out of cloudflared's
    # banner, so it's a one-shot side effect.
    tunnel = None
    if args.public:
        from neuromem.mcp.tunnel import (
            TunnelError,
            format_setup_instructions,
            mcp_config_for_clients,
            persist_public_config,
            start_cloudflared,
            start_ngrok,
        )

        starter = start_cloudflared if args.tunnel_provider == "cloudflared" else start_ngrok

        # Run the MCP server in a background thread so the main thread can
        # spin up the tunnel and print the public URL. The MCP server blocks,
        # which is why we invert the usual order here.
        def _run_server() -> None:
            server.run(transport="http", host=args.host, port=args.port)

        thread = threading.Thread(target=_run_server, daemon=True)
        thread.start()

        # Brief wait for the HTTP server to bind. cloudflared probes the
        # local port immediately, so a short delay avoids spurious 502s.
        import time

        time.sleep(1.5)

        try:
            tunnel = starter(args.port)
        except TunnelError as exc:
            print(f"\n❌ Tunnel failed:\n{exc}\n")
            raise SystemExit(1)

        blobs = mcp_config_for_clients(tunnel.public_url)
        config_path = persist_public_config(blobs)
        print("\n" + format_setup_instructions(tunnel.public_url) + "\n")
        print(f"Tunnel provider: {tunnel.provider}")
        print(f"Local MCP:       http://{args.host}:{args.port}")
        print(f"Public MCP:      {tunnel.public_url}")
        print(f"Config saved:    {config_path}")
        print("\nPress Ctrl+C to stop the tunnel and the server.\n")

        # Keep main thread alive while server thread serves and tunnel runs.
        try:
            thread.join()
        except KeyboardInterrupt:
            print("\nShutting down tunnel...")
            tunnel.stop()
        return

    if args.transport == "stdio":
        server.run(transport="stdio")
    elif args.transport == "http":
        server.run(transport="http", host=args.host, port=args.port)
    elif args.transport == "sse":
        server.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
