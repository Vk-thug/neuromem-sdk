"""
Tests for v0.4.0 plugin manifests — Cursor + Antigravity (new) and the
existing Claude Code / Codex CLI / Gemini CLI plugins.

These tests validate the JSON shape that each MCP-aware client expects.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = REPO_ROOT / "plugins"


@pytest.mark.parametrize(
    "manifest_path",
    [
        PLUGINS_DIR / "cursor" / ".cursor" / "mcp.json",
        PLUGINS_DIR / "antigravity" / ".antigravity" / "mcp.json",
        PLUGINS_DIR / "claude-code" / ".mcp.json",
        PLUGINS_DIR / "codex-cli" / ".mcp.json",
    ],
)
def test_mcp_manifest_shape(manifest_path: Path) -> None:
    """Every MCP manifest must:
    1. Be valid JSON.
    2. Contain a top-level ``mcpServers`` mapping.
    3. Contain a ``neuromem`` server entry.
    4. Reference ``python -m neuromem.mcp`` as the command.
    """
    assert manifest_path.exists(), f"missing manifest: {manifest_path}"
    data = json.loads(manifest_path.read_text())
    assert "mcpServers" in data, f"no mcpServers in {manifest_path}"
    assert "neuromem" in data["mcpServers"], f"no neuromem entry in {manifest_path}"
    server = data["mcpServers"]["neuromem"]
    assert server.get("command") == "python", f"unexpected command in {manifest_path}"
    assert "neuromem.mcp" in (
        server.get("args") or []
    ), f"command does not invoke neuromem.mcp in {manifest_path}"


def test_cursor_plugin_readme_exists() -> None:
    assert (PLUGINS_DIR / "cursor" / "README.md").exists()


def test_antigravity_plugin_readme_exists() -> None:
    assert (PLUGINS_DIR / "antigravity" / "README.md").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
