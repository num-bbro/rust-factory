"""Tests of the canonical form (exchange.py) and its command line (model_fmt.py), ADR 0009.

Fixtures: fixtures/bare.xml is formatter input that breaks every rule it can (out of order, no
xml:lang, CDATA, numbered and unused property definitions, a bare view, a manual view);
fixtures/canonical.xml is the expected output, reviewed by hand. Regenerate it only on purpose:
  cp fixtures/bare.xml fixtures/canonical.xml && python3 -I ../model_fmt.py fixtures/canonical.xml
"""

from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import exchange  # noqa: E402
import model_fmt  # noqa: E402
from exchange import NS, XSI  # noqa: E402

BARE = (HERE / "fixtures" / "bare.xml").read_bytes()
CANONICAL = (HERE / "fixtures" / "canonical.xml").read_text(encoding="utf-8")
A = '<element identifier="id-a" xsi:type="Goal"><name>A</name></element>'
B = '<element identifier="id-b" xsi:type="Goal"><name>B</name></element>'


def model(elements: str = A, rest: str = "", head: str = "<name>M</name>") -> bytes:
    """A minimal exchange file; `rest` follows the elements section."""
    return (f'<?xml version="1.0" encoding="UTF-8"?><model xmlns="{NS}" xmlns:xsi="{XSI}" '
            f'identifier="id-m">{head}<elements>{elements}</elements>{rest}</model>').encode()


def fmt(data: bytes) -> str:
    return exchange.canonical(data)[0]


def problems(data: bytes) -> str:
    try:
        exchange.canonical(data)
    except exchange.FormatError as err:
        return "\n".join(err.problems)
    raise AssertionError("expected a FormatError")


class WholeFile(unittest.TestCase):
    def test_bare_view_is_formatted_to_the_reviewed_output(self):
        self.assertEqual(fmt(BARE), CANONICAL)

    def test_formatted_file_is_unchanged(self):
        self.assertEqual(fmt(CANONICAL.encode()), CANONICAL)

    def test_input_order_does_not_change_the_output(self):
        root = ET.fromstring(BARE)
        # Every sorted list reversed, and the bare view's nodes too (a manual view keeps its order).
        for path in ("elements", "relationships", "views/diagrams",
                     "views/diagrams/view[@identifier='id-view-main']"):
            for holder in root.iterfind("/".join(f"{{{NS}}}{p}" for p in path.split("/"))):
                holder[:] = list(reversed(holder))
        self.assertEqual(fmt(ET.tostring(root)), CANONICAL)

    def test_output_is_the_same_in_every_process(self):
        # Separate processes get different string-hash seeds (python3 -I ignores PYTHONHASHSEED),
        # so any dependence on set or dict order would show here.
        with tempfile.TemporaryDirectory() as tmp:
            outputs = set()
            for i in range(3):
                path = Path(tmp) / f"m{i}.xml"
                path.write_bytes(BARE)
                subprocess.run([sys.executable, "-I", str(HERE.parent / "model_fmt.py"), str(path)],
                               check=True, capture_output=True)
                outputs.add(path.read_text(encoding="utf-8"))
        self.assertEqual(outputs, {CANONICAL})

    def test_unused_property_definition_is_dropped_with_a_note(self):
        notes = exchange.canonical(BARE)[1]
        self.assertEqual(notes, ["dropped unused property definition 'Never Used' (propid-3)"])
        self.assertNotIn("Never Used", CANONICAL)


class CanonicalRules(unittest.TestCase):
    def test_every_name_label_documentation_and_value_is_english(self):
        out = ET.fromstring(fmt(BARE).encode())
        auto = [v for v in out.iter(f"{{{NS}}}view") if v.get("identifier") == "id-view-main"][0]
        texts = [e for e in [*out.iterfind(f"{{{NS}}}elements//*"), *auto.iter(),
                             *out.iterfind(f"{{{NS}}}propertyDefinitions//*")]
                 if e.tag.split("}")[1] in {"name", "label", "documentation", "value"}]
        self.assertGreater(len(texts), 10)
        for e in texts:
            self.assertEqual(e.get("{http://www.w3.org/XML/1998/namespace}lang"), "en", e.text)

    def test_empty_documentation_is_omitted(self):
        out = fmt(model('<element identifier="id-a" xsi:type="Goal"><name>A</name>'
                        "<documentation/></element>"))
        self.assertNotIn("documentation", out)

    def test_documentation_loses_its_trailing_newline(self):
        out = fmt(model('<element identifier="id-a" xsi:type="Goal"><name>A</name>'
                        "<documentation>one\ntwo\n\n</documentation></element>"))
        self.assertIn('<documentation xml:lang="en">one\ntwo</documentation>', out)

    def test_cdata_is_written_escaped(self):
        out = fmt(model('<element identifier="id-a" xsi:type="Goal"><name><![CDATA[a<b & c]]>'
                        "</name></element>"))
        self.assertIn('<name xml:lang="en">a&lt;b &amp; c</name>', out)
        self.assertNotIn("CDATA", out)

    def test_comments_are_rejected_inside_and_outside_the_model(self):
        for data in (model(A + "<!-- note -->"), model().replace(b"?><model", b"?><!-- note --><model")):
            self.assertIn("XML comment ('note') is not allowed", problems(data))

    def test_schema_location_is_always_written(self):
        self.assertIn(f'xsi:schemaLocation="{exchange.SCHEMA_LOCATION}"', fmt(model()))

    def test_property_definitions_get_ids_from_their_names(self):
        defs = ('<propertyDefinitions><propertyDefinition identifier="propid-9" type="string">'
                "<name>Code path</name></propertyDefinition></propertyDefinitions>")
        el = ('<element identifier="id-a" xsi:type="Goal"><name>A</name><properties>'
              '<property propertyDefinitionRef="propid-9"><value>x</value></property>'
              "</properties></element>")
        out = fmt(model(el, defs))
        self.assertIn('<property propertyDefinitionRef="propid-code-path">', out)
        self.assertIn('<propertyDefinition identifier="propid-code-path" type="string">', out)

    def test_property_definitions_whose_names_give_the_same_id_are_rejected(self):
        defs = ('<propertyDefinitions><propertyDefinition identifier="p1" type="string"><name>A b'
                '</name></propertyDefinition><propertyDefinition identifier="p2" type="string">'
                "<name>a-B</name></propertyDefinition></propertyDefinitions>")
        self.assertIn("both give the identifier propid-a-b", problems(model(A, defs)))

    def test_repeated_properties_keep_their_order(self):
        defs = ('<propertyDefinitions><propertyDefinition identifier="p" type="string">'
                "<name>View</name></propertyDefinition></propertyDefinitions>")
        props = "".join(f'<property propertyDefinitionRef="p"><value>{v}</value></property>'
                        for v in ("z", "a", "m"))
        out = fmt(model(f'<element identifier="id-a" xsi:type="Goal"><name>A</name>'
                        f"<properties>{props}</properties></element>", defs))
        self.assertLess(out.index(">z<"), out.index(">a<"))
        self.assertLess(out.index(">a<"), out.index(">m<"))

    def test_access_always_states_its_access_type(self):
        rels = ('<relationships><relationship identifier="r1" xsi:type="Access" source="id-a" '
                'target="id-b"/><relationship identifier="r2" xsi:type="Access" source="id-a" '
                'target="id-b" accessType="Read"/></relationships>')
        out = fmt(model(A + B, rels))
        self.assertIn('identifier="r1" xsi:type="Access" source="id-a" target="id-b" '
                      'accessType="Access"/>', out)
        self.assertIn('accessType="Read"', out)

    def test_attributes_are_written_in_one_order(self):
        out = fmt(model('<element xsi:type="Goal" identifier="id-a"><name>A</name></element>'))
        self.assertIn('<element identifier="id-a" xsi:type="Goal">', out)

    def test_sections_are_written_in_schema_order(self):
        self.assertLess(BARE.index(b"<propertyDefinitions>"), BARE.index(b"<elements>"))
        out = fmt(BARE)
        tags = [f"<{t}>" for t in ("elements", "relationships", "propertyDefinitions", "views")]
        self.assertEqual([out.index(t) for t in tags], sorted(out.index(t) for t in tags))

    def test_children_are_written_in_schema_order(self):
        out = fmt(model('<element identifier="id-a" xsi:type="Goal"><documentation>d'
                        "</documentation><name>A</name></element>"))
        self.assertLess(out.index("<name"), out.index("<documentation"))

    def test_empty_properties_are_omitted(self):
        out = fmt(model('<element identifier="id-a" xsi:type="Goal"><name>A</name><properties/>'
                        "</element>"))
        self.assertNotIn("properties", out)

    def test_two_documentations_in_one_language_are_rejected(self):
        data = model('<element identifier="id-a" xsi:type="Goal"><name>A</name>'
                     "<documentation>1</documentation><documentation>2</documentation></element>")
        self.assertIn("more than one <documentation>", problems(data))

    def test_other_languages_are_rejected(self):
        data = model('<element identifier="id-a" xsi:type="Goal"><name xml:lang="th">ก</name>'
                     "</element>")
        self.assertIn('xml:lang="en" only', problems(data))

    def test_element_without_name_is_rejected(self):
        self.assertIn("element 'id-a': has no <name>",
                      problems(model('<element identifier="id-a" xsi:type="Goal"/>')))

    def test_unsupported_sections_are_rejected_not_dropped(self):
        org = '<organizations><item identifierRef="id-a"/></organizations>'
        self.assertIn("<organizations> is not supported", problems(model(A, org)))
        meta = "<metadata><schema>x</schema></metadata>"
        self.assertIn("<metadata> is not supported", problems(model(A, "", "<name>M</name>" + meta)))

    def test_unknown_attributes_and_foreign_elements_are_rejected(self):
        self.assertIn("attribute colour is not supported",
                      problems(model('<element identifier="id-a" xsi:type="Goal" colour="red">'
                                     "<name>A</name></element>")))
        self.assertIn("<{urn:x}extra> is not supported",
                      problems(model('<element identifier="id-a" xsi:type="Goal"><name>A</name>'
                                     '<extra xmlns="urn:x"/></element>')))

    def test_not_well_formed_and_doctype_are_rejected(self):
        self.assertIn("not well-formed", problems(b"<model"))
        self.assertIn("DOCTYPE", problems(model().replace(b"?><model", b"?><!DOCTYPE model []><model")))


class Views(unittest.TestCase):
    def view(self, nodes: str, props: str = "") -> bytes:
        return model(A + B, '<views><diagrams><view identifier="id-view-v" xsi:type="Diagram">'
                     f"<name>V</name>{props}{nodes}</view></diagrams></views>")

    def test_bare_and_formatted_views_give_the_same_output(self):
        bare = fmt(self.view('<node xsi:type="Element" elementRef="id-b"/>'
                             '<node xsi:type="Element" elementRef="id-a"/>'))
        self.assertIn('identifier="id-view-v-n-id-a"', bare)
        self.assertEqual(fmt(bare.encode()), bare)

    def test_manual_view_is_left_as_it_is(self):
        def view_of(data: bytes) -> list[tuple]:
            root = ET.fromstring(data)
            v = [v for v in root.iter(f"{{{NS}}}view") if v.get("identifier") == "id-view-hand"][0]
            return [(e.tag, {k: x for k, x in e.attrib.items() if k != "propertyDefinitionRef"},
                     (e.text or "").strip()) for e in v.iter()]

        self.assertEqual(view_of(CANONICAL.encode()), view_of(BARE))
        self.assertIn('<property propertyDefinitionRef="propid-layout">', CANONICAL)

    def test_hand_made_nodes_need_a_manual_view(self):
        label = '<node identifier="l" xsi:type="Label" x="1" y="1" w="9" h="9"><label>x</label></node>'
        self.assertIn("set the view property Layout = manual", problems(self.view(label)))

    def test_members_must_be_elements_the_automatic_layout_can_place(self):
        missing = self.view('<node xsi:type="Element" elementRef="id-zz"/>')
        self.assertIn("'id-zz' is not an element of the model", problems(missing))
        junction = model(A + '<element identifier="id-j" xsi:type="AndJunction"><name>j</name>'
                         '</element>', '<views><diagrams><view identifier="id-view-v" '
                         'xsi:type="Diagram"><name>V</name><node xsi:type="Element" '
                         'elementRef="id-j"/></view></diagrams></views>')
        self.assertIn("'id-j' is a AndJunction", problems(junction))


class CommandLine(unittest.TestCase):
    def run_main(self, *args: str) -> tuple[int, str]:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = model_fmt.main(list(args))
        return code, err.getvalue()

    def test_check_fails_on_a_file_that_is_not_canonical_and_names_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.xml"
            path.write_bytes(BARE)
            code, err = self.run_main("--check", str(path))
            self.assertEqual(code, 1)
            self.assertIn(f"{path}: not in canonical form", err)
            self.assertEqual(path.read_bytes(), BARE)          # --check never writes

    def test_check_passes_on_a_canonical_file(self):
        self.assertEqual(self.run_main("--check", str(HERE / "fixtures" / "canonical.xml"))[0], 0)

    def test_format_rewrites_the_file_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.xml"
            path.write_bytes(BARE)
            self.assertEqual(self.run_main(str(path))[0], 0)
            self.assertEqual(path.read_text(encoding="utf-8"), CANONICAL)

    def test_invalid_input_lists_problems_and_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.xml"
            path.write_bytes(model('<element identifier="id-a" xsi:type="Goal"/>'))
            code, err = self.run_main(str(path))
            self.assertEqual(code, 2)
            self.assertIn(f"{path}: element 'id-a': has no <name>", err)

    def test_missing_default_file_is_a_message_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(model_fmt, "DEFAULT", Path(tmp) / "model.xml"):
                code, err = self.run_main("--check")
        self.assertEqual(code, 2)
        self.assertIn("no such file (the exchange model is created by step 2 of #41", err)


if __name__ == "__main__":
    unittest.main()
