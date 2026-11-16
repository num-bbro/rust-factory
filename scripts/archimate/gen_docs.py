#!/usr/bin/env python3
"""Generate the ADR and TOGAF pages from the model (ADR 0009).

  python3 -I gen_docs.py [ROOT]            write docs/adr/NNNN-*.md, docs/adr/README.md,
                                           docs/togaf/*.md and docs/togaf/README.md
  python3 -I gen_docs.py --check [ROOT]    re-render in memory; exit 1 naming each page that is
                                           stale, missing or an orphan
  --no-images                              skip the check that each view a document shows has a
                                           committed image (`just model` uses it before the
                                           build that renders the images)

ROOT is the repository (default: this script's). The model is ROOT/docs/architecture/model.xml.

ADRs. Each ADR is a `Constraint` with identifier `id-mot-adr-NNNN` and name `ADR NNNN: <title>`,
and the properties Status, Date, Issue, Deciders and File (the page's path,
`docs/adr/NNNN-<slug>.md`). Its documentation is the page's Markdown body with each paragraph and
list item on one line (ADR 0009, line breaks: option A); the page wraps them again at 100
characters (mdwrap.py). The header list's "ArchiMate elements" are the sources of the Realization
and Influence relationships to the ADR, sorted; a directed Association named `supersedes` from a
newer ADR to an older one gives the "Supersedes" and "Superseded by" lines; it and the older ADR's
`Status = Superseded by NNNN` must agree.

TOGAF documents. A document is a `Deliverable` with a `File` property (any other Deliverable is
an ordinary element): identifier `id-impl-del-<slug>`, the document's title as name, the
properties File (`docs/togaf/<name>.md`) and Phase (one of PHASES), once each, optionally
Viewpoints and Artifacts (Markdown, shown in the index), and an ordered, repeated `View` naming
the views that belong to the document. Its documentation is the narrative, one line per paragraph
and list item as for the ADRs. The page is the narrative, in which an identifier that is the whole
content of a single-backtick code span becomes a link when it has a target (an ADR or a document
→ its page; a view → its section here, else in the first other document showing it; an element →
its catalog row here, else in the first other document whose views draw it); code blocks, longer
code spans and link texts are never linked. Then one section per view in `View` order: heading
(the view's name), the view's documentation, its committed image
`docs/architecture/views/<view-id>.png` and a catalog of the elements it draws, sorted by
identifier (id, name, type, decisions, issues, crate / code, release, other documents). The release
column is there only when the model has `Plateau` elements. Names and issue references are
escaped so that they show as written; a name with a line break is refused. Anchors are
identifiers: a view's section has its view id, an element's first catalog row on a page has its
element id. Documents are taken in File order. `docs/togaf/README.md` is the generated index.

An orphan is a `.md` page in `docs/adr/` or `docs/togaf/` that the model does not produce;
`template.md` (the hand-written guide) in each is the exception. Orphans are reported, never
deleted. The output depends on the model only: no dates, no paths of this machine.
"""

from __future__ import annotations

import posixpath
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Sibling modules. Added explicitly because `python3 -I` (isolated mode) leaves the script's
# own folder off sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import exchange  # noqa: E402
import mdwrap  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MODEL = "docs/architecture/model.xml"
ADR_DIR = "docs/adr"
INDEX = f"{ADR_DIR}/README.md"
TOGAF_DIR = "docs/togaf"
TOGAF_INDEX = f"{TOGAF_DIR}/README.md"
VIEWS_DIR = "docs/architecture/views"
PAGE_DIRS = (ADR_DIR, TOGAF_DIR)
HAND_WRITTEN = {f"{ADR_DIR}/template.md", f"{TOGAF_DIR}/template.md"}
ADR_ID = re.compile(r"id-mot-adr-(\d{4})")
DOC_ID = re.compile(r"id-impl-del-[a-z0-9]+(-[a-z0-9]+)*")
DOC_FILE = re.compile(rf"{TOGAF_DIR}/[A-Za-z0-9]+(-[A-Za-z0-9]+)*\.md")
HEADER_PROPS = ("Status", "Date", "Issue", "Deciders")
DOC_PROPS = ("File", "Phase")
DOC_TEXT_PROPS = ("Viewpoints", "Artifacts")
LINKS = ("Realization", "Influence")
RELEASE_LINKS = ("Aggregation", "Association")
SUPERSEDES = "supersedes"
CODE_ID = re.compile(r"id-[a-z0-9-]+")


def generated_note(source: str, guide: str = f"{ADR_DIR}/template.md") -> str:
    return (f"<!-- Generated from {MODEL} ({source}) by `just model-docs`. Do not edit: change the "
            f"model, see {guide}. -->")


INDEX_INTRO = f"""\
# Architecture Decision Records

An ADR records **one significant decision**: the context, the options considered, what was chosen and why. The decision of an accepted ADR is never rewritten: corrections and as-built notes are appended as dated `## Amendment YYYY-MM-DD` sections, and a changed decision needs a new ADR that supersedes the old one (whose status becomes `Superseded by NNNN`).

- Source: each ADR is a `Constraint` element in `{MODEL}` (identifier `id-mot-adr-NNNN`) whose documentation is the text. These pages are generated by `just model-docs` and never edited by hand; [template.md](template.md) says how to add an ADR.
- Format: [MADR](https://adr.github.io/madr/).
- Status: `Proposed` (in an open PR) → `Accepted` (PR merged) → `Superseded by NNNN` / `Deprecated`.
- Links: the core elements that implement a decision *realize* its Constraint, the motivation elements that shaped it *influence* it, and a new ADR has a directed Association `supersedes` to the ADR it replaces.

| # | Decision | Status |
|---|---|---|"""

TOGAF_INTRO = """\
# TOGAF architecture documents

The factory follows the **TOGAF Architecture Development Method (ADM)**. Each phase has one document here. The documents hold the *narrative*: purpose, decisions, open questions. The *structure* (actors, processes, applications, nodes and how they relate) lives in the ArchiMate model [`../architecture/model.xml`](../architecture/model.xml). Documents refer to model elements by ID (e.g. `id-bus-proc-review`) instead of repeating them.

Each document is a `Deliverable` element of that model, and these pages are generated from it by `just model-docs`, never edited by hand ([template.md](template.md) says how to add or change one). A page shows the views its document names, each with its diagram and a catalog of the elements drawn.

| ADM phase | Document | Views | Suggested viewpoints | Factory artifacts |
|---|---|---|---|---|"""

TOGAF_OUTRO = """\
**How the phases run in practice:** A–D are done for each epic, iterated lightly as stories are refined. E–F happen when the conductor splits work and plans releases. G is every PR. H is every change request. Requirements management runs continuously on the GitHub Project board.

In this template, the documents describe **the factory itself**. A project created from the template replaces their content with its own business case and keeps the structure. Each document also has a short **Sample domain** part for the reservation service the factory builds as its worked example (epics from #17 on)."""

# The `Phase` values a document may have, in ADM order, with the label the index shows.
PHASES = {"Preliminary": "Preliminary", "A": "A. Architecture Vision",
          "B": "B. Business Architecture", "C": "C. Information Systems",
          "D": "D. Technology Architecture", "E": "E. Opportunities & Solutions",
          "F": "F. Migration Planning", "G": "G. Implementation Governance",
          "H": "H. Architecture Change Mgmt",
          "Requirements Management": "Requirements Management (centre)"}


def _text_problems(where: str, text: str, what: str) -> list[str]:
    """The documentation rules shared by ADRs and documents (ADR 0009, line breaks: option A)."""
    if not text:
        return [f"{where}: has no documentation ({what})"]
    if mdwrap.problems(text):
        return [f"{where}: documentation {p}" for p in mdwrap.problems(text)]
    if mdwrap.unwrap(text) != text:
        return [f"{where}: a paragraph or list item is spread over several lines; store each on "
                "one line (ADR 0009, line breaks: option A)"]
    return []


def _props(model: exchange.Model, ident: str) -> list[tuple[str, str]]:
    """(name, value) of the properties of `ident`, in the model's order."""
    return [(key, value) for owner, key, value in model.properties if owner == ident]


# --- ADRs ---------------------------------------------------------------------------------------

@dataclass
class Adr:
    ident: str
    number: str
    title: str
    props: dict[str, str]
    text: str


def adrs(model: exchange.Model) -> tuple[list[Adr], list[str]]:
    """The ADR elements of the model, in number order, and every problem with them."""
    found, problems = [], []
    for ident in sorted(model.elements):
        m = ADR_ID.fullmatch(ident)
        if not ident.startswith("id-mot-adr-"):
            continue
        where = f"ADR element '{ident}'"
        if m is None:
            problems.append(f"{where}: identifier must be id-mot-adr-NNNN (four digits)")
            continue
        if model.elements[ident] != "Constraint":
            problems.append(f"{where}: must be a Constraint, is a {model.elements[ident]}")
        number = m.group(1)
        name = model.names.get(ident, "")
        title = name.removeprefix(f"ADR {number}: ")
        if title == name or not title.strip():
            problems.append(f"{where}: name must be 'ADR {number}: <title>', is '{name}'")
        props: dict[str, str] = {}
        for key, value in _props(model, ident):
            if key in props:
                problems.append(f"{where}: property {key} is given more than once")
            props[key] = value
        for key in (*HEADER_PROPS, "File"):
            if not props.get(key, "").strip():
                problems.append(f"{where}: property {key} is missing")
        file = props.get("File", "")
        if file and not re.fullmatch(rf"{ADR_DIR}/{number}-[a-z0-9]+(-[a-z0-9]+)*\.md", file):
            problems.append(f"{where}: File must be {ADR_DIR}/{number}-<slug>.md, is '{file}'")
        text = model.documentation.get(ident, "")
        problems += _text_problems(where, text, "the ADR's text")
        found.append(Adr(ident, number, title, props, text))
    return found, problems + superseded(model, found)


def superseded(model: exchange.Model, found: list[Adr]) -> list[str]:
    """`Status = Superseded by NNNN` and the `supersedes` Association must agree."""
    links = {(r["Target"], f"Superseded by {_number(r['Source'])}") for r in model.relationships
             if r["Type"] == "Association" and r["Name"] == SUPERSEDES}
    states = {(a.ident, a.props.get("Status", "")) for a in found
              if a.props.get("Status", "").startswith("Superseded by")}
    def source(status: str) -> str:
        m = re.fullmatch(r"Superseded by (\d{4})", status)
        return f"from id-mot-adr-{m.group(1)}" if m else "(Status must be 'Superseded by NNNN')"

    return ([f"ADR element '{i}': Status = '{s}' needs a `{SUPERSEDES}` Association to it "
             f"{source(s)}, and no other" for i, s in sorted(states - links)]
            + [f"ADR element '{i}': a `{SUPERSEDES}` Association makes its Status '{s}'"
               for i, s in sorted(links - states)])


def _number(ident: str) -> str:
    m = ADR_ID.fullmatch(ident)
    return m.group(1) if m else ident


def page(adr: Adr, model: exchange.Model) -> str:
    """One ADR page: generated note, title, header list, body; wrapped at mdwrap.WIDTH."""
    linked = sorted({r["Source"] for r in model.relationships
                     if r["Target"] == adr.ident and r["Type"] in LINKS})
    supersedes = [r for r in model.relationships
                  if r["Type"] == "Association" and r["Name"] == SUPERSEDES]
    header = [f"- {key}: {adr.props.get(key, '')}" for key in HEADER_PROPS]
    if linked:
        header.append("- ArchiMate elements: " + ", ".join(f"`{i}`" for i in linked))
    header += [f"- Supersedes: ADR {_number(r['Target'])}"
               for r in sorted(supersedes, key=lambda r: r["Target"]) if r["Source"] == adr.ident]
    header += [f"- Superseded by: ADR {_number(r['Source'])}"
               for r in sorted(supersedes, key=lambda r: r["Source"]) if r["Target"] == adr.ident]
    text = "\n".join([generated_note(adr.ident), f"# {adr.number}. {adr.title}", "", *header, "",
                      adr.text])
    return mdwrap.wrap(text) + "\n"


def index(found: list[Adr]) -> str:
    files = {a.number: Path(a.props.get("File", "")).name for a in found}

    def status(value: str) -> str:
        return re.sub(r"(Superseded by )(\d{4})\b",
                      lambda m: f"{m.group(1)}[{m.group(2)}]({files[m.group(2)]})"
                      if m.group(2) in files else m.group(0), value)

    rows = [f"| [{a.number}]({files[a.number]}) | {_cell(a.title)} | "
            f"{status(a.props.get('Status', ''))} |" for a in found]
    return mdwrap.wrap("\n".join([generated_note("the ADR elements"), INDEX_INTRO, *rows])) + "\n"


# --- TOGAF documents ----------------------------------------------------------------------------

@dataclass
class Document:
    ident: str
    title: str
    file: str
    phase: str
    views: list[str]
    text: str
    viewpoints: str = ""
    artifacts: str = ""


def documents(model: exchange.Model) -> tuple[list[Document], list[str]]:
    """The documents of the model, in File order, and every problem with them.

    A document is a `Deliverable` with a `File` property; any other Deliverable is an ordinary
    element, which the generator leaves alone.
    """
    found, problems = [], []
    for ident in sorted(model.elements):
        props = _props(model, ident)
        if model.elements[ident] != "Deliverable" or not any(k == "File" for k, _ in props):
            continue
        where = f"document element '{ident}'"
        if not DOC_ID.fullmatch(ident):
            problems.append(f"{where}: identifier must be id-impl-del-<slug>")
            continue
        single: dict[str, str] = {}
        views: list[str] = []
        for key, value in props:
            if key == "View":
                if value not in model.views:
                    problems.append(f"{where}: View = '{value}' names no view of the model")
                elif value in views:
                    problems.append(f"{where}: View = '{value}' is given more than once")
                else:
                    views.append(value)
            elif key in single and key in (*DOC_PROPS, *DOC_TEXT_PROPS):
                problems.append(f"{where}: property {key} is given more than once")
            else:
                single[key] = value
        for key in DOC_PROPS:
            if not single.get(key, "").strip():
                problems.append(f"{where}: property {key} is missing")
        file = single.get("File", "")
        if file and (not DOC_FILE.fullmatch(file) or file == TOGAF_INDEX or file in HAND_WRITTEN):
            problems.append(f"{where}: File must be {TOGAF_DIR}/<name>.md (letters, digits and "
                            f"hyphens; not README.md or template.md), is '{file}'")
            file = ""
        phase = single.get("Phase", "")
        if phase.strip() and phase not in PHASES:
            problems.append(f"{where}: Phase must be one of " + ", ".join(PHASES)
                            + f"; is '{phase}'")
        title = model.names.get(ident, "")
        if not title.strip():
            problems.append(f"{where}: has no name (the document's title)")
        text = model.documentation.get(ident, "")
        problems += _text_problems(where, text, "the document's narrative")
        found.append(Document(ident, title, file, phase, views, text,
                              single.get("Viewpoints", ""), single.get("Artifacts", "")))
    files = [d.file for d in found if d.file]
    problems += [f"document elements: File = '{f}' is given to more than one"
                 for f in sorted({f for f in files if files.count(f) > 1})]
    return sorted(found, key=lambda d: (d.file, d.ident)), problems


def line_breaks(model: exchange.Model) -> list[str]:
    """Names with a line break: a name is one line in a heading, a link or a table row."""
    return [f"'{ident}': the name has a line break; write it on one line"
            for ident, name in sorted(model.names.items()) if "\n" in name.strip()]


def href(from_file: str, to_file: str, anchor: str = "") -> str:
    """The link from page `from_file` to `to_file` (both repository paths), at `anchor`.

    Every link of the TOGAF pages is made here: the place where step 7 plugs in the site's base
    URL for an element's own page.
    """
    if to_file == from_file and anchor:
        return f"#{anchor}"
    fragment = f"#{anchor}" if anchor else ""
    return posixpath.relpath(to_file, posixpath.dirname(from_file)) + fragment


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _text(text: str) -> str:
    """Plain text (a name, an issue reference) as Markdown that shows it as written, on one line,
    also in a table cell: line breaks become spaces, and the characters that would start
    emphasis, code, a link, HTML, strikethrough, a cell break or an entity are escaped."""
    escaped = re.sub(r"([\\`*_\[\]<>|~])", r"\\\1", " ".join(text.split()))
    return re.sub(r"&(?=#?\w+;)", r"\\&", escaped)


def _markdown_cell(text: str) -> str:
    """A Markdown value (`Artifacts`, `Viewpoints`) as one table cell: line breaks become spaces,
    and `|` is escaped (also inside code, where GitHub's tables need it too)."""
    return re.sub(r"(?<!\\)\|", r"\\|", " ".join(text.split()))


def _code(text: str) -> str:
    """A value (`Crate`, `Code`) as a code span that fits in a table cell."""
    value = " ".join(text.split()).replace("|", "\\|")
    ticks = "`" * (max((len(r) for r in re.findall(r"`+", value)), default=0) + 1)
    pad = " " if value.startswith("`") or value.endswith("`") else ""
    return f"{ticks}{pad}{value}{pad}{ticks}"


def _spans(line: str) -> list[tuple[int, int, int, bool]]:
    """The code spans of one line: (start, end, backtick count, inside a link's text) each.

    A run of n backticks opens a span that the next run of exactly n closes (CommonMark); a run
    without a closer is plain text. A backslash escapes the next character outside spans.
    """
    spans, depth, i = [], 0, 0
    while i < len(line):
        char = line[i]
        if char == "\\":
            i += 2
            continue
        if char == "`":
            run = len(line[i:]) - len(line[i:].lstrip("`"))
            close = next((m.start() for m in re.finditer(r"`+", line[i + run:])
                          if len(m.group(0)) == run), None)
            if close is None:
                i += run
                continue
            end = i + run + close + run
            spans.append((i, end, run, depth > 0))
            i = end
            continue
        if char == "[":
            depth += 1
        elif char == "]" and depth:
            depth -= 1
        i += 1
    return spans


class Togaf:
    """The TOGAF pages of a model: what each document shows and where each identifier links."""

    def __init__(self, model: exchange.Model, docs: list[Document], adr_found: list[Adr]):
        self.model = model
        self.docs = [d for d in docs if d.file]
        self.adr_files = {a.ident: a.props["File"] for a in adr_found if a.props.get("File")}
        self.doc_files = {d.ident: d.file for d in self.docs}
        self.drawn: dict[str, set[str]] = {d.file: {e for v in d.views for e in model.views[v]}
                                           for d in self.docs}
        self.releases: dict[str, list[str]] = {}
        plateaus = sorted(i for i, kind in model.elements.items() if kind == "Plateau")
        self.has_releases = bool(plateaus)
        for p in plateaus:
            for r in model.relationships:
                if r["Source"] == p and r["Type"] in RELEASE_LINKS:
                    self.releases.setdefault(r["Target"], []).append(model.names.get(p, p))

    def target(self, ident: str, here: Document) -> str | None:
        """Where `ident`, written in `here`'s text, links to; None when it has no target."""
        if ident in self.adr_files:
            return href(here.file, self.adr_files[ident])
        if ident in self.doc_files:
            return href(here.file, self.doc_files[ident])
        if ident in self.model.views:
            shown = [d for d in self.docs if ident in d.views]
        elif ident in self.model.elements:
            shown = [d for d in self.docs if ident in self.drawn[d.file]]
        else:
            return None
        if any(d.file == here.file for d in shown):
            return href(here.file, here.file, ident)
        return href(here.file, shown[0].file, ident) if shown else None

    def link_ids(self, text: str, here: Document) -> str:
        """`text` with each identifier that has a target made a link. Only a code span of single
        backticks whose whole content is the identifier counts, and not inside a link's text;
        fenced and indented code, and spans of two or more backticks, are left as they are."""
        lines = text.split("\n")
        code = mdwrap.code_lines(text)
        for n, line in enumerate(lines):
            if n in code:
                continue
            for start, end, run, in_link in reversed(_spans(line)):
                ident = line[start + run:end - run]
                to = None
                if run == 1 and not in_link and CODE_ID.fullmatch(ident):
                    to = self.target(ident, here)
                if to is not None:
                    line = f"{line[:start]}[{line[start:end]}]({to}){line[end:]}"
            lines[n] = line
        return "\n".join(lines)

    def catalog(self, view: str, here: Document, anchored: set[str]) -> list[str]:
        """The catalog table of the elements `view` draws, one row each, sorted by identifier."""
        heads = ["ID", "Name", "Type", "Decisions", "Issues", "Crate / code"]
        if self.has_releases:
            heads.append("Release")
        heads.append("Other documents")
        rows = ["| " + " | ".join(heads) + " |", "|" + "---|" * len(heads)]
        for ident in sorted(set(self.model.views[view])):
            anchor = "" if ident in anchored else f'<a id="{ident}"></a>'
            anchored.add(ident)
            props = _props(self.model, ident)
            decisions = sorted({r["Target"] for r in self.model.relationships
                                if r["Source"] == ident and r["Type"] in LINKS
                                and ADR_ID.fullmatch(r["Target"])})
            cells = [f"{anchor}`{ident}`", _text(self.model.names.get(ident, "")),
                     self.model.elements[ident],
                     ", ".join(f"[ADR {_number(a)}]({href(here.file, self.adr_files[a])})"
                               if a in self.adr_files else f"ADR {_number(a)}" for a in decisions),
                     ", ".join(_text(v) for k, v in props if k == "Issue"),
                     ", ".join(_code(v) for k, v in props if k in ("Crate", "Code"))]
            if self.has_releases:
                cells.append(", ".join(_text(r) for r in self.releases.get(ident, [])))
            cells.append(", ".join(f"[{_text(d.title)}]({href(here.file, d.file, ident)})"
                                   for d in self.docs
                                   if d.file != here.file and ident in self.drawn[d.file]))
            rows.append("| " + " | ".join(cells) + " |")
        return rows

    def page(self, doc: Document) -> str:
        """One document page: generated note, title, narrative, then a section per view."""
        lines = [generated_note(doc.ident, f"{TOGAF_DIR}/template.md"), f"# {doc.title}", "",
                 self.link_ids(doc.text, doc)]
        anchored: set[str] = set()
        for view in doc.views:
            name = _text(self.model.names.get(view, view))
            lines += ["", f'## <a id="{view}"></a>{name}', ""]
            text = self.model.documentation.get(view, "")
            if text:
                lines += [self.link_ids(text, doc), ""]
            lines += [f"![{name}]({href(doc.file, f'{VIEWS_DIR}/{view}.png')})", "",
                      *self.catalog(view, doc, anchored)]
        return mdwrap.wrap("\n".join(lines)) + "\n"

    def index(self) -> str:
        rows = []
        for d in self.docs:
            views = ", ".join(f"[{_text(self.model.names.get(v, v))}]"
                              f"({href(TOGAF_INDEX, d.file, v)})" for v in d.views)
            name = posixpath.basename(d.file)
            rows.append(f"| {_text(PHASES.get(d.phase, d.phase))} | [{_text(name)}]"
                        f"({href(TOGAF_INDEX, d.file)}) | {views or '—'} | "
                        f"{_markdown_cell(d.viewpoints) or '—'} | {_markdown_cell(d.artifacts)} |")
        return mdwrap.wrap("\n".join([generated_note("the Deliverable elements",
                                                     f"{TOGAF_DIR}/template.md"),
                                      TOGAF_INTRO, *rows, "", TOGAF_OUTRO])) + "\n"


def missing_images(docs: list[Document], root: Path) -> list[str]:
    """Each view a document shows whose image is not committed."""
    return [f"document element '{d.ident}': View = '{v}' has no image {VIEWS_DIR}/{v}.png; run "
            f"`just model` and commit `{VIEWS_DIR}/`"
            for d in docs for v in d.views if not (root / VIEWS_DIR / f"{v}.png").is_file()]


# --- all pages ----------------------------------------------------------------------------------

def render(model: exchange.Model) -> tuple[dict[str, str], list[str]]:
    """{repository-relative path: content} for every generated page, and the model's problems."""
    found, problems = adrs(model)
    pages = {a.props["File"]: page(a, model) for a in found if a.props.get("File")}
    pages[INDEX] = index(found)
    docs, doc_problems = documents(model)
    doc_problems += line_breaks(model)
    togaf = Togaf(model, docs, found)
    pages.update({d.file: togaf.page(d) for d in togaf.docs})
    pages[TOGAF_INDEX] = togaf.index()
    return dict(sorted(pages.items())), problems + doc_problems


def compare(pages: dict[str, str], root: Path) -> list[str]:
    """Each page that differs from the rendering, is missing, or is not produced by the model."""
    problems = []
    for rel, content in pages.items():
        path = root / rel
        if not path.is_file():
            problems.append(f"{rel} is missing: run `just model-docs`")
        elif path.read_text(encoding="utf-8") != content:
            problems.append(f"{rel} is stale or was edited by hand: change the model, then run "
                            "`just model-docs`")
    for folder in PAGE_DIRS:
        for path in sorted((root / folder).glob("*.md")):
            rel = path.relative_to(root).as_posix()
            if rel not in pages and rel not in HAND_WRITTEN:
                problems.append(f"{rel} is an orphan: no element in {MODEL} has File = {rel}; "
                                "add the element or delete the page")
    return problems


def main(argv: list[str]) -> int:
    check = "--check" in argv
    images = "--no-images" not in argv
    args = [a for a in argv if a not in ("--check", "--no-images")]
    if len(args) > 1 or any(a.startswith("-") for a in args):
        print(__doc__, file=sys.stderr)
        return 2
    root = Path(args[0]) if args else ROOT
    try:
        model = exchange.read((root / MODEL).read_bytes())
    except (OSError, exchange.FormatError) as err:
        print(f"{MODEL}: {err}", file=sys.stderr)
        return 1
    pages, problems = render(model)
    if not check and not problems:
        for rel, content in pages.items():
            path = root / rel
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                print(f"wrote {rel}")
    problems += compare(pages, root)
    if images:
        problems += missing_images(documents(model)[0], root)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"pages: {len(pages)} generated pages are current")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
