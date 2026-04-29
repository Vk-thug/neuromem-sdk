"""``neuromem config`` — show / edit / validate yaml from the terminal."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _cmd_show(args: argparse.Namespace) -> int:
    from neuromem.config_schema import ConfigService

    cfg = ConfigService(args.config).load()
    import yaml

    yaml.safe_dump(
        cfg.model_dump(mode="json"), sys.stdout, default_flow_style=False, sort_keys=False
    )
    return 0


def _cmd_edit(args: argparse.Namespace) -> int:
    from neuromem.config_schema import ConfigService

    src = Path(args.config)
    if not src.exists():
        print(f"  {src} not found. Run `neuromem init` first.", file=sys.stderr)
        return 1

    editor = os.environ.get("EDITOR") or shutil.which("nano") or shutil.which("vi")
    if not editor:
        print("  No $EDITOR set and neither nano nor vi found.", file=sys.stderr)
        return 1

    with tempfile.NamedTemporaryFile("w+", suffix=".yaml", delete=False) as tmp:
        tmp.write(src.read_text())
        tmp_path = Path(tmp.name)

    try:
        while True:
            subprocess.call([editor, str(tmp_path)])
            try:
                ConfigService(tmp_path).load()
            except Exception as exc:
                print(f"\n  Validation error: {exc}", file=sys.stderr)
                retry = input("  Re-edit? [Y/n]: ").strip().lower()
                if retry in ("", "y", "yes"):
                    continue
                return 1
            shutil.copy(tmp_path, src)
            print(f"\n  Saved {src}")
            return 0
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def _cmd_validate(args: argparse.Namespace) -> int:
    from neuromem.config_schema import ConfigService

    try:
        ConfigService(args.config).load()
    except Exception as exc:
        print(f"  INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"  OK: {args.config}")
    return 0


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="neuromem config")
    parser.add_argument("--config", default="neuromem.yaml")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("show", help="Print the resolved config")
    sub.add_parser("edit", help="Open $EDITOR with validation on save")
    sub.add_parser("validate", help="Validate yaml against the schema")

    args = parser.parse_args(argv)
    handlers = {"show": _cmd_show, "edit": _cmd_edit, "validate": _cmd_validate}
    return handlers[args.action](args)
