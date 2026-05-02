"""v0.4.7: MCP mounted in-process under FastAPI.

When ``mcp.enabled`` is true in yaml, the UI server mounts the FastMCP
streamable-http sub-app at ``cfg.mcp.mount_path`` (default ``/mcp``).
When false, that path returns 404. This replaces the v0.4.6 second-process
``neuromem-mcp`` pattern for the common single-user case.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

fastapi = pytest.importorskip("fastapi")
mcp = pytest.importorskip("mcp.server.fastmcp")
from fastapi.testclient import TestClient  # noqa: E402


def _write_yaml(tmp_path: Path, mcp_enabled: bool) -> Path:
    cfg = tmp_path / "neuromem.yaml"
    body = {
        "neuromem": {
            "mode": "single",
            "user": {"id": "00000000-0000-0000-0000-000000000001"},
            "mcp": {"enabled": mcp_enabled, "mount_path": "/mcp", "expose_as": "http"},
            "storage": {
                "vector_store": {"type": "memory"},
                "database": {"type": "memory", "url": None},
            },
        }
    }
    with cfg.open("w") as f:
        yaml.safe_dump(body, f)
    return cfg


@pytest.fixture
def mock_memory() -> Any:
    controller = MagicMock()
    controller.brain = None
    memory = MagicMock()
    memory.user_id = "00000000-0000-0000-0000-000000000001"
    memory.controller = controller
    return memory


def _mount_paths(app: Any) -> list[str]:
    """Collect the path prefix of every Starlette Mount on the app."""
    from starlette.routing import Mount

    return [r.path for r in app.routes if isinstance(r, Mount)]


def test_mcp_mounted_when_enabled(tmp_path: Path, monkeypatch, mock_memory: Any) -> None:
    cfg = _write_yaml(tmp_path, mcp_enabled=True)
    monkeypatch.setenv("NEUROMEM_CONFIG", str(cfg))
    from neuromem.ui.server import create_app

    app = create_app(mock_memory)
    # Verify the mount exists on the route table. Hitting the endpoint
    # would require running FastMCP's lifespan and a real handshake,
    # which is overkill for "did the mount happen" — that's a separate
    # MCP-protocol test.
    assert "/mcp" in _mount_paths(app), f"MCP not mounted — mounts present: {_mount_paths(app)}"


def test_mcp_not_mounted_when_disabled(tmp_path: Path, monkeypatch, mock_memory: Any) -> None:
    cfg = _write_yaml(tmp_path, mcp_enabled=False)
    monkeypatch.setenv("NEUROMEM_CONFIG", str(cfg))
    from neuromem.ui.server import create_app

    app = create_app(mock_memory)
    assert "/mcp" not in _mount_paths(app)
