"""Tests of the model reader (exchange.read) and the model checks run by `just model-check`:
check_relationships.py and check_model.py (ADR 0009).

The relationship rules come from the pinned Archi install in the real check; here a small rule
table stands in for them, so these tests need no Archi.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import check_model  # noqa: E402
import check_relationships  # noqa: E402
import exchange  # noqa: E402
import xsd_check  # noqa: E402

CANONICAL = (HERE / "fixtures" / "canonical.xml").read_bytes()
MODEL = exchange.read(CANONICAL)


def edited(old: str, new: str) -> exchange.Model:
    """The canonical fixture with one text replaced (which must occur in it)."""
    text = CANONICAL.decode()
    assert old in text, old
    return exchange.read(text.replace(old, new, 1).encode())


class Reader(unittest.TestCase):
    def test_reads_elements_relationships_and_view_members(self):
        self.assertEqual(MODEL.identifier, "id-model-fixture")
        self.assertEqual(MODEL.elements["id-app-data-booking"], "DataObject")
        self.assertIn({"ID": "id-rel-003", "Type": "Access", "Source": "id-app-comp-core",
                       "Target": "id-app-data-booking", "Name": ""}, MODEL.relationships)
        self.assertEqual(sorted(MODEL.views["id-view-main"]), sorted(MODEL.elements))
        self.assertEqual(MODEL.views["id-view-hand"], ["id-app-comp-web", "id-app-comp-api"])

    def test_reads_names_and_documentation(self):
        self.assertEqual(MODEL.names["id-app-comp-web"], "Web app")
        self.assertEqual(MODEL.documentation["id-app-comp-web"], "Serves the pages.")
        self.assertNotIn("id-app-comp-core", MODEL.documentation)

    def test_reads_properties_by_definition_name(self):
        self.assertIn(("id-app-comp-web", "Crate", "crates/web"), MODEL.properties)
        self.assertIn(("id-view-hand", "Layout", "manual"), MODEL.properties)

    def test_connections_name_the_elements_they_join(self):
        hand = [c for c in MODEL.connections if c.view == "id-view-hand"]
        self.assertEqual([(c.relationship, c.source, c.target) for c in hand],
                         [("id-rel-005", "id-app-comp-web", "id-app-comp-api")])

    def test_identifiers_are_model_elements_relationships_and_views(self):
        ids = MODEL.identifiers()
        for ident in ("id-model-fixture", "id-app-comp-web", "id-rel-001", "id-view-main"):
            self.assertIn(ident, ids)
        self.assertNotIn("id-view-main-n-id-app-comp-web", ids)

    def test_not_well_formed_is_a_format_error(self):
        with self.assertRaises(exchange.FormatError):
            exchange.read(b"<model")


class Relationships(unittest.TestCase):
    RULES = {("ApplicationComponent", "ApplicationComponent"): {"CompositionRelationship",
                                                                "AssociationRelationship"},
             ("ApplicationComponent", "DataObject"): {"AccessRelationship"},
             ("ApplicationService", "BusinessProcess"): {"ServingRelationship"},
             ("BusinessProcess", "BusinessProcess"): {"TriggeringRelationship"},
             ("ApplicationComponent", "ApplicationService"): {"RealizationRelationship"}}
    TYPES = {"CompositionRelationship", "AssociationRelationship", "AccessRelationship",
             "ServingRelationship", "TriggeringRelationship", "RealizationRelationship"}

    def check(self, model: exchange.Model) -> list[str]:
        return check_relationships.check(model, self.RULES, self.TYPES)

    def test_allowed_relationships_pass(self):
        self.assertEqual(self.check(MODEL), [])

    def test_relationship_not_allowed_between_its_types_names_the_allowed_ones(self):
        model = edited('xsi:type="Triggering"', 'xsi:type="Serving"')
        self.assertEqual(self.check(model), [
            "id-rel-004: Serving is not allowed from BusinessProcess ('id-bus-proc-book') to "
            "BusinessProcess ('id-bus-proc-pay'); allowed: Triggering"])

    def test_unknown_end_and_unknown_type_are_reported(self):
        model = edited('xsi:type="Triggering" source="id-bus-proc-book" target="id-bus-proc-pay"',
                       'xsi:type="Triggers" source="id-bus-proc-book" target="id-nope"')
        problems = self.check(model)
        self.assertIn("id-rel-004: Target 'id-nope' is not an element ID", problems)
        self.assertIn("id-rel-004: unknown relationship type 'Triggers'", problems)


class ModelRules(unittest.TestCase):
    def test_the_fixture_passes(self):
        self.assertEqual(check_model.id_convention(MODEL), [])
        self.assertEqual(check_model.views(MODEL), [])

    def test_identifiers_must_follow_the_convention(self):
        model = edited('identifier="id-app-comp-web"', 'identifier="id-web"')
        model.relationships[0]["ID"] = "rel-1"
        model.views["view-x"] = []
        problems = "\n".join(check_model.id_convention(model))
        self.assertIn("element 'id-web'", problems)
        self.assertIn("relationship 'rel-1'", problems)
        self.assertIn("view 'view-x'", problems)

    def test_model_identifier_must_follow_the_convention(self):
        model = edited('identifier="id-model-fixture"', 'identifier="id-fixture"')
        self.assertEqual(check_model.id_convention(model), [
            "model 'id-fixture' does not follow the ID convention id-model-<slug>"])

    def test_view_member_must_be_an_element(self):
        model = edited('elementRef="id-app-comp-api" x="200"', 'elementRef="id-app-comp-gone" x="200"')
        self.assertEqual(check_model.views(model)[0],
                         "view 'id-view-hand': member 'id-app-comp-gone' is not an element of the model")

    def test_connection_must_join_its_relationships_ends(self):
        model = edited('source="hand-n1" target="hand-n2"', 'source="hand-n2" target="hand-n1"')
        self.assertEqual(check_model.views(model), [
            "view 'id-view-hand': connection 'hand-c1' joins 'id-app-comp-api' → 'id-app-comp-web', "
            "but id-rel-005 joins 'id-app-comp-web' → 'id-app-comp-api'"])

    def test_connection_must_refer_to_a_relationship(self):
        model = edited('relationshipRef="id-rel-005"', 'relationshipRef="id-rel-099"')
        self.assertEqual(check_model.views(model), [
            "view 'id-view-hand': connection 'hand-c1' refers to unknown relationship 'id-rel-099'"])

    def test_plain_line_in_a_manual_view_is_not_a_connection_problem(self):
        model = edited('xsi:type="Relationship" relationshipRef="id-rel-005"', 'xsi:type="Line"')
        line = next(c for c in model.connections if c.identifier == "hand-c1")
        self.assertEqual(line.relationship, "")
        self.assertEqual(check_model.views(model), [])

    def test_view_property_must_name_a_view(self):
        model = exchange.read(CANONICAL)
        model.properties += [("id-app-comp-web", "View", "id-view-main"),
                             ("id-app-comp-web", "View", "id-view-gone")]
        self.assertEqual(check_model.views(model), [
            "'id-app-comp-web': property View = 'id-view-gone' names no view of the model"])


class AdrViews(unittest.TestCase):
    @staticmethod
    def with_adr() -> exchange.Model:
        """The fixture plus ADR 0001, linked from id-app-comp-web, with a view of the two."""
        model = exchange.read(CANONICAL)
        model.elements["id-mot-adr-0001"] = "Constraint"
        model.relationships.append({"ID": "id-rel-900", "Type": "Realization",
                                    "Source": "id-app-comp-web", "Target": "id-mot-adr-0001",
                                    "Name": ""})
        model.views["id-view-adr-0001"] = ["id-mot-adr-0001", "id-app-comp-web"]
        model.properties.append(("id-mot-adr-0001", "View", "id-view-adr-0001"))
        return model

    def test_the_fixture_and_the_real_model_pass(self):
        self.assertEqual(check_model.adr_views(MODEL), [])
        self.assertEqual(check_model.adr_views(self.with_adr()), [])
        self.assertEqual(check_model.adr_views(exchange.read(REAL_MODEL.read_bytes())), [])

    def test_an_adr_without_a_view_property_is_reported(self):
        model = self.with_adr()
        model.properties.pop()
        self.assertEqual(check_model.adr_views(model), [
            "ADR 'id-mot-adr-0001': needs exactly one View property, has 0"])

    def test_two_view_properties_are_reported(self):
        model = self.with_adr()
        model.properties.append(("id-mot-adr-0001", "View", "id-view-main"))
        self.assertEqual(check_model.adr_views(model), [
            "ADR 'id-mot-adr-0001': needs exactly one View property, has 2"])

    def test_a_linked_element_missing_from_the_view_is_reported(self):
        model = self.with_adr()
        model.views["id-view-adr-0001"] = ["id-mot-adr-0001"]
        self.assertIn("view 'id-view-adr-0001' is missing: id-app-comp-web",
                      check_model.adr_views(model)[0])

    def test_an_element_that_is_not_linked_in_the_view_is_reported(self):
        model = self.with_adr()
        model.views["id-view-adr-0001"].append("id-app-comp-api")
        self.assertIn("view 'id-view-adr-0001' must not be shown: id-app-comp-api",
                      check_model.adr_views(model)[0])

    def test_a_source_of_another_relationship_type_is_not_a_member(self):
        model = self.with_adr()
        model.relationships[-1]["Type"] = "Association"
        problems = "\n".join(check_model.adr_views(model))
        self.assertIn("must not be shown: id-app-comp-web", problems)


REAL_MODEL = HERE.parents[2] / "docs" / "architecture" / "model.xml"


def releases_band() -> exchange.Node:
    """The lower band of the real releases view, which widens with each release recorded."""
    return next(n for n in exchange.read(REAL_MODEL.read_bytes()).nodes
                if n.identifier == "id-view-releases-band-1")


class ManualViews(unittest.TestCase):
    def test_the_fixture_and_the_real_releases_view_pass(self):
        self.assertEqual(check_model.manual_views(MODEL), [])
        real = exchange.read(REAL_MODEL.read_bytes())
        self.assertIn(("id-view-releases", "Layout", "manual"), real.properties)
        self.assertEqual(check_model.manual_views(real), [])

    def test_a_missing_connection_is_reported(self):
        real = exchange.read(REAL_MODEL.read_text(encoding="utf-8").replace(
            'xsi:type="Relationship" relationshipRef="id-rel-140"', 'xsi:type="Line"', 1).encode())
        self.assertEqual(check_model.manual_views(real), [
            "view 'id-view-releases' (Layout = manual): relationship id-rel-140 joins "
            "'id-impl-plat-v0-1-0' and 'id-impl-plat-v0-2-0', both drawn, but it has no connection"])

    def test_an_extra_connection_is_reported(self):
        model = exchange.read(CANONICAL)
        model.relationships = [r for r in model.relationships if r["ID"] != "id-rel-005"]
        self.assertEqual(check_model.manual_views(model), [
            "view 'id-view-hand' (Layout = manual): the connection of relationship id-rel-005 is "
            "drawn, but the model has no such relationship between two members of the view"])

    def test_a_box_outside_its_band_is_reported(self):
        text = REAL_MODEL.read_text(encoding="utf-8")
        old = 'elementRef="id-impl-plat-v0-2-1" x="920" y="219"'
        self.assertIn(old, text)
        band = releases_band()
        x = band.x + band.w + 1
        model = exchange.read(text.replace(old, f'elementRef="id-impl-plat-v0-2-1" x="{x}" y="400"').encode())
        self.assertEqual(check_model.manual_views(model), [
            "view 'id-view-releases' (Layout = manual): node 'id-view-releases-n-id-impl-plat-v0-2-1'"
            f" ({x},400 160x55) is not inside its parent 'id-view-releases-band-1'"
            f" ({band.x},{band.y} {band.w}x{band.h})"])

    def releases(self, x: int = 920, y: int = 219, w: int = 160, h: int = 55) -> exchange.Model:
        text = REAL_MODEL.read_text(encoding="utf-8")
        old = 'elementRef="id-impl-plat-v0-2-1" x="920" y="219" w="160" h="55"'
        self.assertIn(old, text)
        return exchange.read(text.replace(
            old, f'elementRef="id-impl-plat-v0-2-1" x="{x}" y="{y}" w="{w}" h="{h}"').encode())

    def test_a_box_exactly_flush_with_its_parent_passes(self):
        band = releases_band()
        right, bottom = band.x + band.w - 160, band.y + band.h - 55
        self.assertEqual(check_model.manual_views(self.releases(x=right, y=bottom)), [])
        self.assertEqual(check_model.manual_views(
            self.releases(x=band.x, y=band.y, w=band.w, h=band.h)), [])

    def test_a_box_one_pixel_over_any_edge_fails(self):
        band = releases_band()
        right, bottom = band.x + band.w - 160, band.y + band.h - 55
        for what, box in (("right", dict(x=right + 1, y=bottom)),
                          ("bottom", dict(x=right, y=bottom + 1)),
                          ("left", dict(x=band.x - 1, y=bottom)),
                          ("top", dict(x=right, y=band.y - 1))):
            with self.subTest(edge=what):
                problems = check_model.manual_views(self.releases(**box))
                self.assertEqual(len(problems), 1, problems)
                self.assertIn("node 'id-view-releases-n-id-impl-plat-v0-2-1'", problems[0])
                self.assertIn("is not inside its parent 'id-view-releases-band-1'", problems[0])

    def test_an_automatic_view_is_not_checked(self):
        model = exchange.read(REAL_MODEL.read_bytes())
        model.properties = [p for p in model.properties if p[1:] != ("Layout", "manual")]
        self.assertEqual(check_model.manual_views(model), [])
        model.connections = [c for c in model.connections if c.view != "id-view-releases"]
        node = next(n for n in model.nodes
                    if n.identifier == "id-view-releases-n-id-impl-plat-v0-2-1")
        band = releases_band()
        node.x, node.y = band.x + band.w + 1, 400
        self.assertEqual(check_model.manual_views(model), [])

    def test_a_relationship_drawn_twice_is_reported(self):
        model = exchange.read(CANONICAL)
        model.connections.append(next(c for c in model.connections if c.view == "id-view-hand"))
        self.assertEqual(check_model.manual_views(model), [
            "view 'id-view-hand' (Layout = manual): relationship id-rel-005 is drawn more than once"])

    def test_a_bound_that_is_not_a_whole_number_is_a_clear_error(self):
        text = CANONICAL.decode().replace('x="200" y="10"', 'x="2.5" y="10"', 1)
        with self.assertRaises(exchange.FormatError) as err:
            exchange.read(text.encode())
        self.assertEqual(err.exception.problems, [
            "view 'id-view-hand': node 'hand-n2' has a bound that is not a whole number "
            "(x, y, w and h are integers)"])

    def test_main_exits_non_zero_on_a_manual_view_problem(self):
        out, err = io.StringIO(), io.StringIO()
        text = CANONICAL.decode().replace('xsi:type="Relationship" relationshipRef="id-rel-005"',
                                          'xsi:type="Line"', 1)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "model.xml").write_text(text, encoding="utf-8")
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                    mock.patch.object(xsd_check, "viewpoints", return_value={"Layered"}):
                code = check_model.main([str(Path(tmp) / "model.xml"), tmp, "archi"])
        self.assertEqual(code, 1)
        self.assertIn("view 'id-view-hand' (Layout = manual): relationship id-rel-005", err.getvalue())
        self.assertNotIn("manual views", out.getvalue())


class Viewpoints(unittest.TestCase):
    KNOWN = {"Layered", "Motivation"}

    def test_known_viewpoint_and_no_viewpoint_pass(self):
        model = edited('identifier="id-view-main" xsi:type="Diagram"',
                       'identifier="id-view-main" xsi:type="Diagram" viewpoint="Layered"')
        self.assertEqual(model.viewpoints, {"id-view-main": "Layered"})
        self.assertEqual(check_model.viewpoints(model, self.KNOWN), [])

    def test_unknown_viewpoint_fails_and_lists_the_known_ones(self):
        model = edited('identifier="id-view-main" xsi:type="Diagram"',
                       'identifier="id-view-main" xsi:type="Diagram" viewpoint="Motivational"')
        self.assertEqual(check_model.viewpoints(model, self.KNOWN), [
            "view 'id-view-main': viewpoint 'Motivational' is not an ArchiMate viewpoint; one of: "
            "Layered, Motivation"])


PINS = xsd_check.read_env(xsd_check.ENV_FILE)
ARCHI_HOME = xsd_check.archi_home(PINS)


@unittest.skipUnless(any((ARCHI_HOME / "plugins").glob("org.opengroup.archimate.xmlexchange_*.jar")),
                     "needs the pinned Archi (run ./bootstrap.sh); just model-check fails without it")
class ViewpointsFromTheSchema(unittest.TestCase):
    def test_names_come_from_the_pinned_schema(self):
        known = xsd_check.viewpoints(ARCHI_HOME, PINS)
        self.assertIn("Motivation", known)
        self.assertIn("Business Process Cooperation", known)
        self.assertNotIn("Motivational", known)


class DocumentReferences(unittest.TestCase):
    def refs(self, text: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "togaf").mkdir()
            (Path(tmp) / "togaf" / "a.md").write_text(text, encoding="utf-8")
            return check_model.doc_refs(MODEL, Path(tmp))

    def test_known_ids_in_backticks_resolve(self):
        self.assertEqual(self.refs("`id-app-comp-web` serves `id-view-main` via `id-rel-005`."), [])

    def test_unknown_id_names_the_page(self):
        problems = self.refs("See `id-app-comp-gone`; id-not-in-backticks is ignored.")
        self.assertEqual(len(problems), 1)
        self.assertIn("a.md: id-app-comp-gone is mentioned but is not in the model", problems[0])

    def test_unknown_id_in_documentation_names_its_owner(self):
        model = edited("Serves the pages.", "Serves `id-app-comp-web` and `id-app-comp-gone`.")
        with tempfile.TemporaryDirectory() as tmp:
            problems = check_model.doc_refs(model, Path(tmp))
        self.assertEqual(len(problems), 1)
        self.assertIn("id-app-comp-gone is mentioned but is not in the model", problems[0])
        self.assertIn("documentation of 'id-app-comp-web'", problems[0])


class CommandLine(unittest.TestCase):
    def run_main(self, text: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "model.xml").write_bytes(CANONICAL)
            (Path(tmp) / "doc.md").write_text(text, encoding="utf-8")
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                    mock.patch.object(xsd_check, "viewpoints", return_value={"Layered"}):
                code = check_model.main([str(Path(tmp) / "model.xml"), tmp, "archi"])
        return code, out.getvalue(), err.getvalue()

    def test_all_checks_pass_with_one_line_each(self):
        code, out, _ = self.run_main("`id-app-comp-web`")
        self.assertEqual(code, 0)
        self.assertEqual(len(out.splitlines()), 6)

    def test_a_problem_fails_and_is_listed(self):
        code, _, err = self.run_main("`id-app-comp-gone`")
        self.assertEqual(code, 1)
        self.assertIn("id-app-comp-gone", err)

    def test_viewpoints_that_cannot_be_read_are_a_setup_error(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), mock.patch.object(
                xsd_check, "viewpoints", side_effect=xsd_check.CheckError("run ./bootstrap.sh")):
            code = check_model.main(["model.xml", "docs", "archi"])
        self.assertEqual(code, 2)
        self.assertIn("viewpoints: run ./bootstrap.sh", err.getvalue())

    def test_wrong_arguments_print_usage(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(check_model.main(["model.xml"]), 2)


class RelationshipsCommandLine(unittest.TestCase):
    def run_main(self, argv: list[str]) -> tuple[int, str]:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as stop:
            check_relationships.main(argv)
        return stop.exception.code, err.getvalue()

    def test_unreadable_model_fails_naming_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, err = self.run_main([str(Path(tmp) / "missing.xml"), tmp])
        self.assertEqual(code, 1)
        self.assertIn("missing.xml", err)

    def test_not_well_formed_model_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "model.xml").write_text("<model", encoding="utf-8")
            code, err = self.run_main([str(Path(tmp) / "model.xml"), tmp])
        self.assertEqual(code, 1)
        self.assertIn("not well-formed XML", err)

    def test_wrong_arguments_print_usage(self):
        code, err = self.run_main(["model.xml"])
        self.assertEqual(code, 2)
        self.assertIn("check_relationships.py <model.xml> <archi-home>", err)


if __name__ == "__main__":
    unittest.main()
