"""
MCP tunnel helper — exposes a local NeuroMem MCP HTTP server to the public
internet via cloudflared (preferred) or ngrok (fallback), so web-chat
clients (Claude.ai, Gemini chat, ChatGPT) that require an HTTPS-reachable
MCP endpoint can connect.

Why this exists:
* ``stdio`` transport works for local IDE clients (Claude Code, Cursor,
  Codex CLI, Gemini CLI, Antigravity).
* Web-chat clients only accept an HTTPS URL.
* Asking users to provision their own tunnel is high-friction.

This module provides:
* ``start_cloudflared(local_port)`` — spawns ``cloudflared tunnel --url
  http://localhost:<port>`` as a subprocess, parses the public URL out of
  its stdout, returns ``(public_url, process)``.
* ``mcp_config_for_clients(public_url)`` — generates ready-to-paste JSON
  blobs for Claude.ai, Gemini chat, ChatGPT (one per client).
* ``persist_public_config(blobs)`` — writes the blobs to
  ``~/.neuromem/mcp-public.json`` for re-use.

If ``cloudflared`` is not installed, raises a ``TunnelError`` with the
install command for the user's platform.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


class TunnelError(RuntimeError):
    """Raised when a tunnel cannot be established."""


# Cloudflared streams a banner like:
#   2026-04-28T10:00:00Z INF |  https://random-words-1234.trycloudflare.com  |
# We accept any https://*.trycloudflare.com URL.
_CLOUDFLARED_URL_RE = re.compile(
    r"https://[a-zA-Z0-9-]+\.trycloudflare\.com",
    re.MULTILINE,
)
# ngrok stdout format:
#   url=https://abcd-1234.ngrok-free.app
_NGROK_URL_RE = re.compile(r"url=(https://[\w.-]+\.ngrok[\w.-]+)")


@dataclass
class TunnelHandle:
    """Live tunnel process + the public URL it exposed."""

    public_url: str
    process: subprocess.Popen
    provider: str  # "cloudflared" | "ngrok"

    def stop(self, timeout: float = 5.0) -> None:
        """Terminate the tunnel subprocess. Idempotent."""
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()


def _find_binary(name: str) -> Optional[str]:
    """Return absolute path to ``name`` on PATH, or None if absent.

    Wrapped for test seam — tests can monkeypatch this.
    """
    return shutil.which(name)


def _install_hint() -> str:
    """Multi-platform cloudflared install command."""
    return (
        "Install cloudflared:\n"
        "  macOS:   brew install cloudflared\n"
        "  Linux:   https://pkg.cloudflare.com/index.html\n"
        "  Windows: winget install --id Cloudflare.cloudflared\n"
        "Or install ngrok as a fallback: https://ngrok.com/download"
    )


def start_cloudflared(
    local_port: int,
    *,
    timeout: float = 30.0,
    binary_path: Optional[str] = None,
) -> TunnelHandle:
    """Spawn a cloudflared tunnel for ``http://localhost:<port>`` and parse
    its public URL.

    Raises ``TunnelError`` if:
    * cloudflared is not on PATH (and ``binary_path`` is not provided).
    * the URL doesn't appear in stdout within ``timeout`` seconds.

    Cloudflared writes its banner to *stderr*, not stdout — the parser
    reads both.
    """
    binary = binary_path or _find_binary("cloudflared")
    if not binary:
        raise TunnelError(
            "cloudflared is not installed and no binary path was provided.\n\n" + _install_hint()
        )

    cmd = [binary, "tunnel", "--url", f"http://localhost:{local_port}"]
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # cloudflared writes to stderr; merge.
        text=True,
        bufsize=1,
    )

    return _await_url(process, _CLOUDFLARED_URL_RE, "cloudflared", timeout)


def start_ngrok(
    local_port: int,
    *,
    timeout: float = 30.0,
    binary_path: Optional[str] = None,
) -> TunnelHandle:
    """Spawn an ngrok tunnel for ``http://localhost:<port>``.

    ngrok requires a free auth token to be configured (``ngrok config add-authtoken``).
    """
    binary = binary_path or _find_binary("ngrok")
    if not binary:
        raise TunnelError(
            "ngrok is not installed and no binary path was provided.\n"
            "Install: https://ngrok.com/download"
        )

    cmd = [binary, "http", "--log=stdout", "--log-format=logfmt", str(local_port)]
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    return _await_url(process, _NGROK_URL_RE, "ngrok", timeout)


def _await_url(
    process: subprocess.Popen,
    pattern: "re.Pattern[str]",
    provider: str,
    timeout: float,
) -> TunnelHandle:
    """Read the subprocess's merged stdout/stderr for ``timeout`` seconds
    until ``pattern`` matches. Returns a ``TunnelHandle``."""
    start = time.monotonic()
    captured: list[str] = []
    found_url: Optional[str] = None

    # Reader thread so we can enforce timeout cleanly even if the child
    # buffers its output (cloudflared chunks per line, but be defensive).
    done = threading.Event()
    line_buf: list[str] = []

    def _reader() -> None:
        assert process.stdout is not None
        for raw in process.stdout:
            line_buf.append(raw)
            if done.is_set():
                break

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()

    try:
        while time.monotonic() - start < timeout:
            if line_buf:
                line = line_buf.pop(0)
                captured.append(line)
                m = pattern.search(line)
                if m:
                    found_url = m.group(0) if not m.groups() else m.group(1)
                    break
            else:
                time.sleep(0.05)
            if process.poll() is not None:
                # Subprocess exited before producing a URL.
                break
    finally:
        done.set()

    if not found_url:
        # Tear down the failed tunnel before raising.
        process.terminate()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()
        tail = "".join(captured[-20:])
        raise TunnelError(
            f"{provider} did not produce a public URL within {timeout:.1f}s. "
            f"Last output:\n{tail}"
        )

    return TunnelHandle(public_url=found_url, process=process, provider=provider)


def mcp_config_for_clients(public_url: str) -> Dict[str, dict]:
    """Generate ready-to-paste MCP client config for the three web-chat
    clients that accept HTTPS-reachable MCP servers.

    The shape of each blob matches what each client expects in 2026-Q2:
    * Claude.ai web — "Custom integrations" → MCP server URL.
    * Gemini chat — Workspace → MCP connectors → URL.
    * ChatGPT — Connectors → MCP → URL (custom GPTs supported).

    Each blob is a self-contained config the user can paste verbatim. We
    also emit a generic ``mcp.json`` shape that works for IDE clients
    (Cursor, Antigravity) that key on ``mcpServers``.
    """
    return {
        "claude_ai": {
            "name": "neuromem",
            "url": public_url,
            "transport": "http",
            "description": (
                "NeuroMem brain-inspired memory — episodic / semantic / "
                "procedural with knowledge-graph retrieval."
            ),
        },
        "gemini_chat": {
            "mcpServers": {
                "neuromem": {
                    "url": public_url,
                    "transport": "http",
                }
            }
        },
        "chatgpt": {
            "name": "NeuroMem",
            "type": "mcp",
            "url": public_url,
            "auth": "none",
            "description": "NeuroMem brain-inspired memory for AI agents",
        },
        # Generic IDE-style blob (Cursor / Antigravity / VS Code MCP)
        "mcp_json": {
            "mcpServers": {
                "neuromem": {
                    "url": public_url,
                    "transport": "http",
                }
            }
        },
    }


def persist_public_config(blobs: Dict[str, dict], path: Optional[Path] = None) -> Path:
    """Write the per-client MCP config blobs to disk for reuse.

    Default location: ``~/.neuromem/mcp-public.json``. Callers can override
    via ``path`` (used by the UI server when serving ``/api/mcp-config``).
    """
    target = path or Path.home() / ".neuromem" / "mcp-public.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(blobs, indent=2), encoding="utf-8")
    return target


def format_setup_instructions(public_url: str) -> str:
    """Human-readable terminal output describing how to connect each client
    to the running tunnel. Printed by ``neuromem-mcp serve --public`` so
    the user can act on it immediately."""
    blobs = mcp_config_for_clients(public_url)
    sections = [
        f"NeuroMem MCP tunnel is live at: {public_url}",
        "",
        "─── Claude.ai (web) ─────────────────────────────────────────",
        "Settings → Integrations → Add custom MCP server. Paste:",
        json.dumps(blobs["claude_ai"], indent=2),
        "",
        "─── Gemini chat (web) ───────────────────────────────────────",
        "Workspace settings → MCP connectors → Add. Paste:",
        json.dumps(blobs["gemini_chat"], indent=2),
        "",
        "─── ChatGPT (web) ───────────────────────────────────────────",
        "Settings → Connectors → MCP → Add server. Paste:",
        json.dumps(blobs["chatgpt"], indent=2),
        "",
        "─── Cursor / Antigravity / VS Code MCP (IDEs) ───────────────",
        "Drop this into the MCP config file (.cursor/mcp.json or equivalent):",
        json.dumps(blobs["mcp_json"], indent=2),
        "",
        f"Saved to: {Path.home() / '.neuromem' / 'mcp-public.json'}",
    ]
    return "\n".join(sections)


__all__ = [
    "TunnelError",
    "TunnelHandle",
    "start_cloudflared",
    "start_ngrok",
    "mcp_config_for_clients",
    "persist_public_config",
    "format_setup_instructions",
]
