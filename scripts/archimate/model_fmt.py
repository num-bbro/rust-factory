#!/usr/bin/env python3
"""Put ArchiMate exchange files in the canonical form of ADR 0009 (see exchange.py).

  python3 -I model_fmt.py [FILE ...]           format in place
  python3 -I model_fmt.py --check [FILE ...]   only check; exit 1 naming each file not canonical

FILE defaults to docs/architecture/model.xml. Exit codes: 0 ok, 1 not canonical (--check),
2 a file is missing or cannot be put in canonical form (each problem is listed).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Sibling module. Added explicitly because `python3 -I` (isolated mode) leaves the script's
# own folder off sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import exchange  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / "docs" / "architecture" / "model.xml"


def format_file(path: Path, check: bool) -> int:
    if not path.is_file():
        hint = " (the exchange model is created by step 2 of #41; pass a file)" if path == DEFAULT else ""
        print(f"{path}: no such file{hint}", file=sys.stderr)
        return 2
    data = path.read_bytes()
    try:
        text, notes = exchange.canonical(data)
    except exchange.FormatError as err:
        for problem in err.problems:
            print(f"{path}: {problem}", file=sys.stderr)
        return 2
    for note in notes:
        print(f"{path}: note: {note}", file=sys.stderr)
    formatted = text.encode("utf-8")
    if formatted == data:
        print(f"{path}: canonical")
        return 0
    if check:
        print(f"{path}: not in canonical form; run: just model-fmt {path}", file=sys.stderr)
        return 1
    path.write_bytes(formatted)
    print(f"{path}: formatted")
    return 0


def main(argv: list[str]) -> int:
    check = "--check" in argv
    args = [a for a in argv if a != "--check"]
    if any(a.startswith("-") for a in args):
        print(__doc__, file=sys.stderr)
        return 2
    paths = [Path(a) for a in args] or [DEFAULT]
    return max(format_file(p, check) for p in paths)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
