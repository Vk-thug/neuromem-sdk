"""``neuromem`` CLI — single entry point for all subcommands.

Subcommands:
    neuromem init [--ui]              First-run wizard (terminal or browser).
    neuromem ui   [--port ...]        Launch the local UI.
    neuromem mcp                      Launch the MCP server (stdio).
    neuromem config show              Print the current resolved config.
    neuromem config edit              Open ``$EDITOR`` on neuromem.yaml.
    neuromem config validate          Validate yaml against the Pydantic schema.
    neuromem doctor                   Check Ollama / Qdrant / Postgres reachability.

The legacy ``neuromem-ui`` and ``neuromem-mcp`` console scripts remain as
deprecated aliases for one release (see ``pyproject.toml``).
"""

from __future__ import annotations

import argparse
import sys
from typing import Callable, Dict, List, Optional


def _cmd_init(argv: list[str]) -> int:
    from neuromem.cli.init import run as run_init

    return run_init(argv)


def _cmd_ui(argv: list[str]) -> int:
    from neuromem.ui.cli import main as run_ui

    sys.argv = ["neuromem ui", *argv]
    run_ui()
    return 0


def _cmd_mcp(argv: list[str]) -> int:
    from neuromem.mcp.__main__ import main as run_mcp

    sys.argv = ["neuromem mcp", *argv]
    run_mcp()
    return 0


def _cmd_config(argv: list[str]) -> int:
    from neuromem.cli.config import run as run_config

    return run_config(argv)


def _cmd_doctor(argv: list[str]) -> int:
    from neuromem.cli.doctor import run as run_doctor

    return run_doctor(argv)


_DISPATCH: Dict[str, Callable[[list[str]], int]] = {
    "init": _cmd_init,
    "ui": _cmd_ui,
    "mcp": _cmd_mcp,
    "config": _cmd_config,
    "doctor": _cmd_doctor,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neuromem",
        description="NeuroMem SDK — brain-faithful memory for AI agents.",
        usage="neuromem <command> [options]",
    )
    parser.add_argument(
        "command",
        choices=list(_DISPATCH.keys()),
        help="Subcommand to run",
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to the subcommand",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help"):
        _build_parser().print_help()
        return 0

    if argv[0] in ("-V", "--version"):
        from neuromem import __version__

        print(f"neuromem {__version__}")
        return 0

    command, rest = argv[0], argv[1:]
    handler = _DISPATCH.get(command)
    if handler is None:
        print(f"neuromem: unknown command '{command}'", file=sys.stderr)
        _build_parser().print_help(sys.stderr)
        return 2

    return handler(rest)


if __name__ == "__main__":
    raise SystemExit(main())
