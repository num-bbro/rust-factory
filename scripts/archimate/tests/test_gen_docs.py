"""Tests of the Markdown unwrap/wrap (mdwrap.py) and the ADR page generator (gen_docs.py), ADR 0009."""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import exchange  # noqa: E402
import gen_docs  # noqa: E402
import mdwrap  # noqa: E402

TRICKY = """\
## Heading that is longer than the width and must never be wrapped, whatever happens to the rest
A paragraph that is spread over
several lines, with `inline code that has spaces` and a [link](https://example.com/a/very/long/path)
that goes on.

- A list item that continues
  on a second line.
  - A nested item, which
    also continues.
    1. An ordered item inside
       it.
- Next item - with a dash
  - and a nested one.
1.  Ordered with two spaces
    after the marker.

  Indented paragraph inside
  a list item.

```rust
fn f() -> Result<T, E> { let a_very_long_line = "that is never wrapped by anything at all, not even at width 20"; }
  - not a list
```

| Table | with | cells that are long enough to be wrapped if anyone dared to wrap them |
|---|---|---|

> A block quote stays
> as it is.

A hard break\\
stays a break.
    Indented continuation of a paragraph.

    indented code after a blank line
Supercalifragilisticexpialidocious_is_a_word_longer_than_the_width_of_twenty."""


class Unwrap(unittest.TestCase):
    def test_paragraphs_and_list_items_become_one_line(self):
        text = mdwrap.unwrap(TRICKY)
        self.assertIn("A paragraph that is spread over several lines, with `inline code that has "
                      "spaces` and a [link](https://example.com/a/very/long/path) that goes on.",
                      text.split("\n"))
        self.assertIn("- A list item that continues on a second line.", text.split("\n"))
        self.assertIn("  - A nested item, which also continues.", text.split("\n"))
        self.assertIn("    1. An ordered item inside it.", text.split("\n"))
        self.assertIn("1.  Ordered with two spaces after the marker.", text.split("\n"))
        self.assertIn("  Indented paragraph inside a list item.", text.split("\n"))

    def test_code_tables_quotes_headings_and_hard_breaks_are_kept(self):
        lines = mdwrap.unwrap(TRICKY).split("\n")
        for kept in ("```rust", "  - not a list", "|---|---|---|", "> A block quote stays",
                     "> as it is.", "A hard break\\", "    indented code after a blank line"):
            self.assertIn(kept, lines)
        self.assertIn("stays a break. Indented continuation of a paragraph.", lines)

    def test_only_whitespace_between_lines_changes(self):
        self.assertEqual(mdwrap.unwrap(TRICKY).split(), TRICKY.split())

    def test_unwrapped_text_is_a_fixed_point(self):
        once = mdwrap.unwrap(TRICKY)
        self.assertEqual(mdwrap.unwrap(once), once)


class Wrap(unittest.TestCase):
    def test_round_trip_at_many_widths(self):
        doc = mdwrap.unwrap(TRICKY)
        for width in (20, 40, 72, 100):
            with self.subTest(width=width):
                self.assertEqual(mdwrap.unwrap(mdwrap.wrap(doc, width)), doc)

    def test_lines_fit_unless_a_word_cannot_be_split(self):
        wrapped = mdwrap.wrap(mdwrap.unwrap(TRICKY), 40)
        raw = set(TRICKY.split("\n"))
        long = [line for line in wrapped.split("\n") if len(line) > 40 and line not in raw]
        self.assertTrue(long)
        for line in long:
            self.assertEqual(len(line.split()), 1, line)

    def test_continuation_lines_use_the_content_indent(self):
        wrapped = mdwrap.wrap("- a\n  - b\n    1. An ordered item inside a nested list with words",
                              24)
        self.assertEqual(wrapped.split("\n")[2:], ["    1. An ordered item",
                                               "       inside a nested",
                                               "       list with words"])
        self.assertEqual(mdwrap.wrap("1.  two spaces after the marker", 16).split("\n"),
                         ["1.  two spaces", "    after the", "    marker"])

    def test_never_starts_a_line_with_a_block_marker(self):
        for text in ("aaaa - b", "aaaa + b", "aaaa * b", "aaaa 1. b", "aaaa 12) b", "aaaa # b",
                     "aaaa > b", "aaaa | b", "aaaa <div> b", "aaaa ``` b", "aaaa --- b",
                     "aaaa === b", "aaaa ~~~ b", "aaaa :--- b"):
            with self.subTest(text=text):
                self.assertEqual(mdwrap.wrap(text, 5).split("\n"),
                                 [" ".join(text.split()[:2]), "b"])

    def test_a_hard_break_ends_the_unit(self):
        text = "aaaa bbbb\\\ncccc dddd eeee"
        self.assertEqual(mdwrap.unwrap(text), text)
        self.assertEqual(mdwrap.wrap(text, 10), "aaaa bbbb\\\ncccc dddd\neeee")
        self.assertEqual(mdwrap.unwrap(mdwrap.wrap(text, 10)), text)

    def test_code_that_looks_like_a_list_is_never_wrapped(self):
        step = "- run: cargo test --workspace --all-features --locked -- --test-threads 1 " \
               "--nocapture --include-ignored now"
        indented = f"The workflow step:\n\n    {step}\n\nMore text."
        nested_fence = f"- a\n  - b\n\n    ```yaml\n    {step}\n\n    ```\n\nAfter."
        deep_fence = f"1. one\n   - two\n\n     ```sh\n     {step}\n     ```"
        for text in (indented, nested_fence, deep_fence):
            with self.subTest(text=text):
                self.assertEqual(mdwrap.unwrap(text), text)
                self.assertEqual(mdwrap.wrap(text, 40), text)

    def test_a_fence_closes_only_with_a_fence_at_least_as_long(self):
        text = "````\n```\n- a list-like code line that is long\n````\n- an item that is long"
        self.assertEqual(mdwrap.wrap(text, 20).split("\n"),
                         ["````", "```", "- a list-like code line that is long", "````",
                          "- an item that is", "  long"])

    def test_a_fence_closes_only_with_a_bare_fence_at_most_3_spaces_in(self):
        code = "- a list-like code line that is long"
        for closer in ("``` not a close", "    ```"):
            with self.subTest(closer=closer):
                text = f"```\n{closer}\n{code}\n```"
                self.assertEqual(mdwrap.wrap(text, 20), text)

    def test_a_lazy_line_keeps_its_list_items_open(self):
        text = "- a\n  - b\nlazy\n    - c is an item that is long"
        self.assertEqual(mdwrap.wrap(text, 20).split("\n")[3:],
                         ["    - c is an item", "      that is long"])

    def test_inline_code_with_three_backticks_starts_a_paragraph_not_a_fence(self):
        text = "```x``` starts a paragraph that is long"
        self.assertEqual(mdwrap.wrap(text, 20), "```x``` starts a\nparagraph that is\nlong")

    def test_tabs_in_the_indentation_are_refused_and_never_wrapped(self):
        long = "cargo test --workspace --all-features --locked -- --test-threads 1 --nocapture"
        for text in (f"Example:\n\n\t{long}\n\nMore.", f"- step\n\n\t\t- run: {long}",
                     f"Text:\n\n\t- run: {long}\n\tlet x = 1;"):
            with self.subTest(text=text):
                self.assertTrue(any("a tab in the indentation; indent with spaces, or use a "
                                    "fenced code block" in p for p in mdwrap.problems(text)))
                self.assertEqual(mdwrap.unwrap(text), text)
                self.assertEqual(mdwrap.wrap(text, 30), text)
        self.assertEqual(mdwrap.problems(f"```\n\t{long}\n```"), [])

    def test_a_fence_closed_left_of_its_list_item_is_refused(self):
        text = "1. a\n\n   ```\n   code\n ```\n\n   para"
        self.assertEqual(mdwrap.problems(text), [
            "line 5: this fence closes at indent 1, left of its list item's content (indent 3); "
            "close a fence at the indent it was opened"])
        self.assertEqual(mdwrap.problems("1. a\n\n   ```\n   code\n   ```"), [])

    def test_html_blocks_are_kept_up_to_their_end(self):
        text = "<pre>\n- a long preformatted line here\n\n- another one\n</pre>\n\nwords and more"
        self.assertEqual(mdwrap.wrap(text, 12).split("\n")[:6], text.split("\n")[:6])
        self.assertEqual(mdwrap.wrap(text, 12).split("\n")[6:], ["words and", "more"])
        comment = "<!--\nsome hidden words\n-->\nvisible words"
        self.assertEqual(mdwrap.wrap(comment, 8).split("\n"),
                         ["<!--", "some hidden words", "-->", "visible", "words"])

    def test_blocks_inside_nested_lists_and_pipeless_tables_are_one_line_already(self):
        for text in ("- a\n  - b\n    > a quote", "- a\n  - b\n    # A heading\n    text",
                     "a | b\n--- | ---\n1 | 2 with a long cell\n\nAfter the table."):
            with self.subTest(text=text):
                self.assertEqual(mdwrap.unwrap(text), text)
                self.assertEqual(mdwrap.wrap(text, 10).split("\n")[:3], text.split("\n")[:3])

    def test_never_breaks_after_a_backslash_or_at_a_double_space(self):
        self.assertEqual(mdwrap.wrap("aaaa\\ bbbb", 6), "aaaa\\ bbbb")
        self.assertEqual(mdwrap.wrap("aaaa  bbbb", 6), "aaaa  bbbb")

    def test_long_words_stay_whole(self):
        url = "https://example.com/" + "x" * 120
        self.assertEqual(mdwrap.wrap(f"see {url} now", 100).split("\n"), ["see", url, "now"])

    def test_raw_lines_are_never_wrapped(self):
        for line in ("## " + "word " * 30, "| " + "cell | " * 30, "> " + "quote " * 30):
            self.assertEqual(mdwrap.wrap(line.strip(), 40), line.strip())

    def test_is_deterministic(self):
        doc = mdwrap.unwrap(TRICKY)
        self.assertEqual(mdwrap.wrap(doc), mdwrap.wrap(doc))


def adr_model(doc1: str = "## Context\\nOne line per paragraph.", extra: str = "") -> str:
    def adr(num: str, title: str, status: str, doc: str) -> str:
        props = "".join(
            f'<property propertyDefinitionRef="p-{k.lower()}"><value xml:lang="en">{v}</value>'
            "</property>"
            for k, v in (("Status", status), ("Date", "2026-11-16"), ("Issue", "#1"),
                         ("Deciders", "human"), ("File", f"docs/adr/{num}-{title.lower()}.md")))
        return (f'<element identifier="id-mot-adr-{num}" xsi:type="Constraint">'
                f'<name xml:lang="en">ADR {num}: {title}</name>'
                f'<documentation xml:lang="en">{doc}</documentation>'
                f"<properties>{props}</properties></element>")
    defs = "".join(f'<propertyDefinition identifier="p-{k}" type="string"><name xml:lang="en">'
                   f"{k.capitalize()}</name></propertyDefinition>"
                   for k in ("status", "date", "issue", "deciders", "file"))
    return (f'<model xmlns="{exchange.NS}" xmlns:xsi="{exchange.XSI}" identifier="id-model-t">'
            '<name xml:lang="en">t</name><elements>'
            + adr("0001", "First", "Superseded by 0002", doc1.replace("\\n", "\n"))
            + adr("0002", "Second", "Accepted", "Text.")
            + '<element identifier="id-app-comp-b" xsi:type="ApplicationComponent">'
              '<name xml:lang="en">b</name></element>'
              '<element identifier="id-app-comp-a" xsi:type="ApplicationComponent">'
              '<name xml:lang="en">a</name></element>'
              '<element identifier="id-mot-req-r" xsi:type="Requirement">'
              '<name xml:lang="en">r</name></element>'
            + extra + "</elements><relationships>"
            '<relationship identifier="id-rel-001" xsi:type="Realization" source="id-app-comp-b" '
            'target="id-mot-adr-0001"/>'
            '<relationship identifier="id-rel-002" xsi:type="Influence" source="id-mot-req-r" '
            'target="id-mot-adr-0001"/>'
            '<relationship identifier="id-rel-003" xsi:type="Realization" source="id-app-comp-a" '
            'target="id-mot-adr-0001"/>'
            '<relationship identifier="id-rel-004" xsi:type="Serving" source="id-app-comp-a" '
            'target="id-app-comp-b"/>'
            '<relationship identifier="id-rel-005" xsi:type="Association" source="id-mot-adr-0002" '
            'target="id-mot-adr-0001" isDirected="true"><name xml:lang="en">supersedes</name>'
            f"</relationship></relationships><propertyDefinitions>{defs}</propertyDefinitions>"
            "</model>")


def rendered(xml: str | None = None) -> tuple[dict[str, str], list[str]]:
    return gen_docs.render(exchange.read((xml or adr_model()).encode()))


class Pages(unittest.TestCase):
    def test_header_list_comes_from_the_relationships(self):
        page = rendered()[0]["docs/adr/0001-first.md"]
        self.assertEqual(page.split("\n")[1:10], [
            "# 0001. First", "",
            "- Status: Superseded by 0002", "- Date: 2026-11-16", "- Issue: #1",
            "- Deciders: human",
            "- ArchiMate elements: `id-app-comp-a`, `id-app-comp-b`, `id-mot-req-r`",
            "- Superseded by: ADR 0002", ""])
        self.assertTrue(page.endswith("## Context\nOne line per paragraph.\n"))
        second = rendered()[0]["docs/adr/0002-second.md"]
        self.assertIn("- Supersedes: ADR 0001\n", second)
        self.assertNotIn("ArchiMate elements", second)

    def test_every_page_starts_with_the_generated_note(self):
        for rel, content in rendered()[0].items():
            self.assertTrue(content.startswith("<!-- Generated from docs/architecture/model.xml"),
                            rel)

    def test_index_lists_every_adr_and_links_the_superseding_one(self):
        index = rendered()[0]["docs/adr/README.md"]
        self.assertIn("| [0001](0001-first.md) | First | Superseded by [0002](0002-second.md) |",
                      index)
        self.assertIn("| [0002](0002-second.md) | Second | Accepted |", index)

    def test_long_paragraphs_are_wrapped_and_read_back(self):
        doc = "Word " * 60 + "end."
        pages, problems = rendered(adr_model(doc.strip()))
        self.assertEqual(problems, [])
        page = pages["docs/adr/0001-first.md"]
        self.assertTrue(all(len(line) <= 100 for line in page.split("\n")[1:]))
        self.assertIn(doc.strip(), mdwrap.unwrap(page))

    def test_is_deterministic(self):
        self.assertEqual(rendered(), rendered())

    def test_model_problems_are_named(self):
        _, problems = rendered(adr_model("Spread over\\ntwo lines."))
        self.assertTrue(any("option A" in p and "id-mot-adr-0001" in p for p in problems), problems)
        bad = adr_model().replace("ADR 0002: Second", "Second").replace(
            '<property propertyDefinitionRef="p-date"><value xml:lang="en">2026-11-16</value>'
            "</property>", "", 1)
        _, problems = rendered(bad)
        self.assertTrue(any("property Date is missing" in p for p in problems), problems)
        self.assertTrue(any("name must be 'ADR 0002: <title>'" in p for p in problems), problems)
        _, problems = rendered(adr_model(extra='<element identifier="id-mot-adr-x" '
                                               'xsi:type="Constraint"><name>x</name></element>'))
        self.assertTrue(any("id-mot-adr-NNNN" in p for p in problems), problems)


class ModelProblems(unittest.TestCase):
    def problems(self, old: str, new: str) -> list[str]:
        xml = adr_model()
        self.assertIn(old, xml)
        return rendered(xml.replace(old, new, 1))[1]

    def test_the_valid_model_has_none(self):
        self.assertEqual(rendered()[1], [])

    def test_file_must_be_the_numbered_page(self):
        for bad in ("docs/adr/0001-First.md", "docs/adr/0002-first.md", "docs/0001-first.md",
                    "docs/adr/0001-first.txt"):
            with self.subTest(file=bad):
                problems = self.problems(">docs/adr/0001-first.md<", f">{bad}<")
                self.assertIn(f"File must be docs/adr/0001-<slug>.md, is '{bad}'",
                              "\n".join(problems))

    def test_an_adr_must_be_a_constraint(self):
        problems = self.problems('id-mot-adr-0002" xsi:type="Constraint"',
                                 'id-mot-adr-0002" xsi:type="Requirement"')
        self.assertTrue(any("must be a Constraint, is a Requirement" in p for p in problems),
                        problems)

    def test_a_property_given_twice_is_named(self):
        status = ('<property propertyDefinitionRef="p-status"><value xml:lang="en">Accepted'
                  "</value></property>")
        problems = self.problems(status, status + status)
        self.assertTrue(any("property Status is given more than once" in p for p in problems),
                        problems)

    def test_unsupported_markdown_is_named_with_its_element(self):
        problems = rendered(adr_model("Example:\\n\\n\tcode"))[1]
        self.assertEqual(problems, ["ADR element 'id-mot-adr-0001': documentation line 3: a tab "
                                    "in the indentation; indent with spaces, or use a fenced code "
                                    "block"])

    def test_status_and_supersedes_link_must_agree(self):
        problems = self.problems(">Superseded by 0002<", ">Accepted<")
        self.assertTrue(any("'id-mot-adr-0001': a `supersedes` Association makes its Status "
                            "'Superseded by 0002'" in p for p in problems), problems)
        problems = self.problems(">Accepted<", ">Superseded by 0001<")
        self.assertTrue(any("'id-mot-adr-0002': Status = 'Superseded by 0001' needs a "
                            "`supersedes` Association to it from id-mot-adr-0001" in p
                            for p in problems), problems)
        problems = self.problems(">Accepted<", ">Superseded by 0001 (partly)<")
        self.assertTrue(any("(Status must be 'Superseded by NNNN')" in p for p in problems),
                        problems)


class Check(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "docs" / "architecture").mkdir(parents=True)
        (self.root / gen_docs.MODEL).write_text(adr_model(), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *args: str) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = gen_docs.main([*args, str(self.root)])
        return code, out.getvalue() + err.getvalue()

    def test_write_then_check_passes(self):
        self.assertEqual(self.run_main()[0], 0)
        code, out = self.run_main("--check")
        self.assertEqual(code, 0)
        self.assertIn("3 generated pages are current", out)
        self.assertNotIn(str(self.root), (self.root / "docs/adr/0001-first.md").read_text())

    def test_missing_page_fails(self):
        code, out = self.run_main("--check")
        self.assertEqual(code, 1)
        self.assertIn("docs/adr/0001-first.md is missing", out)

    def test_hand_edited_page_fails(self):
        self.run_main()
        page = self.root / "docs/adr/0002-second.md"
        page.write_text(page.read_text() + "More.\n", encoding="utf-8")
        code, out = self.run_main("--check")
        self.assertEqual(code, 1)
        self.assertIn("docs/adr/0002-second.md is stale or was edited by hand", out)

    def test_orphan_page_fails_but_the_template_is_allowed(self):
        self.run_main()
        (self.root / "docs/adr/template.md").write_text("guide\n", encoding="utf-8")
        (self.root / "docs/adr/0003-gone.md").write_text("old\n", encoding="utf-8")
        code, out = self.run_main("--check")
        self.assertEqual(code, 1)
        self.assertIn("docs/adr/0003-gone.md is an orphan", out)
        self.assertNotIn("template.md is", out)
        self.assertEqual(self.run_main()[0], 1)          # writing never deletes it
        self.assertTrue((self.root / "docs/adr/0003-gone.md").exists())

    def test_model_problem_fails_and_writes_nothing(self):
        (self.root / gen_docs.MODEL).write_text(adr_model("two\\nlines"), encoding="utf-8")
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("option A", out)
        self.assertFalse((self.root / "docs/adr").exists())

    def test_unreadable_model_and_bad_arguments(self):
        (self.root / gen_docs.MODEL).write_text("<model", encoding="utf-8")
        self.assertEqual(self.run_main("--check")[0], 1)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(gen_docs.main(["--nope"]), 2)


class RealModel(unittest.TestCase):
    def test_the_repository_pages_are_current(self):
        root = HERE.parents[2]
        pages, problems = gen_docs.render(exchange.read((root / gen_docs.MODEL).read_bytes()))
        self.assertEqual(problems, [])
        self.assertEqual(gen_docs.compare(pages, root), [])


if __name__ == "__main__":
    unittest.main()
