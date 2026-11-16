"""Unwrap and wrap Markdown paragraphs: the model stores each paragraph and each list item on one
line (ADR 0009, line breaks: option A); generated pages wrap them again at WIDTH characters so
they read and diff like hand-written Markdown.

Both directions work on block structure only, line by line:

* never joined, never wrapped: blank lines, fenced code blocks (``` or ~~~, with everything
  inside), ATX headings, table rows (`|`), block quotes (`>`), HTML lines (`<`), thematic breaks
  and setext underlines, and a line indented 4 or more spaces that starts a block (indented code);
* a list item (`-`, `*`, `+`, `1.`, `1)`) is one unit with its continuation lines, which are
  written at the item's content indent;
* any other line starts a paragraph; its continuation lines are written at its first line's indent;
* a line ending in a backslash (a hard break) ends its unit.

`unwrap(wrap(text)) == text` for every text `unwrap` returns, so a generated page reads back to the
model's text. Wrapping never changes how the Markdown renders: it breaks only at a single space,
never before a word that could start a block (a list marker, `#`, `>`, `|`, `<`, a fence, a break
line) and never after a word ending in a backslash; a word longer than the width (a long URL or
code span) stays whole on an over-long line.

Pure functions, standard library only.
"""

from __future__ import annotations

import re

WIDTH = 100

_FENCE = re.compile(r" {0,3}(`{3,}|~{3,})")
_VERBATIM = re.compile(r" {0,3}(#{1,6}(\s|$)|>|<|(=+|-+) *$|([*_])( *\4){2,} *$)|\s*\|")
_LIST = re.compile(r"(\s*)([-*+]|\d{1,9}[.)])( +|$)")
# A word that would start a block (or end a paragraph) if it began a continuation line.
_BLOCK_WORD = re.compile(r"#{1,6}|[-*+]|\d{1,9}[.)]|[-=_*]+|[>|<].*|`{3}.*|~{3}.*")


def _blank(line: str) -> bool:
    return not line.strip()


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _lines_of(text: str):
    """Yield (line, kind) with kind "raw" (never joined or wrapped), "list" or "para"."""
    fence = ""
    for line in text.split("\n"):
        m = _FENCE.match(line)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) \
                    and not line[m.end():].strip():
                fence = ""
            yield line, "raw"
        elif m:
            fence = m.group(1)
            yield line, "raw"
        elif _blank(line) or _VERBATIM.match(line):
            yield line, "raw"
        elif _LIST.match(line):
            yield line, "list"
        else:
            yield line, "para"


def unwrap(text: str) -> str:
    """Join each paragraph and each list item onto one line (continuation lines are stripped and
    joined with one space); everything else is kept as it is."""
    out: list[str] = []
    open_unit = False                    # the last line of `out` may take continuation lines
    for line, kind in _lines_of(text):
        if kind == "para" and open_unit:
            out[-1] += " " + line.strip()
        elif kind == "para" and _indent(line) >= 4:
            out.append(line)             # indented code: starts no unit
            open_unit = False
            continue
        else:
            out.append(line.rstrip() if kind != "raw" else line)
            open_unit = kind != "raw"
        if out[-1].endswith("\\"):
            open_unit = False            # a hard break ends the unit
    return "\n".join(out)


def _wrap_line(line: str, kind: str, width: int) -> list[str]:
    if kind == "list":
        m = _LIST.match(line)
        assert m is not None
        head = m.group(0)
        spaces = len(m.group(3))
        cont = len(head) if 1 <= spaces <= 4 else len(m.group(1)) + len(m.group(2)) + 1
    else:
        cont = _indent(line)
        head = line[:cont]
    words = line[len(head):].split(" ")
    lines, cur = [], head + words[0]
    for prev, word in zip(words, words[1:]):
        breakable = prev and word and not prev.endswith("\\") and not _BLOCK_WORD.fullmatch(word)
        if breakable and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = " " * cont + word
        else:
            cur += " " + word
    lines.append(cur)
    return lines


def wrap(text: str, width: int = WIDTH) -> str:
    """Wrap each paragraph line and list-item line at `width` characters."""
    out: list[str] = []
    open_unit = False
    for line, kind in _lines_of(text):
        if kind == "raw" or (kind == "para" and not open_unit and _indent(line) >= 4):
            out.append(line)
            open_unit = False
            continue
        out.extend(_wrap_line(line, kind, width))
        open_unit = not line.endswith("\\")
    return "\n".join(out)
