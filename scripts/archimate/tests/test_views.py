"""Tests of views.py: the rendering-input hash, the PNG header, views.lock, and the check, update
and dimension comparison of the committed view images (ADR 0009, step 4). No Archi needed: the
"rendered" PNGs are made here.
"""

from __future__ import annotations

import contextlib
import io
import os
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


def hashes(old: str = "", new: str = "", archi: str = ARCHI, text: str = CANONICAL) -> dict[str, str]:
    """Input hashes of the fixture (or `text`) with one text replaced (which must occur in it)."""
    assert old in text, old
    return views.input_hashes(text.replace(old, new, 1).encode(), archi)


# The fixture with a view reference in the manual view, to the main view.
VIEW_REF = CANONICAL.replace(
    "<label>Drawn by hand</label>",
    '<label>Drawn by hand</label>\n          <viewRef ref="id-view-main"/>', 1)


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
        influence = CANONICAL.replace('xsi:type="Triggering"', 'xsi:type="Influence" modifier="+"')
        before, after = hashes(text=influence), hashes('modifier="+"', 'modifier="-"', text=influence)
        self.assertEqual({vid for vid in before if after[vid] != before[vid]}, {"id-view-main"})

    def test_changes_with_the_name_of_a_view_referred_to(self):
        before = hashes(text=VIEW_REF)
        after = hashes("<name xml:lang=\"en\">Main</name>", "<name xml:lang=\"en\">Overview</name>",
                       text=VIEW_REF)
        self.assertEqual({vid for vid in before if after[vid] != before[vid]},
                         {"id-view-hand", "id-view-main"})
        # Without the reference, renaming the main view changes only the main view.
        self.assertChanges("<name xml:lang=\"en\">Main</name>",
                           "<name xml:lang=\"en\">Overview</name>", {"id-view-main"})
        # A view without view references has no "views" key, so its hash is as before.
        self.assertEqual(before["id-view-main"], BASE["id-view-main"])

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

    def test_rejects_a_png_whose_first_chunk_is_not_ihdr(self):
        data = png(10, 10)
        with self.assertRaisesRegex(views.ViewsError, "does not start with an IHDR"):
            views.png_size(data[:12] + b"tEXt" + data[16:])

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
        first = views.LOCK_HEADER.count("\n") + 1
        with self.assertRaisesRegex(views.ViewsError, f"line {first} is not"):
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
        problems = views.check(BASE, lock, images)
        self.assertEqual(problems, ["docs/architecture/views/id-view-gone.png " + views.STRAY])

    def test_image_of_a_view_that_left_the_model(self):
        lock, images = committed()
        only_main = dict(BASE)
        del only_main["id-view-hand"]
        problems = views.check(only_main, lock, images)
        self.assertEqual(len(problems), 2, problems)
        self.assertIn("lists 'id-view-hand', which is not a view", problems[0])
        self.assertIn("id-view-hand.png is the image of 'id-view-hand', which is no longer a view",
                      problems[1])
        self.assertTrue(all(p.endswith(FIX) for p in problems))

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
        return {p.name: p.read_bytes() for p in sorted(self.views.iterdir()) if p.is_file()}

    def test_writes_images_and_lock_then_is_a_no_op(self):
        changes, problems = views.update(BASE, self.views, self.rendered)
        self.assertEqual((len(changes), problems), (3, []))
        first = self.files()
        self.assertEqual(sorted(first), ["id-view-hand.png", "id-view-main.png", "views.lock"])
        images = {k: v for k, v in first.items() if k != "views.lock"}
        self.assertEqual(views.check(BASE, first["views.lock"].decode(), images), [])
        self.render(b"other machine")                  # bytes differ; inputs did not change
        self.assertEqual(views.update(BASE, self.views, self.rendered), ([], []))
        self.assertEqual(self.files(), first)

    def test_rewrites_only_the_changed_view(self):
        views.update(BASE, self.views, self.rendered)
        first = self.files()
        self.render(b"second")
        after = hashes('x="464" y="62"', 'x="465" y="62"')
        changes, _ = views.update(after, self.views, self.rendered)
        self.assertEqual([c.split("/")[-1] for c in changes], ["id-view-main.png", "views.lock"])
        now = self.files()
        self.assertEqual(now["id-view-hand.png"], first["id-view-hand.png"])
        self.assertEqual(now["id-view-main.png"], (self.rendered / "id-view-main.png").read_bytes())

    def test_replaces_a_missing_or_edited_image(self):
        views.update(BASE, self.views, self.rendered)
        (self.views / "id-view-hand.png").write_bytes(png(300, 100, b"edited"))
        (self.views / "id-view-main.png").unlink()
        self.assertEqual(len(views.update(BASE, self.views, self.rendered)[0]), 2)
        self.assertEqual(self.files()["id-view-hand.png"],
                         (self.rendered / "id-view-hand.png").read_bytes())

    def test_removes_the_image_of_a_removed_view(self):
        views.update(BASE, self.views, self.rendered)
        only_main = dict(BASE)
        del only_main["id-view-hand"]
        changes, problems = views.update(only_main, self.views, self.rendered)
        self.assertEqual(problems, [])
        self.assertIn("view 'id-view-hand' left the model", changes[0])
        self.assertEqual(sorted(self.files()), ["id-view-main.png", "views.lock"])
        self.assertEqual(list(views.parse_lock(self.files()["views.lock"].decode())),
                         ["id-view-main"])

    def test_reports_and_keeps_other_files(self):
        views.update(BASE, self.views, self.rendered)
        (self.views / "notes.txt").write_text("x")
        (self.views / "id-view-old.png").write_bytes(png(1, 1))   # not in the lock
        (self.views / "sub").mkdir()
        changes, problems = views.update(BASE, self.views, self.rendered)
        self.assertEqual(changes, [])
        self.assertEqual(problems, [f"docs/architecture/views/{name} {views.STRAY}"
                                    for name in ("id-view-old.png", "notes.txt", "sub")])
        self.assertEqual(sorted(self.files())[:2], ["id-view-hand.png", "id-view-main.png"])
        self.assertTrue((self.views / "notes.txt").exists() and (self.views / "sub").is_dir())

    def test_fails_on_a_lock_that_is_not_utf8(self):
        views.update(BASE, self.views, self.rendered)
        (self.views / "views.lock").write_bytes(b"\xff\xfe")
        with self.assertRaisesRegex(views.ViewsError, "views.lock cannot be read .*delete it"):
            views.update(BASE, self.views, self.rendered)

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

    def test_fails_when_nothing_was_compared(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock, _ = committed()
            for text in (lock, views.LOCK_HEADER, ""):     # no rendered images; empty locks
                lines, problems = views.dims(text, Path(tmp))
                self.assertEqual(lines, [])
                self.assertIn("nothing was compared: views.lock lists no view with a rendered "
                              "image", problems)


class CommandLine(unittest.TestCase):
    def run_main(self, *argv: str) -> tuple[int, str]:
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            return views.main(list(argv)), err.getvalue()

    def test_usage(self):
        self.assertEqual(self.run_main()[0], 2)
        self.assertEqual(self.run_main("--update", ".")[0], 2)

    def repository(self, tmp: str) -> Path:
        """A repository with the fixture model and a rendered report, no views folder yet."""
        root = Path(tmp)
        (root / "docs/architecture").mkdir(parents=True)
        (root / "docs/architecture/model.xml").write_text(CANONICAL, encoding="utf-8")
        (root / "tools").mkdir()
        (root / "tools/archi.env").write_text(f"ARCHI_VERSION={ARCHI}\n", encoding="utf-8")
        images = root / "report/id-model-fixture/images"
        images.mkdir(parents=True)
        for vid in BASE:
            (images / f"{vid}.png").write_bytes(png(50, 40))
        return root

    def test_bad_lock_or_folder_ends_in_a_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.repository(tmp)
            report = str(root / "report")
            self.assertEqual(self.run_main("--update", tmp, report)[0], 0)
            lock = root / "docs/architecture/views/views.lock"
            text = lock.read_bytes()
            lock.write_bytes(b"\xff" + text)
            for argv in (("--check", tmp), ("--update", tmp, report), ("--dims", tmp, report)):
                code, err = self.run_main(*argv)
                self.assertEqual(code, 1, argv)
                self.assertIn("views.lock cannot be read", err)
                self.assertIn("delete it, then run `just model`", err)
            lock.write_bytes(text)
            if os.geteuid() != 0:                        # root can read a mode-000 file
                lock.chmod(0)
                code, err = self.run_main("--check", tmp)
                lock.chmod(0o644)
                self.assertEqual(code, 1)
                self.assertIn("views.lock cannot be read", err)
            (root / "docs/architecture/views/sub").mkdir()
            code, err = self.run_main("--check", tmp)
            self.assertEqual(code, 1)
            self.assertIn("views/sub is a folder: was not written by `just model`", err)
            code, err = self.run_main("--update", tmp, report)
            self.assertEqual(code, 1)
            self.assertIn("views/sub was not written by `just model`", err)

    def test_check_update_and_dims_on_a_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.repository(tmp)
            images = root / "report/id-model-fixture/images"
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
