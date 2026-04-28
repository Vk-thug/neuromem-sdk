"""
Tests for v0.4.0 MCP tunnel helper (cloudflared / ngrok URL parsing,
config blobs, persistence).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from neuromem.mcp.tunnel import (
    TunnelError,
    _CLOUDFLARED_URL_RE,
    _NGROK_URL_RE,
    _await_url,
    format_setup_instructions,
    mcp_config_for_clients,
    persist_public_config,
)


class TestUrlPatterns:
    def test_cloudflared_pattern(self):
        line = "2026-04-28T10:00:00Z INF |  https://random-words-1234.trycloudflare.com  |"
        m = _CLOUDFLARED_URL_RE.search(line)
        assert m is not None
        assert m.group(0) == "https://random-words-1234.trycloudflare.com"

    def test_cloudflared_pattern_rejects_non_trycloudflare(self):
        m = _CLOUDFLARED_URL_RE.search("https://example.com")
        assert m is None

    def test_ngrok_pattern(self):
        line = "t=2026-04-28 lvl=info msg=started url=https://abcd-1234.ngrok-free.app"
        m = _NGROK_URL_RE.search(line)
        assert m is not None
        assert m.group(1) == "https://abcd-1234.ngrok-free.app"


class TestMcpConfigBlobs:
    def setup_method(self):
        self.url = "https://test-tunnel.trycloudflare.com"
        self.blobs = mcp_config_for_clients(self.url)

    def test_all_clients_present(self):
        for key in ("claude_ai", "gemini_chat", "chatgpt", "mcp_json"):
            assert key in self.blobs

    def test_url_propagates_through_all_blobs(self):
        b = self.blobs
        assert b["claude_ai"]["url"] == self.url
        assert b["gemini_chat"]["mcpServers"]["neuromem"]["url"] == self.url
        assert b["chatgpt"]["url"] == self.url
        assert b["mcp_json"]["mcpServers"]["neuromem"]["url"] == self.url

    def test_blobs_are_json_serialisable(self):
        json.dumps(self.blobs)  # must not raise

    def test_setup_instructions_mentions_each_client(self):
        instr = format_setup_instructions(self.url)
        assert "Claude.ai" in instr
        assert "Gemini" in instr
        assert "ChatGPT" in instr
        assert self.url in instr


class TestPersistConfig:
    def test_writes_to_custom_path(self, tmp_path: Path):
        url = "https://x.trycloudflare.com"
        blobs = mcp_config_for_clients(url)
        target = tmp_path / "subdir" / "mcp.json"
        out = persist_public_config(blobs, target)
        assert out == target
        assert target.exists()
        loaded = json.loads(target.read_text())
        assert loaded["claude_ai"]["url"] == url


class _FakeProcess:
    """Minimal subprocess.Popen stand-in for _await_url."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = list(lines)
        self.stdout = iter(self._lines)
        self._dead = False
        self._terminated = False
        self._killed = False

    def poll(self) -> int | None:
        return 0 if self._dead else None

    def terminate(self) -> None:
        self._terminated = True
        self._dead = True

    def kill(self) -> None:
        self._killed = True
        self._dead = True

    def wait(self, timeout: float | None = None) -> int:
        return 0


class TestAwaitUrl:
    def test_await_url_finds_cloudflared(self):
        proc = _FakeProcess(
            [
                "2026-04-28 INF starting tunnel\n",
                "2026-04-28 INF | https://abc-xyz.trycloudflare.com |\n",
            ]
        )
        handle = _await_url(proc, _CLOUDFLARED_URL_RE, "cloudflared", timeout=5.0)
        assert handle.public_url == "https://abc-xyz.trycloudflare.com"
        assert handle.provider == "cloudflared"

    def test_await_url_raises_on_timeout(self):
        proc = _FakeProcess(["banner without url\n"])  # no URL
        with pytest.raises(TunnelError) as info:
            _await_url(proc, _CLOUDFLARED_URL_RE, "cloudflared", timeout=0.5)
        assert "did not produce a public URL" in str(info.value)


class TestStartCloudflaredErrors:
    def test_missing_binary_raises(self):
        from neuromem.mcp.tunnel import start_cloudflared

        with mock.patch("neuromem.mcp.tunnel._find_binary", return_value=None):
            with pytest.raises(TunnelError) as info:
                start_cloudflared(8000)
        msg = str(info.value)
        assert "cloudflared is not installed" in msg
        assert "brew install cloudflared" in msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
