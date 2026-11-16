"""Tests of the automatic layout (layout.py): a box grows in height to show its whole name (#73)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import layout  # noqa: E402
from layout import (BAND_PAD, CHARS_PER_LINE, H, LINE_H, PAR_PAD, PAR_TITLE, ROW_GAP,  # noqa: E402
                    box_height, name_lines)

THREE_LINES = "Customers can free slots they no longer need"   # 13 / 15 / 14 characters
FIVE_LINES = "ADR 0005: Release image built once, accepted, then promoted unchanged"

# Line counts Archi 5.11.0 drew for names of the model, 160 pixels wide, under Xvfb, read from
# a calibration render on 2026-11-17 (#73). The estimate may exceed them by one line.
ARCHI_LINES = [
    ("Cancel a reservation", 1),
    ("Persistence adapter (crate adapters-db)", 2),
    ("Development cost under control", 2),
    ("H. Architecture Change Management", 3),
    ("Healthy, maintainable software", 3),
    ("Refuse cancelling an unknown reservation", 3),
    ("Architecture documented in TOGAF / ArchiMate", 3),
    (THREE_LINES, 3),
    ("ADR 0002: ArchiMate model as text, built into Archi in CI", 4),
    ("ADR 0003: Layered Cargo workspace with enforced dependency direction", 5),
    (FIVE_LINES, 5),
    ("ADR 0006: Pilot and rollout with Podman Quadlet, health checks and automatic rollback", 5),
    ("ADR 0010: OpenAPI specification, spec-first, checked against the running service", 5),
    ("ADR 0008: Atomic schedule changes through one `update` operation on the repository port", 6),
    ("ADR 0009: ArchiMate exchange model as the single source of the architecture "
     "documentation", 6),
]


def latin_lines(name: str) -> int:
    """The wrap of the first version (#73): every character one unit."""
    lines, used = 0, 0
    for word in name.split():
        for i in range(0, len(word), CHARS_PER_LINE):
            piece = len(word[i:i + CHARS_PER_LINE])
            if used and used + 1 + piece <= CHARS_PER_LINE:
                used += 1 + piece
            else:
                lines, used = lines + 1, piece
    return max(lines, 1)


class NameLines(unittest.TestCase):
    def test_short_name_is_one_line(self):
        self.assertEqual(name_lines("Customer"), 1)
        self.assertEqual(name_lines(""), 1)

    def test_exact_fit_is_one_line_and_one_more_character_wraps(self):
        fit = "abcdefgh ijklmnop"
        self.assertEqual(len(fit), CHARS_PER_LINE)
        self.assertEqual(name_lines(fit), 1)
        self.assertEqual(name_lines(fit + "q"), 2)
        self.assertEqual(name_lines("x" * CHARS_PER_LINE), 1)

    def test_long_name_wraps_at_word_breaks(self):
        self.assertEqual(name_lines(THREE_LINES), 3)
        self.assertEqual(name_lines("  Customers   can\nfree slots they no longer need "), 3)

    def test_very_long_word_is_cut_into_line_long_pieces(self):
        self.assertEqual(name_lines("x" * (2 * CHARS_PER_LINE + 6)), 3)
        self.assertEqual(name_lines("ab " + "x" * (2 * CHARS_PER_LINE + 6)), 4)

    def test_east_asian_wide_characters_count_twice(self):
        cjk = "取消预约" * 8 + "取消"                      # 34 characters, no spaces
        self.assertEqual(len(cjk), 34)
        self.assertGreaterEqual(name_lines(cjk), 4)               # Archi draws about 4
        self.assertEqual(name_lines("予約" * 4), 1)                # 16 units fit a line
        self.assertEqual(name_lines("予約" * 4 + "a"), 1)          # 17 units: exact fit
        self.assertEqual(name_lines("予約" * 4 + "取"), 2)         # 18 units: cut before it
        self.assertEqual(name_lines("ＡＢＣＤＥＦＧＨＩ"), 2)          # full-width letters too

    def test_mixed_latin_and_east_asian_name(self):
        self.assertEqual(name_lines("Reservation 予約"), 1)        # 11 + 1 + 4 units
        self.assertEqual(name_lines("Reservation 予約サービス"), 2)  # 11 + 1 + 10 units

    def test_latin_names_count_one_unit_a_character(self):
        for name, _ in ARCHI_LINES:
            with self.subTest(name=name):
                self.assertEqual(name_lines(name), latin_lines(name))

    def test_estimate_is_never_below_what_archi_draws(self):
        for name, drawn in ARCHI_LINES:
            with self.subTest(name=name):
                self.assertGreaterEqual(max(3, name_lines(name)), drawn)

    def test_names_archi_draws_in_three_lines_keep_the_standard_height(self):
        for name, drawn in ARCHI_LINES:
            if drawn <= 3:
                with self.subTest(name=name):
                    self.assertEqual(box_height(name), H)


class BoxHeight(unittest.TestCase):
    def test_up_to_three_lines_keep_the_standard_height(self):
        self.assertEqual(box_height("Customer"), H)
        self.assertEqual(box_height(THREE_LINES), H)

    def test_each_further_line_adds_one_line_height(self):
        self.assertEqual(box_height(THREE_LINES + " now"), H + LINE_H)
        self.assertEqual(box_height(FIVE_LINES), H + 2 * LINE_H)


def lay(names: dict[str, str], types: dict[str, str],
        rels: list[tuple[str, str, str]]) -> layout.ViewLayout:
    """Lay out every element of `types`; rels are (type, source, target)."""
    return layout.layout(list(types), types, names, [
        {"ID": f"id-rel-{i:03}", "Type": t, "Source": s, "Target": d}
        for i, (t, s, d) in enumerate(rels)])


def geometry(v: layout.ViewLayout) -> tuple:
    return ([(b.ref, b.x, b.y, b.w, b.h) for _, b in sorted(v.boxes.items())],
            [(b.label, b.x, b.y, b.w, b.h) for b in v.bands],
            [(ln.rel_id, ln.bends) for ln in v.lines])


# Two layers, a row of three, a nested parent with two children, lines within and across rows.
TYPES = {"g1": "Goal", "g2": "Goal", "g3": "Goal", "r": "Requirement",
         "p": "ApplicationComponent", "c1": "ApplicationComponent", "c2": "ApplicationComponent",
         "s": "ApplicationService"}
RELS = [("Realization", "r", "g1"), ("Realization", "r", "g2"), ("Influence", "g3", "g2"),
        ("Composition", "p", "c1"), ("Composition", "p", "c2"), ("Realization", "c1", "s"),
        ("Realization", "s", "r"), ("Serving", "c2", "s")]
SHORT = {ref: ref.upper() for ref in TYPES}


class Layout(unittest.TestCase):
    def test_a_view_with_only_short_names_is_unchanged(self):
        before = lay(SHORT, TYPES, RELS)
        self.assertTrue(all(b.h == H for b in before.boxes.values() if not b.children))
        three = dict.fromkeys(TYPES, THREE_LINES)
        self.assertEqual(geometry(lay(three, TYPES, RELS)), geometry(before))

    def test_a_row_takes_the_height_of_its_tallest_box(self):
        short = lay(SHORT, TYPES, RELS)
        tall = lay({**SHORT, "g2": FIVE_LINES}, TYPES, RELS)
        g1, g2, g3, r = (tall.boxes[k] for k in ("g1", "g2", "g3", "r"))
        self.assertEqual(g2.h, box_height(FIVE_LINES))
        self.assertEqual((g1.h, g3.h), (H, H))
        self.assertEqual({g1.y, g2.y, g3.y}, {short.boxes["g2"].y})      # top-aligned, not moved
        self.assertEqual(r.y, g2.y + g2.h + ROW_GAP)                      # next row moves down
        grow = g2.h - H
        self.assertEqual(tall.bands[0].h, short.bands[0].h + grow)        # its band grows
        self.assertEqual(tall.bands[1].y, short.bands[1].y + grow)        # later bands move down
        self.assertEqual(tall.boxes["p"].y, short.boxes["p"].y + grow)
        self.assertEqual([b.x for _, b in sorted(tall.boxes.items())],    # order and x unchanged
                         [b.x for _, b in sorted(short.boxes.items())])

    def test_a_nested_parent_grows_with_its_tallest_child(self):
        v = lay({**SHORT, "c2": FIVE_LINES}, TYPES, RELS)
        p, c1, c2 = (v.boxes[k] for k in ("p", "c1", "c2"))
        self.assertEqual(p.children, [c1, c2])
        self.assertEqual(p.h, PAR_TITLE + c2.h + PAR_PAD)
        self.assertEqual((c1.y, c2.y), (p.y + PAR_TITLE, p.y + PAR_TITLE))
        self.assertEqual((c1.h, c2.h), (H, box_height(FIVE_LINES)))
        band = v.bands[1]
        self.assertGreaterEqual(band.y + band.h, p.y + p.h + BAND_PAD)
        self.assertGreater(v.boxes["s"].y, p.y + p.h)                     # the row below moves


if __name__ == "__main__":
    unittest.main()
