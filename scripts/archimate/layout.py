"""Automatic layout for generated ArchiMate views.

Conventions (the ones ArchiMate practitioners draw by hand):

* One horizontal **band per layer**: Motivation, Strategy, Business, Application, Technology,
  Implementation & Migration, Other (top to bottom).
* Inside a band, one **row per aspect**: active structure (who) on top, behaviour (what they do)
  in the middle, passive structure (what is used) at the bottom. Motivation uses
  stakeholders/drivers -> goals/outcomes -> principles/requirements.
* **Composition / aggregation inside a layer is shown by nesting** the child in its parent,
  so those lines disappear (one level deep).
* **Ordering**: a few barycentre sweeps place every element under or above the elements it is
  connected to, so most lines become short and vertical.
* **Routing**: lines run at right angles through the empty channels between rows and the
  gutters between columns, never through boxes; parallel lines are spread apart.
* **Box size**: every element box is W wide and at least H tall; a box grows in height so its
  whole name shows (`box_height`), a row is as tall as its tallest box (boxes stay top-aligned),
  and nesting parents and bands grow with it.

Pure functions, standard library only. Coordinates are absolute, as the Open Exchange
format requires (also for nested nodes).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

LAYERS: list[tuple[str, list[list[str]]]] = [
    # layer, then its aspect rows (top to bottom)
    ("Motivation", [["Stakeholder", "Driver", "Assessment"], ["Goal", "Outcome", "Value", "Meaning"],
                    ["Principle", "Requirement", "Constraint"]]),
    ("Strategy", [["Resource"], ["Capability", "ValueStream", "CourseOfAction"], []]),
    ("Business", [["BusinessActor", "BusinessRole", "BusinessCollaboration", "BusinessInterface"],
                  ["BusinessProcess", "BusinessFunction", "BusinessInteraction", "BusinessEvent",
                   "BusinessService"],
                  ["BusinessObject", "Contract", "Representation", "Product"]]),
    ("Application", [["ApplicationComponent", "ApplicationCollaboration", "ApplicationInterface"],
                     ["ApplicationFunction", "ApplicationInteraction", "ApplicationProcess",
                      "ApplicationEvent", "ApplicationService"],
                     ["DataObject"]]),
    ("Technology", [["Node", "Device", "SystemSoftware", "TechnologyCollaboration",
                     "TechnologyInterface", "Path", "CommunicationNetwork", "Equipment",
                     "Facility", "DistributionNetwork"],
                    ["TechnologyFunction", "TechnologyProcess", "TechnologyInteraction",
                     "TechnologyEvent", "TechnologyService"],
                    ["Artifact", "Material"]]),
    ("Implementation & Migration", [["WorkPackage", "ImplementationEvent"],
                                    ["Plateau", "Gap"], ["Deliverable"]]),
    ("Other", [["Location", "Grouping"], [], []]),
]
LAYER_INDEX = {t: li for li, (_, rows) in enumerate(LAYERS) for row in rows for t in row}
ASPECT_INDEX = {t: ai for _, rows in LAYERS for ai, row in enumerate(rows) for t in row}
ELEMENT_TYPES = set(LAYER_INDEX)
NESTING_TYPES = {"Composition", "Aggregation"}
CHAIN_TYPES = {"Triggering", "Flow"}

# Geometry (pixels)
W, H = 160, 55                 # element box
GAP_X, ROW_GAP = 60, 70        # between boxes in a row / between rows (room for line channels)
PAR_PAD, PAR_TITLE = 15, 30    # nested parent: padding / room for its own name
BAND_PAD, BAND_LABEL = 20, 22  # layer band: padding / label strip
BAND_GAP, MARGIN = 40, 20
MAX_ROW_W = 1500               # wrap a row into a second line beyond this width
LINE_STEP = 8                  # spacing between parallel lines
# Name wrapping, calibrated against Archi's rendering (Archi version in tools/archi.env) of every
# element name in the model in a W-wide box: Archi centres the name at the top and wraps it at
# word breaks (and after a hyphen) by pixel width: a line holds 9 ("MMMM MMMM") to 38 ("iii…")
# characters, usually 16 to 20; lines are 17 pixels apart and two fill an H-tall box.
# CHARS_PER_LINE is the largest value for which the estimate is never smaller than what Archi
# draws (counting the three lines any box shows), and the only one that also keeps every name of
# up to three Archi lines (tests/test_layout.py, ARCHI_LINES).
CHARS_PER_LINE = 17
EXTRA, LINE = 12, 17           # box height from 3 lines up: EXTRA + LINE * lines (issue #77)


@dataclass
class Box:
    ref: str                                  # element id
    x: float = 0
    y: float = 0
    w: float = W
    h: float = H
    children: list[Box] = field(default_factory=list)

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


@dataclass
class Row:
    layer: int
    items: list[Box]
    y: float = 0

    @property
    def h(self) -> float:
        return max(b.h for b in self.items)


@dataclass
class Band:
    label: str
    x: float
    y: float
    w: float
    h: float
    rows: list[Row]


@dataclass
class Line:
    rel_id: str
    source: str
    target: str
    bends: list[tuple[float, float]]


@dataclass
class ViewLayout:
    bands: list[Band]
    boxes: dict[str, Box]          # every placed element (top-level and nested)
    nested: set[str]               # relationship ids shown by nesting instead of a line
    lines: list[Line]


def char_units(c: str) -> int:
    """Width of a character in the wrap: 2 for East Asian wide and full-width ones, else 1."""
    return 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1


def name_lines(name: str) -> int:
    """Lines a name takes in a W-wide box: greedy word wrap at CHARS_PER_LINE units a line.

    A character is 1 unit (2 if East Asian wide, `char_units`); a word longer than a line is cut
    into pieces of at most a line. Characters are counted, not measured, so the estimate depends
    on no font and is the same on every machine.
    Known limit: a name made mostly of wide Latin capitals (W, M) can be under-estimated by a
    line; the over-estimate for names with many narrow characters (i, l, punctuation) is accepted.
    """
    lines, used = 0, 0
    for word in name.split():
        pieces, piece = [], 0
        for c in word:
            if piece + char_units(c) > CHARS_PER_LINE:
                pieces.append(piece)
                piece = 0
            piece += char_units(c)
        pieces.append(piece)
        for piece in pieces:
            if used and used + 1 + piece <= CHARS_PER_LINE:
                used += 1 + piece
            else:
                lines, used = lines + 1, piece
    return max(lines, 1)


def box_height(name: str) -> int:
    """Height of an element box: H for one or two lines, EXTRA + LINE * lines from three up.
    EXTRA and LINE were fitted to rendered pixels (issue #77), not only to line counts."""
    lines = name_lines(name)
    return H if lines <= 2 else EXTRA + LINE * lines


def layout(refs: list[str], types: dict[str, str], names: dict[str, str],
           rels: list[dict[str, str]]) -> ViewLayout:
    """Lay out one view. `types` and `names` map element id -> type and name; `rels` are the
    model's relationships."""
    on_view = set(refs)
    rels = [r for r in rels if r["Source"] in on_view and r["Target"] in on_view]
    rtype = {r["ID"]: r["Type"].removesuffix("Relationship") for r in rels}

    # --- 1. nesting (one level) -----------------------------------------------------
    parent: dict[str, str] = {}
    nested: set[str] = set()
    for r in rels:
        s, t = r["Source"], r["Target"]
        if (rtype[r["ID"]] in NESTING_TYPES and LAYER_INDEX[types[s]] == LAYER_INDEX[types[t]]
                and s not in parent and t not in parent and t not in parent.values()
                and s != t):
            parent[t] = s
            nested.add(r["ID"])
    boxes = {ref: Box(ref, h=box_height(names[ref])) for ref in refs}
    for ref in refs:                                     # keep member order among siblings
        if ref in parent:
            boxes[parent[ref]].children.append(boxes[ref])
    for p in {parent[c] for c in parent}:
        kids = boxes[p].children
        boxes[p].children = chain_order(kids, rels, rtype)
        boxes[p].w = len(kids) * W + (len(kids) - 1) * GAP_X / 2 + 2 * PAR_PAD
        boxes[p].h = PAR_TITLE + max(k.h for k in kids) + PAR_PAD

    # --- 2. rows: (layer, aspect), top-level boxes only ------------------------------------
    keyed: dict[tuple[int, int], list[Box]] = {}
    for ref in refs:
        if ref not in parent:
            keyed.setdefault((LAYER_INDEX[types[ref]], ASPECT_INDEX[types[ref]]), []).append(boxes[ref])
    rows: list[Row] = []
    for (li, _), items in sorted(keyed.items()):
        line: list[Box] = []
        width = 0.0
        for b in items:                                   # wrap very wide rows
            if line and width + GAP_X + b.w > MAX_ROW_W:
                rows.append(Row(li, line))
                line, width = [], 0.0
            width += (GAP_X if line else 0) + b.w
            line.append(b)
        rows.append(Row(li, line))

    # --- 3. vertical placement (bands and rows) ---------------------------------------
    y = MARGIN
    band_spans: list[tuple[int, float, float, list[Row]]] = []
    for li in sorted({r.layer for r in rows}):
        layer_rows = [r for r in rows if r.layer == li]
        top = y
        y += BAND_LABEL + BAND_PAD
        for i, r in enumerate(layer_rows):
            r.y = y
            y += r.h + (ROW_GAP if i < len(layer_rows) - 1 else 0)
        y += BAND_PAD
        band_spans.append((li, top, y - top, layer_rows))
        y += BAND_GAP

    # --- 4. horizontal ordering + placement (barycentre sweeps) ----------------------------
    neighbours: dict[str, list[str]] = {ref: [] for ref in refs}
    for r in rels:
        if r["ID"] not in nested:
            neighbours[r["Source"]].append(r["Target"])
            neighbours[r["Target"]].append(r["Source"])
    x0 = MARGIN + BAND_PAD
    for row in rows:
        pack(row, x0)
    for sweep in range(8):
        order = rows if sweep % 2 == 0 else list(reversed(rows))
        for row in order:
            def desired(b: Box) -> float:
                own = {d.ref for d in [b, *b.children]}
                # All neighbours count, including ones in the same row, so related boxes in a
                # row (e.g. a scout serving the conductor) end up side by side.
                xs = [boxes[n].cx for d in [b, *b.children] for n in neighbours[d.ref]
                      if n not in own]
                return sum(xs) / len(xs) if xs else b.cx

            want = {id(b): desired(b) for b in row.items}
            row.items.sort(key=lambda b: want[id(b)])
            row.items = keep_chains(row.items, rels, rtype)
            pack(row, x0, want)
    shift = x0 - min(b.x for row in rows for b in row.items)
    for row in rows:
        for b in row.items:
            move(b, shift)
    right = max(b.x + b.w for row in rows for b in row.items) + BAND_PAD
    bands = [Band(LAYERS[li][0], MARGIN, top, right - MARGIN, h, lr) for li, top, h, lr in band_spans]

    # --- 5. routing ----------------------------------------------------------------------
    lines = route(rels, nested, boxes, parent, rows)
    return ViewLayout(bands, boxes, nested, lines)


def chain_order(kids: list[Box], rels: list[dict[str, str]], rtype: dict[str, str]) -> list[Box]:
    """Order siblings along triggering/flow chains (topological), else keep member order."""
    ids = [k.ref for k in kids]
    nxt = {i: [] for i in ids}
    indeg = dict.fromkeys(ids, 0)
    for r in rels:
        if rtype[r["ID"]] in CHAIN_TYPES and r["Source"] in nxt and r["Target"] in nxt:
            nxt[r["Source"]].append(r["Target"])
            indeg[r["Target"]] += 1
    out, ready = [], [i for i in ids if indeg[i] == 0]
    while ready:
        i = ready.pop(0)
        out.append(i)
        for j in nxt[i]:
            indeg[j] -= 1
            if indeg[j] == 0:
                ready.append(j)
    out += [i for i in ids if i not in out]               # cycles: keep the rest in member order
    by_id = {k.ref: k for k in kids}
    return [by_id[i] for i in out]


def keep_chains(items: list[Box], rels: list[dict[str, str]], rtype: dict[str, str]) -> list[Box]:
    """Within a row, boxes linked by triggering/flow keep their chain order (left to right).

    The slots the chain members occupy after barycentre sorting are refilled in chain order,
    so the rest of the row is untouched.
    """
    ordered = chain_order(items, rels, rtype)
    linked = {r["Source"] for r in rels if rtype[r["ID"]] in CHAIN_TYPES} | \
             {r["Target"] for r in rels if rtype[r["ID"]] in CHAIN_TYPES}
    members = [b for b in ordered if b.ref in linked]
    if len(members) < 2:
        return items
    it = iter(members)
    return [next(it) if b.ref in linked else b for b in items]


def move(b: Box, dx: float, dy: float = 0) -> None:
    b.x += dx
    b.y += dy
    for c in b.children:
        move(c, dx, dy)


def place(b: Box, x: float, y: float) -> None:
    b.x, b.y = x, y
    for i, c in enumerate(b.children):
        c.x = x + PAR_PAD + i * (W + GAP_X / 2)
        c.y = y + PAR_TITLE


def pack(row: Row, x0: float, want: dict[int, float] | None = None) -> None:
    """Place boxes left to right without overlap.

    Without `want`: packed tightly from x0. With `want` (box id -> wanted centre x): each box as
    close to its wanted centre as the boxes to its left allow (the caller re-aligns at the end).
    """
    x = float("-inf") if want else x0
    for b in row.items:
        left = want[id(b)] - b.w / 2 if want else x
        bx = max(left, x)
        place(b, bx, row.y)
        x = bx + b.w + GAP_X


# --- routing -------------------------------------------------------------------------------

def route(rels, nested, boxes, parent, rows) -> list[Line]:
    row_of: dict[str, int] = {}
    for i, row in enumerate(rows):
        for b in row.items:
            row_of[b.ref] = i
            for c in b.children:
                row_of[c.ref] = i
    tops = [r.y for r in rows]
    bottoms = [r.y + r.h for r in rows]

    def channel(i: int) -> float:
        """y of the empty channel just above row i (i == len(rows): below the last row)."""
        if i == 0:
            return tops[0] - 12
        if i == len(rows):
            return bottoms[-1] + 12
        return (bottoms[i - 1] + tops[i]) / 2

    used: dict[tuple[str, float], int] = {}               # spread lines sharing a channel/gutter

    def spread(kind: str, base: float) -> float:
        k = used.get((kind, round(base)), 0)
        used[(kind, round(base))] = k + 1
        return base + LINE_STEP * ((k + 1) // 2) * (1 if k % 2 else -1)

    ports: dict[tuple[str, str], int] = {}                # spread line ends along a box edge

    def port(ref: str, side: str) -> float:
        b = boxes[ref]
        k = ports.get((ref, side), 0)
        ports[(ref, side)] = k + 1
        off = 14 * ((k + 1) // 2) * (1 if k % 2 else -1)
        return b.cx + max(-b.w / 2 + 12, min(b.w / 2 - 12, off))

    def free_x(want: float, r_from: int, r_to: int) -> float:
        """Nearest x to `want` whose vertical line crosses no box in rows r_from..r_to."""
        spans = [(b.x - 10, b.x + b.w + 10) for i in range(r_from, r_to + 1) for b in rows[i].items]
        for d in range(0, 3000, 4):
            for x in (want - d, want + d):
                if all(not lo < x < hi for lo, hi in spans):
                    return x
        return want

    def adjacent(s: str, t: str) -> bool:
        if parent.get(s) != parent.get(t):
            return False
        siblings = boxes[parent[s]].children if s in parent else rows[row_of[s]].items
        ids = [b.ref for b in siblings]
        return abs(ids.index(s) - ids.index(t)) == 1

    lines = []
    for r in rels:
        if r["ID"] in nested:
            continue
        s, t = r["Source"], r["Target"]
        rs, rt = row_of[s], row_of[t]
        if rs == rt:
            if adjacent(s, t):
                bends = []
            else:
                ch = spread("ch", channel(rs))
                bends = [(port(s, "top"), ch), (port(t, "top"), ch)]
        else:
            down = rt > rs
            sx = port(s, "bottom" if down else "top")
            tx = port(t, "top" if down else "bottom")
            ch_s = channel(rs + 1) if down else channel(rs)
            ch_t = channel(rt) if down else channel(rt + 1)
            lo, hi = (rs + 1, rt - 1) if down else (rt + 1, rs - 1)
            if abs(sx - tx) < 2 and (lo > hi or free_x(sx, lo, hi) == sx):
                bends = []                                 # already a clean vertical line
            elif lo > hi:                                  # neighbouring rows: one channel
                ch = spread("ch", ch_s)
                bends = [(sx, ch), (tx, ch)]
            else:
                g = spread("gx", free_x((sx + tx) / 2, lo, hi))
                c1, c2 = spread("ch", ch_s), spread("ch", ch_t)
                bends = [(sx, c1), (g, c1), (g, c2), (tx, c2)]
        lines.append(Line(r["ID"], s, t, bends))
    return lines
