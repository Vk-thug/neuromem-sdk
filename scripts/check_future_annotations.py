#!/usr/bin/env python3
"""
Check that .py files using PEP 604 union syntax (`X | None`) declare
`from __future__ import annotations`.

PEP 604 union types only evaluate at runtime on Python 3.10+. On 3.9 they
crash at import with `TypeError: unsupported operand type(s) for |: 'type'
and 'NoneType'` unless the module declares `from __future__ import
annotations`, which defers all annotations to strings.

Usage:
    python scripts/check_future_annotations.py [path ...]
    # or for staged files only:
    git diff --cached --name-only --diff-filter=ACM | grep -E '[.]py$' | xargs python scripts/check_future_annotations.py

Exit code 0 if clean, 1 if any file needs the import.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Matches `name: type | None`, `-> type | None`, `= type | None`, etc.
# Deliberately conservative: only flag clear PEP 604 union patterns.
PEP604_PATTERN = re.compile(
    r"(?:->|:)\s*[\w\[\]., ]+\s*\|\s*(?:None|\w+)",
    re.MULTILINE,
)
FUTURE_IMPORT = "from __future__ import annotations"


def check_file(path: Path) -> str | None:
    """Return an error message if the file is missing the import, else None."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    if FUTURE_IMPORT in text:
        return None

    match = PEP604_PATTERN.search(text)
    if match is None:
        return None

    line_no = text[: match.start()].count("\n") + 1
    return f"{path}:{line_no}: PEP 604 union used without `{FUTURE_IMPORT}`"


def main(argv: list[str]) -> int:
    targets = argv[1:] if len(argv) > 1 else ["neuromem/", "benchmarks/", "tests/"]
    errors: list[str] = []

    for target in targets:
        p = Path(target)
        if p.is_file() and p.suffix == ".py":
            err = check_file(p)
            if err:
                errors.append(err)
        elif p.is_dir():
            for py_file in p.rglob("*.py"):
                err = check_file(py_file)
                if err:
                    errors.append(err)

    if errors:
        print("PEP 604 union syntax without `from __future__ import annotations`:")
        for e in errors:
            print(f"  {e}")
        print(
            "\nAdd `from __future__ import annotations` at the top of each file "
            "(after the module docstring) to make the code py3.9 compatible."
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
