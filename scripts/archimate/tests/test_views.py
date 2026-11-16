"""Tests of views.py: the rendering-input hash, the PNG header, views.lock, and the check, update
and dimension comparison of the committed view images (ADR 0009, step 4). No Archi needed: the
"rendered" PNGs are made here.
"""

from __future__ import annotations

import contextlib
import io
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import views  # noqa: E402

CANONICAL = (HERE / "fixtures" / "canonical.xml").read_text(encoding="utf-8")
ARCHI = "5.11.0"
FIX = "run `just model` and commit `docs/architecture/views/`"


def png(width: int, height: int, body: bytes = b"") -> bytes:
    """A PNG signature and IHDR chunk (enough for the header reader), then `body` and IEND."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return views.PNG_SIGNATURE + chunk(b"IHDR", ihdr) + chunk(b"tEXt", body) + chunk(b"IEND", b"")


def hashes(old: str = "", new: str = "", archi: str = ARCHI) -> dict[str, str]:
    """Input hashes of the fixture with one text replaced (which must occur in it)."""
    assert old in CANONICAL, old
    return views.input_hashes(CANONICAL.replace(old, new, 1).encode(), archi)


BASE = hashes()


class RenderingInputs(unittest.TestCase):
    def assertChanges(self, old: str, new: str, changed: set[str]):
        after = hashes(old, new)
        self.assertEqual({vid for vid in BASE if after[vid] != BASE[vid]}, changed)

    def test_one_hash_per_view_and_stable(self):
        self.assertEqual(sorted(BASE), ["id-view-hand", "id-view-main"])
        self.assertEqual(hashes(), BASE)

    def test_changes_with_the_name_or_type_of_an_element_drawn(self):
        self.assertChanges("<name xml:lang=\"en\">Web app</name>", "<name xml:lang=\"en\">Web</name>",
                           {"id-view-hand", "id-view-main"})
        self.assertChanges('"id-bus-proc-pay" xsi:type="BusinessProcess"',
                           '"id-bus-proc-pay" xsi:type="BusinessFunction"', {"id-view-main"})

    def test_changes_with_the_type_name_and_line_attributes_of_a_relationship_drawn(self):
        self.assertChanges('xsi:type="Triggering"', 'xsi:type="Flow"', {"id-view-main"})
        self.assertChanges("<name xml:lang=\"en\">calls</name>", "<name xml:lang=\"en\">uses</name>",
                           {"id-view-hand", "id-view-main"})
        self.assertChanges('accessType="Access"', 'accessType="Read"', {"id-view-main"})
        self.assertChanges('isDirected="true"', "", {"id-view-hand", "id-view-main"})

    def test_changes_with_the_view_itself(self):
        self.assertChanges('x="464" y="62"', 'x="465" y="62"', {"id-view-main"})
        self.assertChanges("<name>Hand-arranged</name>", "<name>By hand</name>", {"id-view-hand"})
        self.assertChanges('<view identifier="id-view-main" xsi:type="Diagram">',
                           '<view identifier="id-view-main" xsi:type="Diagram" viewpoint="Layered">',
                           {"id-view-main"})
        self.assertChanges('<bendpoint x="149" y="346"/>', "", {"id-view-main"})
        self.assertChanges('<fillColor r="200"', '<fillColor r="100"', {"id-view-hand"})

    def test_changes_with_the_archi_version(self):
        after = hashes(archi="5.12.0")
        self.assertTrue(all(after[vid] != BASE[vid] for vid in BASE))

    def test_unchanged_by_documentation_properties_and_what_is_not_drawn(self):
        self.assertChanges("Serves the pages.", "Serves every page.", set())
        self.assertChanges("<value xml:lang=\"en\">crates/web</value>",
                           "<value xml:lang=\"en\">crates/www</value>", set())
        self.assertChanges("<name xml:lang=\"en\">Main</name>",
                           "<name xml:lang=\"en\">Main</name>\n        <documentation xml:lang=\"en\">"
                           "About the view.</documentation>", set())
        self.assertChanges("<value>manual</value>", "<value>manual </value>", set())
        # Not drawn in the hand view: changes the main view only.
        self.assertChanges("<name xml:lang=\"en\">Pay</name>", "<name xml:lang=\"en\">Settle</name>",
                           {"id-view-main"})
        # A relationship that no view draws.
        self.assertChanges('id-rel-001" xsi:type="Composition"', 'id-rel-001" xsi:type="Aggregation"',
                           set())

    def test_definition_is_one_json_text(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring(CANONICAL.encode())
        view = next(v for v in root.iter(f"{views._Q}view") if v.get("identifier") == "id-view-hand")
        text = views.rendering_inputs(root, view, ARCHI).decode()
        self.assertTrue(text.startswith('{"archi":"5.11.0","elements":[["id-app-comp-api",'
                                        '"ApplicationComponent","API"],'), text)
        self.assertIn('"relationships":[["id-rel-005","Association","calls","","true",""]]', text)
        self.assertNotIn("manual", text)
        self.assertEqual(views.sha256(text.encode()), BASE["id-view-hand"])


class PngHeader(unittest.TestCase):
    def test_reads_width_and_height(self):
        self.assertEqual(views.png_size(png(1494, 1028)), (1494, 1028))

    def test_rejects_a_file_that_is_not_a_png(self):
        with self.assertRaisesRegex(views.ViewsError, "not a PNG"):
            views.png_size(b"GIF89a" + bytes(30))
        with self.assertRaisesRegex(views.ViewsError, "not a PNG"):
            views.png_size(b"")

    def test_rejects_a_truncated_png(self):
        for size in (8, 16, 23):
            with self.assertRaisesRegex(views.ViewsError, "truncated"):
                views.png_size(png(10, 10)[:size])

    def test_rejects_a_zero_size(self):
        with self.assertRaisesRegex(views.ViewsError, "zero"):
            views.png_size(png(0, 10))


class Lock(unittest.TestCase):
    ENTRIES = {"id-view-b": views.Entry("1" * 64, "2" * 64, 10, 20),
               "id-view-a": views.Entry("3" * 64, "4" * 64, 30, 40)}

    def test_round_trip_in_view_order(self):
        text = views.format_lock(self.ENTRIES)
        self.assertTrue(text.startswith(views.LOCK_HEADER))
        body = text[len(views.LOCK_HEADER):].splitlines()
        self.assertEqual(body, [f"id-view-a {'3' * 64} {'4' * 64} 30x40",
                                f"id-view-b {'1' * 64} {'2' * 64} 10x20"])
        self.assertEqual(views.parse_lock(text), self.ENTRIES)
        self.assertEqual(views.format_lock(views.parse_lock(text)), text)

    def test_rejects_a_malformed_line(self):
        text = views.format_lock(self.ENTRIES).replace("30x40", "30 by 40")
        with self.assertRaisesRegex(views.ViewsError, "line 6 is not"):
            views.parse_lock(text)

    def test_rejects_a_view_listed_twice(self):
        text = views.format_lock(self.ENTRIES)
        with self.assertRaisesRegex(views.ViewsError, "listed twice"):
            views.parse_lock(text + text.splitlines()[-1] + "\n")


def committed() -> tuple[str, dict[str, bytes]]:
    """A lock and images that match the fixture's two views."""
    images = {"id-view-hand.png": png(300, 100, b"hand"), "id-view-main.png": png(640, 600, b"main")}
    entries = {vid: views.entry_for(h, images[f"{vid}.png"]) for vid, h in BASE.items()}
    return views.format_lock(entries), images


class Check(unittest.TestCase):
    def assertOneProblem(self, problems: list[str], *parts: str):
        self.assertEqual(len(problems), 1, problems)
        for part in parts:
            self.assertIn(part, problems[0])
        self.assertTrue(problems[0].endswith(FIX), problems[0])

    def test_passes_when_all_match(self):
        lock, images = committed()
        self.assertEqual(views.check(BASE, lock, images), [])

    def test_view_changed_without_its_image(self):
        lock, images = committed()
        after = hashes('x="464" y="62"', 'x="465" y="62"')
        self.assertOneProblem(views.check(after, lock, images),
                              "view 'id-view-main' changed since its image was rendered")

    def test_replaced_or_edited_png(self):
        lock, images = committed()
        images["id-view-hand.png"] = png(300, 100, b"edited")
        self.assertOneProblem(views.check(BASE, lock, images), "view 'id-view-hand'",
                              "is not the image in views.lock")
        images["id-view-hand.png"] = b"not an image"
        self.assertOneProblem(views.check(BASE, lock, images), "view 'id-view-hand'", "not a PNG")

    def test_deleted_png(self):
        lock, images = committed()
        del images["id-view-main.png"]
        self.assertOneProblem(views.check(BASE, lock, images), "view 'id-view-main'",
                              "id-view-main.png is missing")

    def test_stray_png(self):
        lock, images = committed()
        images["id-view-gone.png"] = png(1, 1)
        self.assertOneProblem(views.check(BASE, lock, images),
                              "id-view-gone.png belongs to no view of the model")

    def test_hand_edited_lock(self):
        lock, images = committed()
        sizes = lock.replace(" 640x600", " 641x600")
        self.assertOneProblem(views.check(BASE, sizes, images), "view 'id-view-main'",
                              "is 640x600, views.lock says 641x600")
        inputs = lock.replace(f"id-view-hand {BASE['id-view-hand']}", f"id-view-hand {'0' * 64}")
        self.assertOneProblem(views.check(BASE, inputs, images), "view 'id-view-hand' changed")
        lines = lock.splitlines(keepends=True)
        reordered = "".join(lines[:-2] + [lines[-1], lines[-2]])
        self.assertOneProblem(views.check(BASE, reordered, images), "not in its generated form")
        self.assertOneProblem(views.check(BASE, lock + "id-view-x\n", images), "views.lock",
                              "is not '<view-id>")

    def test_lock_entry_without_a_view_and_view_without_entry(self):
        lock, images = committed()
        only_main = hashes()
        del only_main["id-view-hand"]
        del images["id-view-hand.png"]
        self.assertOneProblem(views.check(only_main, lock, images),
                              "views.lock lists 'id-view-hand', which is not a view")
        lock = views.format_lock({k: v for k, v in views.parse_lock(lock).items()
                                  if k == "id-view-main"})
        images["id-view-hand.png"] = png(300, 100, b"hand")
        self.assertOneProblem(views.check(BASE, lock, images),
                              "view 'id-view-hand' has no entry in views.lock")

    def test_missing_lock(self):
        self.assertOneProblem(views.check(BASE, None, {}), "views.lock is missing")


class Update(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.views = Path(tmp.name) / "views"
        self.rendered = Path(tmp.name) / "rendered"
        self.rendered.mkdir()
        self.render(b"first")

    def render(self, body: bytes):
        for vid in BASE:
            (self.rendered / f"{vid}.png").write_bytes(png(300, 100, body + vid.encode()))

    def files(self) -> dict[str, bytes]:
        return {p.name: p.read_bytes() for p in sorted(self.views.iterdir())}

    def test_writes_images_and_lock_then_is_a_no_op(self):
        self.assertEqual(len(views.update(BASE, self.views, self.rendered)), 3)
        first = self.files()
        self.assertEqual(sorted(first), ["id-view-hand.png", "id-view-main.png", "views.lock"])
        images = {k: v for k, v in first.items() if k != "views.lock"}
        self.assertEqual(views.check(BASE, first["views.lock"].decode(), images), [])
        self.render(b"other machine")                  # bytes differ; inputs did not change
        self.assertEqual(views.update(BASE, self.views, self.rendered), [])
        self.assertEqual(self.files(), first)

    def test_rewrites_only_the_changed_view(self):
        views.update(BASE, self.views, self.rendered)
        first = self.files()
        self.render(b"second")
        after = hashes('x="464" y="62"', 'x="465" y="62"')
        changes = views.update(after, self.views, self.rendered)
        self.assertEqual([c.split("/")[-1] for c in changes], ["id-view-main.png", "views.lock"])
        now = self.files()
        self.assertEqual(now["id-view-hand.png"], first["id-view-hand.png"])
        self.assertEqual(now["id-view-main.png"], (self.rendered / "id-view-main.png").read_bytes())

    def test_replaces_a_missing_or_edited_image(self):
        views.update(BASE, self.views, self.rendered)
        (self.views / "id-view-hand.png").write_bytes(png(300, 100, b"edited"))
        (self.views / "id-view-main.png").unlink()
        self.assertEqual(len(views.update(BASE, self.views, self.rendered)), 2)
        self.assertEqual(self.files()["id-view-hand.png"],
                         (self.rendered / "id-view-hand.png").read_bytes())

    def test_removes_images_of_removed_views_and_strays(self):
        views.update(BASE, self.views, self.rendered)
        (self.views / "notes.txt").write_text("x")
        only_main = dict(BASE)
        del only_main["id-view-hand"]
        views.update(only_main, self.views, self.rendered)
        self.assertEqual(sorted(self.files()), ["id-view-main.png", "views.lock"])
        self.assertEqual(list(views.parse_lock(self.files()["views.lock"].decode())),
                         ["id-view-main"])

    def test_fails_when_archi_rendered_no_image(self):
        (self.rendered / "id-view-main.png").unlink()
        with self.assertRaisesRegex(views.ViewsError, "no image for view 'id-view-main'"):
            views.update(BASE, self.views, self.rendered)


class Dims(unittest.TestCase):
    def test_equal_different_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            rendered = Path(tmp)
            lock, images = committed()
            (rendered / "id-view-hand.png").write_bytes(png(300, 100, b"other bytes"))
            lines, problems = views.dims(lock, rendered)
            self.assertEqual(lines, ["id-view-hand: rendered 300x100, lock 300x100 equal"])
            self.assertEqual(len(problems), 1)
            self.assertIn("view 'id-view-main': no rendered image", problems[0])
            (rendered / "id-view-main.png").write_bytes(png(642, 600))
            lines, problems = views.dims(lock, rendered)
            self.assertEqual(lines[1], "id-view-main: rendered 642x600, lock 640x600 DIFFERENT")
            self.assertEqual(problems, ["view 'id-view-main': rendered 642x600 here, but "
                                        "views.lock says 640x600"])


class CommandLine(unittest.TestCase):
    def run_main(self, *argv: str) -> tuple[int, str]:
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            return views.main(list(argv)), err.getvalue()

    def test_usage(self):
        self.assertEqual(self.run_main()[0], 2)
        self.assertEqual(self.run_main("--update", ".")[0], 2)

    def test_check_update_and_dims_on_a_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs/architecture").mkdir(parents=True)
            (root / "docs/architecture/model.xml").write_text(CANONICAL, encoding="utf-8")
            (root / "tools").mkdir()
            (root / "tools/archi.env").write_text(f"ARCHI_VERSION={ARCHI}\n", encoding="utf-8")
            images = root / "report/id-model-fixture/images"
            images.mkdir(parents=True)
            for vid in BASE:
                (images / f"{vid}.png").write_bytes(png(50, 40))
            code, err = self.run_main("--check", tmp)
            self.assertEqual(code, 1)
            self.assertIn("views.lock is missing", err)
            self.assertEqual(self.run_main("--update", tmp, str(root / "report"))[0], 0)
            self.assertEqual(self.run_main("--check", tmp), (0, ""))
            self.assertEqual(self.run_main("--dims", tmp, str(root / "report")), (0, ""))
            (images / "id-view-main.png").write_bytes(png(51, 40))
            code, err = self.run_main("--dims", tmp, str(root / "report"))
            self.assertEqual(code, 1)
            self.assertIn("rendered 51x40 here, but views.lock says 50x40", err)


if __name__ == "__main__":
    unittest.main()
