"""Unwrap and wrap Markdown paragraphs: the model stores each paragraph and each list item on one
line (ADR 0009, line breaks: option A); generated pages wrap them again at WIDTH characters so
they read and diff like hand-written Markdown.

Both directions work on block structure only, line by line, and know which list items a line is
inside (the "base" indent: the content indent of the innermost open list item, else 0):

* never joined, never wrapped ("raw"): blank lines; fenced code blocks (``` or ~~~ at any indent,
  with everything up to the closing fence); a line indented 4 or more spaces past the base that
  does not continue a paragraph (indented code); ATX headings, block quotes (`>`), HTML lines
  (`<`, and the rest of that HTML block: up to `-->`, `?>`, `]]>`, `>` or the closing `</pre>`,
  `</script>`, `</style>`, `</textarea>` for those, else up to the next blank line), thematic
  breaks and setext underlines, each up to 3 spaces past the base; table rows
  (a line starting with `|`, or a header line followed by a delimiter row such as `--- | ---`,
  and every line of that table up to the next blank line);
* a list item (`-`, `*`, `+`, `1.`, `1)`) is one unit with its continuation lines, which are
  written at the item's content indent;
* any other line starts a paragraph; its continuation lines are written at its first line's indent;
* a line ending in a backslash (a hard break) ends its unit.

Not supported, so `problems` reports it and both directions leave the line alone: a tab in the
indentation of a line outside a fenced code block, and a fence closed at less indent than the list
item it was opened in.

`unwrap(wrap(text)) == text` for every text `unwrap` returns, so a generated page reads back to the
model's text. Wrapping never changes how the Markdown renders: raw lines are copied, and a list
item or paragraph breaks only at a single space, never before a word that could start a block (a
list marker, `#`, `>`, `|`, `<`, a fence, a break line, a delimiter-row fragment) and never after a
word ending in a backslash, and never inside an inline link or image, `[text](target)` or
`![alt](target)`, which is one unbreakable unit (`jekyll-relative-links` does not convert a link
whose text is over two lines); a word longer than the width (a long URL or code span) stays whole on
an over-long line.

Pure functions, standard library only.
"""

from __future__ import annotations

import re

WIDTH = 100

_FENCE = re.compile(r"(\s*)(`{3,}|~{3,})(.*)")
_RAW = re.compile(r" {0,3}(#{1,6}(\s|$)|>|<|(=+|-+) *$|([*_])( *\4){2,} *$)")
_LIST = re.compile(r"(\s*)([-*+]|\d{1,9}[.)])( +|$)")
# A word that would start a block (or end a paragraph) if it began a continuation line.
_BLOCK_WORD = re.compile(r"#{1,6}|[-*+]|\d{1,9}[.)]|[-=_*]+|[>|<].*|`{3}.*|~{3}.*|:[-:|]*")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _html_end(rel: str) -> re.Pattern[str]:
    """What ends the HTML block that `rel` (a line starting with `<`) opens."""
    for start, end in ((r"<(pre|script|style|textarea)\b", r"</(pre|script|style|textarea)>"),
                       (r"<!--", r"-->"), (r"<\?", r"\?>"), (r"<!\[CDATA\[", r"\]\]>"),
                       (r"<![A-Za-z]", r">")):
        if re.match(start, rel.lstrip(), re.IGNORECASE):
            return re.compile(end, re.IGNORECASE)
    return re.compile(r"^\s*$")                  # any other HTML block ends at a blank line


def _delimiter_row(line: str) -> bool:
    return "|" in line and "-" in line and re.fullmatch(r"[\s|:-]+", line) is not None


def _classify(text: str) -> tuple[list[tuple[str, str]], list[str], set[int]]:
    """Each line with its kind: "raw", "list" (starts an item), "para" (starts a paragraph) or
    "cont" (continues the item or paragraph above); what is not supported, by line; and the
    numbers (from 0) of the lines that are code: fences, fenced and indented code."""
    lines = text.split("\n")
    out: list[tuple[str, str]] = []
    problems: list[str] = []
    code: set[int] = set()
    items: list[int] = []                # content indents of the open list items
    fence: tuple[str, int, int, int] | None = None  # fence character, length, indent, item indent
    html: re.Pattern[str] | None = None  # what ends the open HTML block
    unit = table = False                 # a unit may continue / inside a table
    for i, line in enumerate(lines):
        ind = _indent(line)
        if fence:
            m = _FENCE.fullmatch(line)
            if m and m.group(2)[0] == fence[0] and len(m.group(2)) >= fence[1] \
                    and not m.group(3).strip() and ind <= fence[2] + 3:
                if ind < fence[3]:
                    problems.append(f"line {i + 1}: this fence closes at indent {ind}, left of its "
                                    f"list item's content (indent {fence[3]}); close a fence at "
                                    "the indent it was opened")
                fence = None
            out.append((line, "raw"))
            code.add(i)
            continue
        if html:
            if html.search(line):
                html = None
            if line.strip():
                out.append((line, "raw"))
                continue
        if not line.strip():
            out.append((line, "raw"))
            unit = table = False
            continue
        if "\t" in line[:ind]:
            problems.append(f"line {i + 1}: a tab in the indentation; indent with spaces, or use "
                            "a fenced code block")
            out.append((line, "raw"))
            unit = False
            continue
        listed = _LIST.match(line)
        if not unit or listed or _RAW.match(line.lstrip()):
            while items and items[-1] > ind:     # a new block leaves the items it is not in
                items.pop()
        base = items[-1] if items else 0
        rel = line[min(ind, base):]
        fenced = _FENCE.match(line)
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if fenced and not (fenced.group(2)[0] == "`" and "`" in fenced.group(3)):
            fence = (fenced.group(2)[0], len(fenced.group(2)), ind, base)
            kind = "raw"
            code.add(i)
        elif table or line.lstrip().startswith("|") or _delimiter_row(nxt):
            table = True
            kind = "raw"
        elif ind >= base + 4:
            kind = "cont" if unit and not listed else "raw"
            if kind == "raw":
                code.add(i)
        elif _RAW.match(rel):
            if rel.lstrip().startswith("<"):
                end = _html_end(rel)
                html = None if end.search(rel.lstrip()[1:]) else end
            kind = "raw"
        elif listed:
            spaces = len(listed.group(3))
            items.append(len(listed.group(0)) if 1 <= spaces <= 4
                         else len(listed.group(1)) + len(listed.group(2)) + 1)
            kind = "list"
        else:
            kind = "cont" if unit else "para"
        unit = kind != "raw" and not line.endswith("\\")   # a hard break ends the unit
        out.append((line, kind))
    return out, problems, code


def code_lines(text: str) -> set[int]:
    """The numbers (from 0) of the lines of `text` that are code: fence lines, the lines inside a
    fenced code block, and indented code."""
    return _classify(text)[2]


def problems(text: str) -> list[str]:
    """What `text` uses that wrapping does not support (each names its line)."""
    return _classify(text)[1]


def unwrap(text: str) -> str:
    """Join each paragraph and each list item onto one line (continuation lines are stripped and
    joined with one space); everything else is kept as it is."""
    out: list[str] = []
    for line, kind in _classify(text)[0]:
        if kind == "cont":
            out[-1] += " " + line.strip()
        else:
            out.append(line if kind == "raw" else line.rstrip())
    return "\n".join(out)


def _closing(line: str, start: int, open_: str, close: str) -> int:
    """The index of the bracket that closes the one at `start`, or -1 (backslash escapes and, for
    square brackets, code spans skipped)."""
    depth = 0
    i = start
    while i < len(line):
        if line[i] == "\\":
            i += 2
            continue
        if line[i] == "`" and open_ == "[":
            ticks = re.match(r"`+", line[i:]).group(0)
            end = line.find(ticks, i + len(ticks))
            if end > 0:
                i = end + len(ticks)
                continue
        depth += line[i] == open_
        depth -= line[i] == close
        if depth == 0:
            return i
        i += 1
    return -1


def _link_spaces(line: str, begin: int) -> set[int]:
    """The indexes of the spaces, from `begin` on, inside an inline link or image `[..](..)`."""
    locked: set[int] = set()
    i = begin
    while i < len(line):
        if line[i] == "\\":
            i += 2
            continue
        if line[i] == "[":
            end = _closing(line, i, "[", "]")
            if end > 0 and line[end + 1:end + 2] == "(":
                last = _closing(line, end + 1, "(", ")")
                if last > 0:
                    locked.update(k for k in range(i, last) if line[k] == " ")
                    i = last
        i += 1
    return locked


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
    locked = _link_spaces(line, len(head))
    words: list[str] = []
    at = len(head)
    for part in line[len(head):].split(" "):
        words.append(words.pop() + " " + part if words and at - 1 in locked else part)
        at += len(part) + 1
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
    for line, kind in _classify(text)[0]:
        if kind == "raw":
            out.append(line)
        else:
            out.extend(_wrap_line(line, "list" if kind == "list" else "para", width))
    return "\n".join(out)
