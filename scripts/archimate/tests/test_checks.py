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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import check_model  # noqa: E402
import check_relationships  # noqa: E402
import exchange  # noqa: E402

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
                       "Target": "id-app-data-booking"}, MODEL.relationships)
        self.assertEqual(sorted(MODEL.views["id-view-main"]), sorted(MODEL.elements))
        self.assertEqual(MODEL.views["id-view-hand"], ["id-app-comp-web", "id-app-comp-api"])

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

    def test_view_property_must_name_a_view(self):
        model = edited("<value xml:lang=\"en\">crates/web</value>", "<value xml:lang=\"en\">x</value>")
        model.properties += [("id-app-comp-web", "View", "id-view-main"),
                             ("id-app-comp-web", "View", "id-view-gone")]
        self.assertEqual(check_model.views(model), [
            "'id-app-comp-web': property View = 'id-view-gone' names no view of the model"])


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


class CommandLine(unittest.TestCase):
    def run_main(self, text: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "model.xml").write_bytes(CANONICAL)
            (Path(tmp) / "doc.md").write_text(text, encoding="utf-8")
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = check_model.main([str(Path(tmp) / "model.xml"), tmp])
        return code, out.getvalue(), err.getvalue()

    def test_all_checks_pass_with_one_line_each(self):
        code, out, _ = self.run_main("`id-app-comp-web`")
        self.assertEqual(code, 0)
        self.assertEqual(len(out.splitlines()), 3)

    def test_a_problem_fails_and_is_listed(self):
        code, _, err = self.run_main("`id-app-comp-gone`")
        self.assertEqual(code, 1)
        self.assertIn("id-app-comp-gone", err)


if __name__ == "__main__":
    unittest.main()
