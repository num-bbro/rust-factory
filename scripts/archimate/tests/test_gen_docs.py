"""Tests of the Markdown unwrap/wrap (mdwrap.py) and the ADR and TOGAF page generator
(gen_docs.py), ADR 0009."""

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
        self.assertIn("4 generated pages are current", out)
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


FENCED = "```\\nSee `id-app-comp-a` here.\\n```"
NARRATIVE = ("## Content\\nSee `id-mot-adr-0001`, `id-view-one`, `id-view-three`, `id-app-comp-a`, "
             "`id-app-comp-c`, `id-mot-req-r`, `id-rel-001` and `id-app-comp-zz`.\\n" + FENCED)


def togaf_model(first_views: tuple[str, ...] = ("id-view-two", "id-view-one"),
                narrative: str = NARRATIVE, extra: str = "", rels: str = "",
                first_props: tuple[tuple[str, str], ...] = ()) -> str:
    """adr_model plus three views and three documents: the first shows `first_views` (and has
    `first_props` after its Phase), the second the third view, the third none."""
    def doc(slug: str, title: str, file: str, phase: str, views: tuple[str, ...], text: str,
            more: tuple[tuple[str, str], ...] = ()) -> str:
        props = [("file", file), ("phase", phase), *more] + [("view", v) for v in views]
        return (f'<element identifier="id-impl-del-{slug}" xsi:type="Deliverable">'
                f'<name xml:lang="en">{title}</name>'
                f'<documentation xml:lang="en">{text.replace(chr(92) + "n", chr(10))}'
                "</documentation><properties>"
                + "".join(f'<property propertyDefinitionRef="p-{k}"><value xml:lang="en">{v}'
                          "</value></property>" for k, v in props)
                + "</properties></element>")

    def view(vid: str, name: str, members: tuple[str, ...], text: str = "") -> str:
        documentation = f'<documentation xml:lang="en">{text}</documentation>' if text else ""
        return (f'<view identifier="{vid}" xsi:type="Diagram"><name xml:lang="en">{name}</name>'
                f"{documentation}"
                + "".join(f'<node identifier="n-{vid}-{m}" xsi:type="Element" elementRef="{m}"/>'
                          for m in members) + "</view>")

    elements = (
        '<element identifier="id-app-comp-c" xsi:type="ApplicationComponent">'
        '<name xml:lang="en">c | see</name><properties>'
        '<property propertyDefinitionRef="p-issue"><value xml:lang="en">#7</value></property>'
        '<property propertyDefinitionRef="p-crate"><value xml:lang="en">crates/c</value></property>'
        '<property propertyDefinitionRef="p-code"><value xml:lang="en">src/c.rs</value></property>'
        "</properties></element>"
        + doc("first", "A. First", "docs/togaf/A-first.md", "A", first_views, narrative,
              first_props)
        + doc("second", "B. Second", "docs/togaf/B-second.md", "B", ("id-view-three",),
              "Text with `id-app-comp-b` and `id-app-comp-a`.")
        + doc("third", "C. Third", "docs/togaf/C-third.md", "C", (), "Only `id-app-comp-b`.")
        + extra)
    views = ("<views><diagrams>"
             + view("id-view-one", "One", ("id-app-comp-b", "id-app-comp-a"))
             + view("id-view-two", "Two", ("id-mot-req-r", "id-app-comp-b"),
                    "Shows `id-app-comp-c`.")
             + view("id-view-three", "Three", ("id-app-comp-c", "id-app-comp-a"))
             + "</diagrams></views>")
    defs = "".join(f'<propertyDefinition identifier="p-{k}" type="string"><name xml:lang="en">'
                   f"{k.capitalize()}</name></propertyDefinition>"
                   for k in ("phase", "view", "crate", "code", "viewpoints", "artifacts"))
    return (adr_model(extra=elements)
            .replace("</relationships>", rels + "</relationships>")
            .replace("</propertyDefinitions>", defs + "</propertyDefinitions>")
            .replace("</model>", views + "</model>"))


def togaf(xml: str | None = None) -> tuple[dict[str, str], list[str]]:
    return rendered(xml or togaf_model())


def section(page: str, view: str) -> str:
    """One view section of a page, up to the next section."""
    start = page.index(f'## <a id="{view}"></a>')
    end = page.find("\n## ", start + 1)
    return page[start:end if end > 0 else None]


class TogafPages(unittest.TestCase):
    def test_the_valid_model_has_no_problems_and_every_document_a_page(self):
        pages, problems = togaf()
        self.assertEqual(problems, [])
        self.assertTrue({"docs/togaf/A-first.md", "docs/togaf/B-second.md", "docs/togaf/C-third.md",
                         "docs/togaf/README.md"} <= set(pages))
        for rel in ("docs/togaf/A-first.md", "docs/togaf/README.md"):
            first = pages[rel].split("\n")[0]
            self.assertTrue(first.startswith("<!-- Generated from docs/architecture/model.xml ("),
                            rel)
            self.assertTrue(first.endswith("see docs/togaf/template.md. -->"), rel)

    def test_page_is_title_narrative_then_view_sections_in_view_order(self):
        page = togaf()[0]["docs/togaf/A-first.md"]
        self.assertEqual(page.split("\n")[1:4], ["# A. First", "", "## Content"])
        self.assertLess(page.index("```"), page.index('## <a id="id-view-two"></a>Two'))
        self.assertLess(page.index('## <a id="id-view-two"></a>Two'),
                        page.index('## <a id="id-view-one"></a>One'))
        other = togaf(togaf_model(first_views=("id-view-one", "id-view-two")))[0]
        self.assertLess(other["docs/togaf/A-first.md"].index('<a id="id-view-one">'),
                        other["docs/togaf/A-first.md"].index('<a id="id-view-two">'))
        self.assertNotIn("## <a id=", togaf()[0]["docs/togaf/C-third.md"])

    def test_view_section_has_documentation_image_and_catalog(self):
        two = section(togaf()[0]["docs/togaf/A-first.md"], "id-view-two").split("\n")
        self.assertEqual(two[:6], [
            '## <a id="id-view-two"></a>Two', "",
            "Shows [`id-app-comp-c`](B-second.md#id-app-comp-c).", "",
            "![Two](../architecture/views/id-view-two.png)", ""])
        one = section(togaf()[0]["docs/togaf/A-first.md"], "id-view-one").split("\n")
        self.assertEqual(one[2], "![One](../architecture/views/id-view-one.png)")

    def test_catalog_columns_rows_sorted_and_first_row_anchored(self):
        page = togaf()[0]["docs/togaf/A-first.md"]
        two = section(page, "id-view-two").split("\n")
        self.assertEqual(two[6:10], [
            "| ID | Name | Type | Decisions | Issues | Crate / code | Other documents |",
            "|---|---|---|---|---|---|---|",
            '| <a id="id-app-comp-b"></a>`id-app-comp-b` | b | ApplicationComponent | '
            "[ADR 0001](../adr/0001-first.md) |  |  |  |",
            '| <a id="id-mot-req-r"></a>`id-mot-req-r` | r | Requirement | '
            "[ADR 0001](../adr/0001-first.md) |  |  |  |"])
        one = section(page, "id-view-one").split("\n")
        self.assertEqual(one[4:], [
            "| ID | Name | Type | Decisions | Issues | Crate / code | Other documents |",
            "|---|---|---|---|---|---|---|",
            '| <a id="id-app-comp-a"></a>`id-app-comp-a` | a | ApplicationComponent | '
            "[ADR 0001](../adr/0001-first.md) |  |  | [B. Second](B-second.md#id-app-comp-a) |",
            "| `id-app-comp-b` | b | ApplicationComponent | [ADR 0001](../adr/0001-first.md) |  |"
            "  |  |", ""])
        three = section(togaf()[0]["docs/togaf/B-second.md"], "id-view-three")
        self.assertIn('| <a id="id-app-comp-c"></a>`id-app-comp-c` | c \\| see | '
                      "ApplicationComponent |  | #7 | `crates/c`, `src/c.rs` |  |", three)

    def test_release_column_only_when_the_model_has_plateaus(self):
        self.assertNotIn("Release", togaf()[0]["docs/togaf/A-first.md"])
        plateau = ('<element identifier="id-impl-plat-v1-0-0" xsi:type="Plateau">'
                   '<name xml:lang="en">v1.0.0</name></element>'
                   '<element identifier="id-impl-plat-v0-9-0" xsi:type="Plateau">'
                   '<name xml:lang="en">v0.9.0</name></element>')
        rels = ('<relationship identifier="id-rel-901" xsi:type="Aggregation" '
                'source="id-impl-plat-v1-0-0" target="id-app-comp-a"/>'
                '<relationship identifier="id-rel-902" xsi:type="Association" '
                'source="id-impl-plat-v0-9-0" target="id-app-comp-a"/>')
        pages, problems = togaf(togaf_model(extra=plateau, rels=rels))
        self.assertEqual(problems, [])
        one = section(pages["docs/togaf/A-first.md"], "id-view-one").split("\n")
        self.assertEqual(one[4], "| ID | Name | Type | Decisions | Issues | Crate / code | Release "
                                 "| Other documents |")
        self.assertTrue(one[6].endswith("|  |  | v0.9.0, v1.0.0 | "
                                        "[B. Second](B-second.md#id-app-comp-a) |"), one[6])
        self.assertTrue(one[7].endswith("|  |  |  |  |"), one[7])

    def test_identifiers_link_to_each_kind_of_target(self):
        page = togaf()[0]["docs/togaf/A-first.md"]
        self.assertIn("See [`id-mot-adr-0001`](../adr/0001-first.md), "
                      "[`id-view-one`](#id-view-one), "
                      "[`id-view-three`](B-second.md#id-view-three), "
                      "[`id-app-comp-a`](#id-app-comp-a), "
                      "[`id-app-comp-c`](B-second.md#id-app-comp-c), "
                      "[`id-mot-req-r`](#id-mot-req-r), "
                      "`id-rel-001` and `id-app-comp-zz`.", mdwrap.unwrap(page))
        self.assertIn("```\nSee `id-app-comp-a` here.\n```", page)          # code is kept
        # On this page, even when an earlier document draws it too; else the first other page.
        self.assertIn("Text with [`id-app-comp-b`](A-first.md#id-app-comp-b) and "
                      "[`id-app-comp-a`](#id-app-comp-a).", togaf()[0]["docs/togaf/B-second.md"])
        self.assertIn("Only [`id-app-comp-b`](A-first.md#id-app-comp-b).",
                      togaf()[0]["docs/togaf/C-third.md"])
        # When no document's view draws the element, it has no target and stays code.
        alone = togaf(togaf_model(first_views=()))[0]["docs/togaf/C-third.md"]
        self.assertIn("Only `id-app-comp-b`.", alone)

    def test_index_lists_phase_document_views_viewpoints_and_artifacts(self):
        xml = togaf_model(first_props=(("viewpoints", "Motivation | Goals"),
                                       ("artifacts", "`CLAUDE.md`,\nEpic issues")))
        index = togaf(xml)[0]["docs/togaf/README.md"]
        self.assertEqual(index.split("\n")[1], "# TOGAF architecture documents")
        table = ("| ADM phase | Document | Views | Suggested viewpoints | Factory artifacts |\n"
                 "|---|---|---|---|---|\n"
                 "| A. Architecture Vision | [A-first.md](A-first.md) | [Two](A-first.md#id-view-two), "
                 "[One](A-first.md#id-view-one) | Motivation \\| Goals | `CLAUDE.md`, Epic issues |\n"
                 "| B. Business Architecture | [B-second.md](B-second.md) | "
                 "[Three](B-second.md#id-view-three) | — |  |\n"
                 "| C. Information Systems | [C-third.md](C-third.md) | — | — |  |\n")
        self.assertIn(table, index)
        # Intro, table, then the closing paragraphs.
        self.assertLess(index.index("Documents refer to model elements by ID"), index.index(table))
        self.assertLess(index.index(table), index.index("**How the phases run in practice:**"))
        self.assertLess(index.index("**How the phases run"), index.index("In this template,"))

    def test_phase_label_of_requirements_management_keeps_centre(self):
        xml = togaf_model().replace('<value xml:lang="en">C</value>',
                                    '<value xml:lang="en">Requirements Management</value>', 1)
        pages, problems = togaf(xml)
        self.assertEqual(problems, [])
        self.assertIn("| Requirements Management (centre) | [C-third.md](C-third.md) |",
                      pages["docs/togaf/README.md"])

    def test_repeated_view_properties_keep_their_order(self):
        model = exchange.read(togaf_model(first_views=("id-view-two", "id-view-three",
                                                       "id-view-one")).encode())
        self.assertEqual(gen_docs.documents(model)[0][0].views,
                         ["id-view-two", "id-view-three", "id-view-one"])

    def test_is_deterministic(self):
        self.assertEqual(togaf(), togaf())


def first_page_linker() -> tuple[gen_docs.Togaf, gen_docs.Document]:
    model = exchange.read(togaf_model().encode())
    docs = gen_docs.documents(model)[0]
    return gen_docs.Togaf(model, docs, gen_docs.adrs(model)[0]), docs[0]


# Texts in which an identifier must not become a link (each would show link syntax as text, or
# nest a link), on the first page, where `id-app-comp-a` has a target.
NOT_LINKED = (
    "`` `id-app-comp-a` ``",                      # double-backtick span around the identifier
    "``id-app-comp-a``",                          # double-backtick span that is the identifier
    "``code `id-app-comp-a` here``",              # identifier inside a longer span
    "```text `id-app-comp-a` ```",                # one-line triple-backtick span
    "[`id-app-comp-a`](https://example.com)",     # already a link
    "[see `id-app-comp-a` here](https://example.com)",
    "![alt `id-app-comp-a`](x.png)",              # an image's alt text
    "\\`id-app-comp-a\\`",                        # escaped backticks: no code span
    "` id-app-comp-a`",                           # the span holds more than the identifier
    "Para.\n\n    `id-app-comp-a` is indented code",
    "```\n`id-app-comp-a`\n```",                   # fenced code
    "~~~~\n`id-app-comp-a`\n~~~\n~~~~",
)


class TogafLinks(unittest.TestCase):
    def test_only_a_single_backtick_span_that_is_the_identifier_is_linked(self):
        togaf_, here = first_page_linker()
        for text in NOT_LINKED:
            with self.subTest(text=text):
                self.assertEqual(togaf_.link_ids(text, here), text)

    def test_several_spans_on_a_line_and_in_a_list_paragraph(self):
        togaf_, here = first_page_linker()
        self.assertEqual(togaf_.link_ids("`id-app-comp-a`, ``x`` and `id-mot-req-r`.", here),
                         "[`id-app-comp-a`](#id-app-comp-a), ``x`` and "
                         "[`id-mot-req-r`](#id-mot-req-r).")
        self.assertEqual(togaf_.link_ids("- item\n\n    `id-app-comp-a` in the item", here),
                         "- item\n\n    [`id-app-comp-a`](#id-app-comp-a) in the item")
        self.assertEqual(togaf_.link_ids("[x](y) then `id-app-comp-a`", here),
                         "[x](y) then [`id-app-comp-a`](#id-app-comp-a)")

    def test_a_document_identifier_links_to_its_page(self):
        togaf_, here = first_page_linker()
        self.assertEqual(togaf_.link_ids("See `id-impl-del-second` and `id-impl-del-first`.", here),
                         "See [`id-impl-del-second`](B-second.md) and "
                         "[`id-impl-del-first`](A-first.md).")


class TogafCells(unittest.TestCase):
    def row(self, xml: str, ident: str, page: str = "docs/togaf/B-second.md") -> str:
        pages, problems = togaf(xml)
        self.assertEqual(problems, [])
        return next(line for line in pages[page].split("\n") if f"`{ident}` |" in line)

    def test_a_name_shows_as_written(self):
        xml = togaf_model().replace(
            "c | see", "&lt;T&gt; *x* _x_ `b` | p ~s~ [l](u) &amp;amp; a\\b", 1)
        self.assertIn(" | \\<T\\> \\*x\\* \\_x\\_ \\`b\\` \\| p \\~s\\~ \\[l\\](u) \\&amp; a\\\\b | ",
                      self.row(xml, "id-app-comp-c"))

    def test_values_with_line_breaks_pipes_and_backticks_stay_in_their_cell(self):
        xml = (togaf_model().replace(">#7<", ">#26\n#27<", 1)
               .replace(">crates/c<", ">a|b`c<", 1).replace(">src/c.rs<", ">src/\nc.rs<", 1))
        row = self.row(xml, "id-app-comp-c")
        self.assertIn(" | #26 #27 | ``a\\|b`c``, `src/ c.rs` | ", row)
        self.assertEqual(row.count(" | "), 6)

    def test_release_lists_only_aggregation_and_association(self):
        plateau = ('<element identifier="id-impl-plat-v1-0-0" xsi:type="Plateau">'
                   '<name xml:lang="en">v1.0.0</name></element>')
        rels = ('<relationship identifier="id-rel-901" xsi:type="Composition" '
                'source="id-impl-plat-v1-0-0" target="id-app-comp-c"/>'
                '<relationship identifier="id-rel-902" xsi:type="Serving" '
                'source="id-impl-plat-v1-0-0" target="id-app-comp-c"/>')
        row = self.row(togaf_model(extra=plateau, rels=rels), "id-app-comp-c")
        self.assertTrue(row.endswith(" | `crates/c`, `src/c.rs` |  |  |"), row)


class TogafProblems(unittest.TestCase):
    def problems(self, old: str, new: str) -> str:
        xml = togaf_model()
        self.assertIn(old, xml)
        return "\n".join(togaf(xml.replace(old, new, 1))[1])

    def test_wrong_identifier(self):
        self.assertIn("document element 'id-impl-del-Third': identifier must be id-impl-del-<slug>",
                      self.problems('"id-impl-del-third"', '"id-impl-del-Third"'))
        self.assertIn("'id-impl-deliverable': identifier must be id-impl-del-<slug>",
                      self.problems('"id-impl-del-third"', '"id-impl-deliverable"'))

    def test_only_a_deliverable_with_a_file_is_a_document(self):
        file = ('<property propertyDefinitionRef="p-file"><value xml:lang="en">'
                "docs/togaf/C-third.md</value></property>")
        other = ('<element identifier="id-impl-del-release-notes" xsi:type="Deliverable">'
                 '<name xml:lang="en">Release notes</name><properties>'
                 '<property propertyDefinitionRef="p-phase"><value xml:lang="en">nonsense'
                 "</value></property></properties></element>")
        for old, new in ((file, ""),                                    # no File
                         ('"id-impl-del-third" xsi:type="Deliverable"',  # not a Deliverable
                          '"id-impl-del-third" xsi:type="WorkPackage"')):
            with self.subTest(new=new):
                xml = togaf_model(extra=other)
                self.assertIn(old, xml)
                pages, problems = togaf(xml.replace(old, new, 1))
                self.assertEqual(problems, [])
                self.assertNotIn("docs/togaf/C-third.md", pages)
                self.assertNotIn("C-third.md", pages["docs/togaf/README.md"])
        self.assertEqual(togaf(togaf_model(extra=other))[1], [])

    def test_phase_must_be_an_adm_phase(self):
        self.assertIn("'id-impl-del-third': Phase must be one of Preliminary, A, B, C, D, E, F, G, "
                      "H, Requirements Management; is 'Phase C'",
                      self.problems('<value xml:lang="en">C</value>',
                                    '<value xml:lang="en">Phase C</value>'))

    def test_document_without_a_name(self):
        self.assertIn("'id-impl-del-third': has no name (the document's title)",
                      self.problems('<name xml:lang="en">C. Third</name>', '<name xml:lang="en"> '
                                    "</name>"))

    def test_a_name_with_a_line_break_is_refused(self):
        self.assertIn("'id-app-comp-c': the name has a line break; write it on one line",
                      self.problems("c | see", "c\nsee"))
        self.assertIn("'id-view-one': the name has a line break",
                      self.problems('<name xml:lang="en">One</name>', '<name xml:lang="en">O\nne'
                                    "</name>"))

    def test_missing_or_repeated_property(self):
        phase = '<property propertyDefinitionRef="p-phase"><value xml:lang="en">C</value></property>'
        self.assertIn("'id-impl-del-third': property Phase is missing", self.problems(phase, ""))
        self.assertIn("'id-impl-del-third': property Phase is given more than once",
                      self.problems(phase, phase + phase))

    def test_wrong_file_form(self):
        for bad in ("docs/togaf/README.md", "docs/togaf/template.md", "docs/C-third.md",
                    "docs/togaf/C third.md", "docs/togaf/C-third.txt"):
            with self.subTest(file=bad):
                self.assertIn("File must be docs/togaf/<name>.md (letters, digits and hyphens; "
                              f"not README.md or template.md), is '{bad}'",
                              self.problems(">docs/togaf/C-third.md<", f">{bad}<"))
        self.assertIn("File = 'docs/togaf/A-first.md' is given to more than one",
                      self.problems(">docs/togaf/C-third.md<", ">docs/togaf/A-first.md<"))

    def test_unknown_or_repeated_view(self):
        self.assertIn("'id-impl-del-second': View = 'id-view-nope' names no view of the model",
                      self.problems('<value xml:lang="en">id-view-three</value>',
                                    '<value xml:lang="en">id-view-nope</value>'))
        self.assertIn("'id-impl-del-first': View = 'id-view-two' is given more than once",
                      "\n".join(togaf(togaf_model(first_views=("id-view-two",) * 2))[1]))

    def test_text_rules_as_for_adrs(self):
        self.assertIn("'id-impl-del-third': a paragraph or list item is spread over several lines",
                      self.problems("Only `id-app-comp-b`.", "Only\nthis."))
        self.assertIn("'id-impl-del-third': has no documentation (the document's narrative)",
                      self.problems('<documentation xml:lang="en">Only `id-app-comp-b`.'
                                    "</documentation>", ""))


class TogafCheck(unittest.TestCase):
    run_main = Check.run_main
    tearDown = Check.tearDown

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "docs" / "architecture").mkdir(parents=True)
        (self.root / gen_docs.MODEL).write_text(togaf_model(), encoding="utf-8")
        views = self.root / gen_docs.VIEWS_DIR
        views.mkdir(parents=True)
        for vid in ("id-view-one", "id-view-two", "id-view-three"):
            (views / f"{vid}.png").write_bytes(b"png")

    def test_write_then_check_passes(self):
        self.assertEqual(self.run_main()[0], 0)
        code, out = self.run_main("--check")
        self.assertEqual(code, 0, out)
        self.assertIn("7 generated pages are current", out)

    def test_hand_edited_togaf_page_fails(self):
        self.run_main()
        page = self.root / "docs/togaf/B-second.md"
        page.write_text(page.read_text().replace("Text with", "Text,"), encoding="utf-8")
        code, out = self.run_main("--check")
        self.assertEqual(code, 1)
        self.assertIn("docs/togaf/B-second.md is stale or was edited by hand", out)

    def test_orphan_togaf_page_fails_but_the_template_is_allowed(self):
        self.run_main()
        (self.root / "docs/togaf/template.md").write_text("guide\n", encoding="utf-8")
        (self.root / "docs/togaf/Z-gone.md").write_text("old\n", encoding="utf-8")
        code, out = self.run_main("--check")
        self.assertEqual(code, 1)
        self.assertIn("docs/togaf/Z-gone.md is an orphan: no element in docs/architecture/model.xml "
                      "has File = docs/togaf/Z-gone.md", out)
        self.assertNotIn("template.md is", out)

    def test_missing_togaf_page_fails(self):
        self.run_main()
        (self.root / "docs/togaf/C-third.md").unlink()
        code, out = self.run_main("--check")
        self.assertEqual(code, 1)
        self.assertIn("docs/togaf/C-third.md is missing", out)

    def test_view_without_committed_image_fails_unless_images_are_skipped(self):
        self.run_main()
        (self.root / gen_docs.VIEWS_DIR / "id-view-three.png").unlink()
        code, out = self.run_main("--check")
        self.assertEqual(code, 1)
        self.assertIn("document element 'id-impl-del-second': View = 'id-view-three' has no image "
                      "docs/architecture/views/id-view-three.png; run `just model`", out)
        self.assertEqual(self.run_main("--check", "--no-images")[0], 0)

    def test_model_problem_fails_and_writes_nothing(self):
        (self.root / gen_docs.MODEL).write_text(togaf_model(narrative="two\\nlines"),
                                                encoding="utf-8")
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("option A", out)
        self.assertFalse((self.root / "docs/togaf").exists())


class RealModel(unittest.TestCase):
    def test_the_repository_pages_are_current(self):
        root = HERE.parents[2]
        pages, problems = gen_docs.render(exchange.read((root / gen_docs.MODEL).read_bytes()))
        self.assertEqual(problems, [])
        self.assertEqual(gen_docs.compare(pages, root), [])
        docs = gen_docs.documents(exchange.read((root / gen_docs.MODEL).read_bytes()))[0]
        self.assertEqual(len(docs), 10)
        self.assertEqual(gen_docs.missing_images(docs, root), [])


if __name__ == "__main__":
    unittest.main()


PLATEAUS = "".join(
    f'<element identifier="id-impl-plat-{k}" xsi:type="Plateau"><name xml:lang="en">Release '
    f'{k.replace("-", ".")}</name><properties><property propertyDefinitionRef="p-tag">'
    f'<value xml:lang="en">{k.replace("-", ".")}</value></property></properties></element>'
    for k in ("v0-10-0", "v0-2-1", "v0-2-0"))


def release_rels(*links: tuple[str, str, str]) -> str:
    return "".join(f'<relationship identifier="id-rel-9{n:02}" xsi:type="{kind}" source="{s}" '
                   f'target="{t}"/>' for n, (kind, s, t) in enumerate(links))


class Releases(unittest.TestCase):
    def model(self, *links: tuple[str, str, str]) -> str:
        return (togaf_model(extra=PLATEAUS, rels=release_rels(*links))
                .replace("</propertyDefinitions>",
                         '<propertyDefinition identifier="p-tag" type="string"><name '
                         'xml:lang="en">Tag</name></propertyDefinition></propertyDefinitions>'))

    def release_cell(self, xml: str, ident: str = "id-app-comp-a") -> str:
        pages, problems = togaf(xml)
        self.assertEqual(problems, [])
        row = next(r for r in pages["docs/togaf/A-first.md"].split("\n") if f"`{ident}` |" in r)
        return row.split(" | ")[-2]

    def test_plateaus_are_sorted_by_version_number_not_by_text(self):
        xml = self.model(("Aggregation", "id-impl-plat-v0-10-0", "id-app-comp-a"),
                         ("Aggregation", "id-impl-plat-v0-2-1", "id-app-comp-a"),
                         ("Aggregation", "id-impl-plat-v0-2-0", "id-app-comp-a"))
        self.assertEqual(self.release_cell(xml),
                         "Release v0.2.0, Release v0.2.1, Release v0.10.0")

    def test_a_plateau_is_listed_once_per_element_even_with_two_relationships(self):
        xml = self.model(("Aggregation", "id-impl-plat-v0-2-1", "id-app-comp-a"),
                         ("Association", "id-impl-plat-v0-2-1", "id-app-comp-a"),
                         ("Association", "id-app-comp-a", "id-impl-plat-v0-2-1"))
        self.assertEqual(self.release_cell(xml), "Release v0.2.1")

    def test_an_association_counts_in_either_direction(self):
        xml = self.model(("Association", "id-app-comp-a", "id-impl-plat-v0-2-0"),
                         ("Association", "id-impl-plat-v0-2-1", "id-app-comp-a"))
        self.assertEqual(self.release_cell(xml), "Release v0.2.0, Release v0.2.1")

    def test_an_adr_page_says_in_which_releases_it_was_released(self):
        xml = self.model(("Aggregation", "id-impl-plat-v0-10-0", "id-mot-adr-0001"),
                         ("Association", "id-mot-adr-0001", "id-impl-plat-v0-2-1"),
                         ("Aggregation", "id-impl-plat-v0-2-1", "id-mot-adr-0001"))
        pages = rendered(xml)[0]
        self.assertIn("- ArchiMate elements: `id-app-comp-a`, `id-app-comp-b`, `id-mot-req-r`\n"
                      "- Released in: v0.2.1, v0.10.0\n", pages["docs/adr/0001-first.md"])
        self.assertNotIn("Released in", pages["docs/adr/0002-second.md"])
        self.assertNotIn("Released in", rendered()[0]["docs/adr/0001-first.md"])


class ViewText(unittest.TestCase):
    def test_a_code_span_over_two_lines_in_a_views_documentation_is_refused(self):
        xml = togaf_model().replace("Shows `id-app-comp-c`.",
                                    "Who does what `x\n`id-bus-proc-review` b in the lifecycle.")
        problems = "\n".join(togaf(xml)[1])
        self.assertIn("view 'id-view-two': a paragraph or list item is spread over several "
                      "lines", problems)

    def test_a_views_documentation_over_two_lines_is_refused_only_when_a_document_shows_it(self):
        spread = "Shows\n`id-app-comp-c`."
        problems = togaf(togaf_model().replace("Shows `id-app-comp-c`.", spread))[1]
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("view 'id-view-two': a paragraph or list item is spread over several "
                      "lines",
                      problems[0])
        hidden = togaf_model(first_views=("id-view-one",)).replace("Shows `id-app-comp-c`.",
                                                                   spread)
        self.assertEqual(togaf(hidden)[1], [])


class SurvivingRules(unittest.TestCase):
    """Rules that a reviewer's mutation run showed nothing tested."""

    def test_a_span_closes_only_with_a_backtick_run_of_equal_length(self):
        self.assertEqual(gen_docs._spans("`a`"), [(0, 3, 1, False)])
        self.assertEqual(gen_docs._spans("`a``"), [])
        self.assertEqual(gen_docs._spans("``a`"), [])
        self.assertEqual(gen_docs._spans("``a`` `b`"), [(0, 5, 2, False), (6, 9, 1, False)])

    def test_a_backslash_escapes_the_next_character_outside_spans(self):
        self.assertEqual(gen_docs._spans("\\`a`"), [])
        self.assertEqual(gen_docs._spans("\\\\`a`"), [(2, 5, 1, False)])

    def test_a_code_value_with_a_backtick_at_either_end_is_padded(self):
        self.assertEqual(gen_docs._code("`x"), "`` `x ``")
        self.assertEqual(gen_docs._code("x`"), "`` x` ``")
        self.assertEqual(gen_docs._code("`"), "`` ` ``")
        self.assertEqual(gen_docs._code("a`b"), "``a`b``")

    def test_a_repeated_viewpoints_or_artifacts_property_is_refused(self):
        for key in ("viewpoints", "artifacts"):
            with self.subTest(key=key):
                xml = togaf_model(first_props=((key, "a"), (key, "b")))
                self.assertIn(f"'id-impl-del-first': property {key.capitalize()} is given more "
                              "than once", "\n".join(togaf(xml)[1]))

    def test_a_views_name_is_escaped_in_its_heading(self):
        xml = togaf_model().replace('<name xml:lang="en">One</name>',
                                    '<name xml:lang="en">A *b* &lt;c&gt; |d</name>')
        page = togaf(xml)[0]["docs/togaf/A-first.md"]
        self.assertIn('## <a id="id-view-one"></a>A \\*b\\* \\<c\\> \\|d\n', page)
