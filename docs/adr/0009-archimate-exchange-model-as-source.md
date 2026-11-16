# 0009. ArchiMate exchange model as the single source of the architecture documentation

- Status: Accepted
- Date: 2026-11-16
- Issue: #41 (change request), #42 (task: spike and this ADR)
- Deciders: human approver (requirements confirmed one at a time and plan approved on
  2026-11-16; sign-off at gate 1 by merging this ADR), architect agent
- ArchiMate elements: `id-mot-req-togaf`, `id-tech-sw-archi`; the decision, document and release
  elements of the mapping below are added by the follow-up steps
- Supersedes: ADR 0002

## Context and problem
Today the architecture documentation has three hand-edited sources: the model in
`docs/architecture/model/*.csv` (Archi's CSV layout plus a `views.csv` this repo invented, see
ADR 0002), the TOGAF narrative in `docs/togaf/*.md`, and the ADRs in `docs/adr/*.md`. No tool
other than this repo's scripts can read that set, and diagrams exist only as build output: no
document shows one, and no diagram leads to the decisions or documents behind its boxes.

The human's requirement (2026-11-16, change request #41): the maintained form must be a
standard, self-describing ArchiMate format that other software can read, and reading must work
both ways: a document shows its diagrams, and a diagram leads to the decisions, documents and
releases behind each box (`id-mot-req-togaf`).

## Decision drivers
The five requirements the human confirmed on 2026-11-16:
1. **One edited source**: the Open Group *ArchiMate Model Exchange File Format* (XML); the CSV
   files are removed.
2. **ADR and TOGAF text live in the model**; Markdown pages are generated (with diagrams and
   catalog tables), never hand-edited.
3. **Any standard tool** can read it: validated against the official schema on every change;
   nothing Archi-specific.
4. **Read it in both places**: generated Markdown and images committed to the repo, and a public
   GitHub Pages site with clickable diagrams.
5. **Archi is view-only for now**; agents edit the XML in PRs. A round trip through Archi must
   stay possible later.

Also, as before: agents edit it reliably with reviewable diffs, builds run unattended in CI, and
Thai text works.

## Options considered
1. **Exchange XML as the single source, with ADRs, TOGAF documents and releases as model
   elements, and generated Markdown** (chosen).
2. **Keep the CSV source; generate the exchange XML and commit it.** Other tools could read the
   committed file, but it would be a copy of a tool-specific source: two files to keep in step, and
   the edited form would still carry no meaning outside this repo. Fails requirement 1.
3. **Archi's native `.archimate` file as the source.** Readable only by Archi (and jArchi/coArchi),
   not a standard; noisy diffs with Archi's random folder IDs and style data. Fails requirement 3.
4. **Exchange XML for the model, Markdown for ADRs and TOGAF kept outside it.** Smallest change,
   but the link from a box to its decisions and documents would exist only as text conventions
   that no ArchiMate tool understands. Fails requirements 2 and 4 (the "both ways" part).

How to represent a decision (ArchiMate has no "decision" element type):
- **`Constraint`** (chosen): "a factor that limits the realization of goals", which is what an
  accepted ADR is; visibly different from `Requirement`; every core structure or behaviour element
  may *realize* it and every element may *influence* it (checked against Archi's
  `relationships.xml`, see the spike).
- *Requirement*: already used for user stories and business requirements; decisions would be
  indistinguishable from them in views and catalogs.
- *Principle*: too general. A principle applies to any system in a context; a decision is
  specific to one problem and one choice. (The relationship rules would allow it: Realization
  from an ApplicationComponent to a Principle is allowed.)
- *Assessment*: an assessment is the *outcome of analysing* a driver, not the choice made; core
  elements may only associate with it or influence it (no Realization), so "this component
  implements ADR N" cannot be said.

## Decision
Chosen: **option 1**, because it is the only option that meets all five requirements, and the
spike (below) shows that the pinned Archi 5.11.0 and the official schema accept everything it
needs without leaving the standard.

### The source file and its canonical form
- One file, `docs/architecture/model.xml`, in namespace
  `http://www.opengroup.org/xsd/archimate/3.0/` with
  `xsi:schemaLocation="http://www.opengroup.org/xsd/archimate/3.0/ http://www.opengroup.org/xsd/archimate/3.1/archimate3_Diagram.xsd"`.
  The format has no include mechanism, so a split source would not be importable by other tools.
- **Canonical form** = what `just model-fmt` writes: UTF-8, LF, 2-space indent, fixed attribute
  order, sections in schema order, items sorted by identifier (parallel additions land in
  different places). `just model-fmt --check` parses, serialises and byte-compares. The spike
  fixed these rules of the form (each is either required by the schema or avoids a difference
  between the schema and Archi):
  - every name, label, documentation and value carries `xml:lang="en"`;
  - an empty `documentation` is omitted, not written empty;
  - `documentation` text has no trailing newline (Archi's export strips it; the generator adds
    one when it writes a page);
  - text is XML-escaped; no CDATA sections and no comments (a comment would not survive a
    parse-and-serialise round);
  - `Access` relationships always state `accessType` (Archi reads a missing one as `Write`, the
    schema's default is `Access`);
  - property definitions have stable identifiers `propid-<slug>`, and every definition is used.
- Identifiers stay our `id-<layer>-<kind>-<slug>` IDs: they are valid `xs:ID`s, and Archi keeps
  every one of them on import.

### Views: agents list members, the formatter lays out
- **Agents never place boxes.** In a view they add only
  `<node xsi:type="Element" elementRef="id-…"/>`; `just model-fmt` computes the node identifiers,
  bands, nesting, coordinates and connections, reusing `scripts/archimate/layout.py` and the view
  emission of `build_exchange.py`. The schema requires `identifier`, `x`, `y`, `w` and `h` on every
  node, so the bare form is formatter input only: the committed (formatted) file always has them,
  and schema validation runs on it.
- A view property `Layout = manual` tells the formatter to leave a hand-arranged view alone
  (for later, when Archi editing is allowed).

### Validation, in `just model-check` (no Archi start, so it stays in the CI `gates` job)
- **Official schema** with `xmllint --noout --nonet --schema archimate3_Diagram.xsd`, the XSDs
  read from the pinned Archi install (`plugins/org.opengroup.archimate.xmlexchange_*.jar`,
  `xsd/`), with an XML catalog that maps the `xml.xsd` import to the copy in the same jar. Their
  sha256 values are pinned in `tools/archi.env`; they are byte-identical to the Open Group's
  published 3.1 schemas. Same principle as `relationships.xml` (ADR 0002 amendment): no second
  copy in the repo.
- `bootstrap.sh` installs `libxml2-utils` (Ubuntu) / `libxml2` (Arch); `just doctor` reports it.
- Kept and pointed at the XML: `check_relationships.py` (relationship rules from Archi's
  `relationships.xml`), the ID convention, document references.
- New: canonical form, generated pages are current, image lock (below), every `View` property
  names an existing view, and every diagram connection joins nodes of its relationship's ends
  (neither the schema nor Archi checks the last two).
- `build.sh` validates with `xmllint` before starting Archi and runs Archi under a timeout:
  Archi's importer hangs instead of exiting when its own schema check fails.

### ADRs → one `Constraint` element each
- Identifier `id-mot-adr-NNNN`, name `ADR NNNN: <title>`; properties `Status`, `Date`, `Issue`,
  `Deciders`, `File` (the generated page). The full text, as Markdown, is the `documentation`
  (Archi's report renders it, other tools show plain text).
- Links replace today's `ADR` property rows and the "ArchiMate elements" header lines:
  **Realization** from the core elements that implement the decision, **Influence** from
  motivation elements that shaped it. "Supersedes" is a **directed Association named
  `supersedes`** from the new ADR to the old one, plus `Status = Superseded by NNNN` on the old
  one. Amendments stay appended, dated sections of the text, as now.

### TOGAF documents → one `Deliverable` element each
- Identifier `id-impl-del-<slug>` (e.g. one per ADM phase); the narrative is the `documentation`;
  properties `File`, `Phase`, and an ordered, repeated `View` naming the views that belong to the
  document (the exchange format has no relationship from an element to a view; Archi keeps
  repeated properties in order).
- The generated page is the narrative (IDs become links) plus, for each view: the image, the
  view's documentation, a link to its clickable page on the site, and a **catalog table** (id,
  name, type, decisions, issues, crate/code, release, other documents). These are TOGAF's
  artifacts (catalogs and diagrams) inside the deliverable.

### Releases → one `Plateau` element each
- Identifier `id-impl-plat-vX-Y-Z`, **Aggregation** to the elements and ADR Constraints it
  delivered, so a release is a box in a diagram and a column in catalogs. ArchiMate does not allow
  a Plateau to aggregate a Deliverable, Driver, Principle, Stakeholder, Assessment, Value,
  Meaning, Work Package, Gap or Implementation Event; for those, a release uses Association.

### Generated output
- One standard-library generator, `scripts/archimate/gen_docs.py`, writes `docs/adr/*.md`,
  `docs/adr/README.md` and `docs/togaf/*.md`, each with a "generated, do not edit" header;
  `--check` re-renders and diffs (fails on stale or orphan files).
- **Images:** Archi's PNGs are committed to `docs/architecture/views/` with a `views.lock` holding,
  per view, a hash of the view's rendering inputs and of the PNG, and its dimensions. `just model`
  writes both; `model-check` fails with "run `just model`" when a view changed without its image.
  PNG bytes are not reproducible across displays (spike item 4), so checks compare the lock, never
  re-rendered bytes.
- **Site:** `.github/workflows/pages.yml` on push to `main` publishes the rendered documents and
  Archi's HTML report (boxes are clickable there) with the official Pages actions. PRs get the
  same site as a downloadable artifact.

### Archi is view-only for now
The human opens `docs/architecture/model.xml` in Archi (File › Import › Open Exchange File) to
look, not to edit. A later "edit in Archi" feature would export, then normalise with
`just model-fmt`; spike item 5 lists what it would have to undo.

### Refinements to the approved plan found by the spike
Rules that go beyond the plan in #41, collected here (details in the sections above and in the
spike):
- `xml:lang="en"` on every name, label, documentation and value.
- An empty `documentation` is omitted.
- No trailing newline in `documentation` text.
- No XML comments (and no CDATA).
- `Access` relationships always state `accessType`.
- Every property definition is used.
- `xsi:schemaLocation` is always written.
- The formatter generates node identifiers (as well as coordinates and connections).
- Two extra checks: every `View` property names an existing view; every diagram connection's
  ends match its relationship's ends.
- `build.sh` runs `xmllint` before Archi, and Archi under a timeout.
- A Plateau uses Association where ArchiMate does not allow Aggregation.
- The "ArchiMate elements" header lines of the ADRs are replaced by relationships, as the `ADR`
  property rows are.
- `views.lock` also stores each view's dimensions; checks never compare re-rendered bytes, and
  `just model` always renders under Xvfb.
- Archi's HTML report is not reproducible and is never compared.
- Size estimate: about 125–150 KB / 2,000–2,200 lines (plan: 110 KB / 1,700 lines).
- "PNG dimensions equal on dev and CI" moves from step 0 to step 4.

## Consequences
- Good: one standard file holds the whole architecture; any conformant tool can import it, and the
  schema check on every PR keeps it conformant.
- Good: reading works both ways: a document page shows its diagrams and catalogs; on the site and
  in Archi, a box leads to its decisions (Constraints), documents (Deliverables) and releases
  (Plateaus).
- Good: no ADR text, TOGAF text and model can drift apart any more: there is one copy.
- Trade-offs the human accepted by approving the plan:
  1. **Prose is written inside XML.** PRs show each text change twice: in `model.xml` and in the
     generated page (the readable one).
  2. **Model changes are serialised.** With one source file, architecture tasks run one after
     another, not in parallel (`/implement` treats `model.xml` as one shared area).
  3. **On GitHub itself, diagrams are pictures;** the catalog table under each diagram gives the
     links. Clicking boxes works on the Pages site and in Archi.
  4. **One-time re-layout** of the four existing diagrams (sorted order changes box positions).
  5. **Size and effort:** `model.xml` grows to about 110 KB / 1,700 lines by the plan's estimate
     (the spike measures about 125–150 KB / 2,000–2,200 lines, see item 6); about 8 PRs, mostly
     hard (Opus) tasks; roughly USD 30–40 at list price.
- Bad: agents must write Markdown as escaped XML text (`&lt;`, `&amp;`); the formatter and the
  generated page make mistakes visible, but diffs of long text are less pleasant than in a `.md`
  file.
- **Open question for the human, to decide before step 3: line breaks inside paragraphs.**
  Archi's HTML report renders every single line break in a documentation text as a `<br/>`
  (spike item 1), and the ADRs and TOGAF files are hard-wrapped at about 100 characters. Two
  options:
  - **(A) Unwrap each paragraph to one line at migration.** The text then reads well in Archi's
    report, on the site and in other tools. The lossless proof of step 3 and 5 then compares
    whitespace-normalised text, not the sha256 of the bytes.
  - **(B) Keep the text byte-identical.** The sha256 proof planned in #41 holds as written, and
    the report (and so the site's element pages) shows ragged paragraphs.
- Follow-up (each one task issue under #41, one PR each; `main` stays green after each):
  1. Canonical reader/writer and `just model-fmt`, schema validation, xmllint in bootstrap and
     doctor, tests on fixtures.
  2. Cutover: `model.xml` replaces the CSV; `build.sh` and `check_relationships.py` read XML; the
     CSV files and `build_exchange.py` are deleted; lossless proof; rules updated. `build.sh`
     validates with `xmllint` before starting Archi and runs Archi under a timeout. The intended
     access type (Read / Write / ReadWrite / Access) of each of the 7 `Access` relationships is
     stated explicitly; the choice per relationship is put to the human in that PR.
  3. ADRs into the model (including this one); generator and check; templates.
  4. Committed view images and `views.lock`; check that PNG dimensions are equal on the dev
     machine and on CI (moved here from step 0, see spike item 4).
  5. TOGAF documents into the model; pages with diagrams and catalogs.
  6. Release Plateaus (v0.1.0, v0.2.0, v0.2.1).
  7. Pages workflow and site (human step: Settings › Pages › Source = "GitHub Actions").
  8. Sweep: skills, reviewer rules, CONTRIBUTING, memory.

## Spike (2026-11-16, Archi 5.11.0, libxml2 2.15.4, Arch Linux)
Throwaway work in a temporary directory, nothing of it committed. Input: today's generated
`build/architecture/model.xml` (53 elements, 69 relationships, 4 views) plus, by hand: Constraints
for ADR 0002 (has a table), ADR 0008 (has a Rust code block with `Result<T, E>`, lists, emphasis)
and a stub ADR 0009; a Deliverable holding the full text of
`docs/togaf/C-information-systems-architecture.md`; a Plateau `Release v0.2.1`; a Realization from
`id-app-comp-application` to the ADR 0008 Constraint; an Influence from `id-mot-req-togaf` to the
ADR 0002 Constraint; a directed Association `supersedes` from ADR 0009 to ADR 0002; Aggregations
from the Plateau to `id-app-comp-application` and to the ADR 0008 Constraint; eight new property
definitions (`propid-status`, `propid-file`, `propid-view`, `propid-layout`, …), a repeated `View`
property, properties on the existing view `id-view-motivation`, a new hand-placed view showing all
of the above, and `xsi:schemaLocation`. Result: 58 elements, 74 relationships, 5 views,
84,394 bytes, 1,148 lines.

### 1. Archi imports the hand-maintained file: yes
- Imported with the exact command line of `scripts/archimate/build.sh`
  (`--abortOnException --xmlexchange.import … --saveModel … --html.createReport …`): "Validated!",
  "XML Imported!", "Report generated!", exit 0, in 3.5 s.
- Every element, relationship, view, node and connection identifier is kept in `model.archimate`
  (296 identifiers in, all present). Property *definition* identifiers are not kept: the native
  format stores properties as key/value pairs. The repeated `View` property keeps its order;
  properties on views are kept and shown on the view's report page; `supersedes` is stored as a
  named, directed Association.
- Documentation is kept byte for byte (sha256 of the text equal before and after import).
- The report page of a Constraint **renders the Markdown**: headings, lists, emphasis, inline code,
  the fenced Rust block (as `<pre><code class="language-rust">`, with `<`, `>` and `&` correct)
  and the ADR 0002 table (as an HTML `<table>`). All 62 element pages with documentation are
  rendered the same way. Each single line break in the source becomes a `<br/>`, so hard-wrapped
  paragraphs show ragged lines (open question under Consequences).
- The view image map links every box to its element page (`<area … href="../elements/<id>.html">`,
  7 of 7 boxes on the spike view). An element page lists its relationships, so
  `id-app-comp-application` links to the ADR 0008 Constraint and to the Plateau.
- All 74 relationships are allowed by Archi's `relationships.xml` (checked with the rules loader of
  `check_relationships.py`). Rules that shape the mapping: Realization to a Constraint is allowed
  from every core structure and behaviour element, but not from motivation elements; Influence to
  a Constraint is allowed from every element; Constraint to Constraint allows Association,
  Aggregation, Composition, Influence and Specialization; a Plateau may not aggregate a
  Deliverable, Driver, Principle, Stakeholder, Assessment, Value, Meaning, Work Package, Gap or
  Implementation Event.
- Adding the Constraint, Deliverable and Plateau, and properties on a view, did not change the
  images of the four existing views (PNG bytes equal to the plain `just model` build).

### 2. Official schema, offline: yes, on libxml2 2.15.4 and 2.9.14
- Command (catalog file with one entry,
  `<system systemId="http://www.w3.org/2001/xml.xsd" uri="file:///…/xsd/xml.xsd"/>`, in the OASIS
  catalog namespace):
  `XML_CATALOG_FILES=catalog.xml xmllint --noout --nonet --schema xsd/archimate3_Diagram.xsd model.xml`
  → "validates", exit 0, for both today's generated file and the spike file. Without the catalog
  the schema does not compile (`archimate3_Model.xsd` imports `http://www.w3.org/2001/xml.xsd`,
  and `--nonet` forbids fetching it), so the catalog is required, not optional.
- Source: `~/.local/opt/archi-5.11.0/plugins/org.opengroup.archimate.xmlexchange_5.11.0.202610161626.jar`,
  directory `xsd/`. sha256:
  - `archimate3_Diagram.xsd` 6419080f4c4bc43b4a7b8acf870146a7bae6c3487a3ce08d3c521c028ea6056e
  - `archimate3_View.xsd` d708ce176403034b1229b892712cfd69660aefe17da4cc54acea1ac35e4a9854
  - `archimate3_Model.xsd` dd451abe3e3193f91dd9544b279af9bbbf17e75ff1ef86f65ad52b3f8cd29794
  - `xml.xsd` (W3C, same jar) f0fa306f2951fb1a477220eb7bdeaa35959c8d0224258f2104d3c4724ba746f7

  The three `archimate3_*.xsd` files are byte-identical to the ones published at
  https://www.opengroup.org/xsd/archimate/3.1/ (same sha256, empty `diff`, fetched 2026-11-16).
- libxml2: `xmllint` 2.15.4 here (Arch). Ubuntu 24.04, the CI runner, ships libxml2 2.9.14. No
  Ubuntu image was available offline, so the same validation was run with libxml2
  2.9.14+dfsg-1.3~deb12u6 (Debian 12, a local builder image, no network) through a 25-line C
  program making the same library calls as `xmllint --nonet --schema` (catalog, no-network entity
  loader, schema parse, validate): the spike file validates; a bare view node, wrong child order
  and an unknown relationship target are rejected; without the catalog the schema does not
  compile. Neither `.github/actions/setup` nor `bootstrap.sh` installs `xmllint` today
  (`libxml2-utils` is not in the Ubuntu package list); step 1 adds it. Whether the runner image
  happens to have it preinstalled was not checked and should not be relied on.

### 3. Strict schema versus Archi
One deviation per file, each validated with the command of item 2 and imported with Archi's
command line (Archi validates with its own Xerces copy of the same XSDs before importing):

| Deviation | xmllint | Archi | Rule for the canonical form / our checks |
|---|---|---|---|
| `documentation` before `name` in an element | rejects | rejects | children in schema order: name, documentation, properties |
| `propertyDefinitions` before `relationships` | rejects | rejects | sections in schema order |
| view `properties` after the nodes | rejects | rejects | view: name, documentation, properties, then nodes and connections |
| element without `name` | rejects | rejects | every element, view and property definition has a name |
| bare view node (no `identifier`, `x`, `y`, `w`, `h`) | rejects | rejects | formatter input only; the committed file is formatted |
| node with identifier but no coordinates | rejects | rejects | same |
| node `elementRef` pointing at a relationship | rejects | rejects | — (schema key/keyref) |
| property referring to an unknown definition | rejects | rejects | — |
| property referring to an element instead of a definition | rejects | rejects | — |
| empty `<properties/>` | rejects | rejects | omit `properties` when there are none |
| relationship to an unknown element | rejects | rejects | — |
| duplicate identifier | rejects | rejects | — |
| identifier with `:` and a space | rejects | rejects | ID convention check gives the clearer message |
| unknown element type (`Decision`) | rejects | rejects | decisions are `Constraint` |
| no `xml:lang` | accepts | accepts | always write `xml:lang="en"` (one form, matches Archi's export) |
| `xml:lang="th"` on documentation | accepts | accepts | Thai text needs no language tag; keep `en` |
| empty `<documentation>` (either spelling) | accepts | accepts, stores nothing | omit it |
| two `documentation` entries, same language | accepts | keeps only the first | at most one per language |
| unused property definition | accepts | accepts | our check: every definition is used |
| CDATA section | accepts | accepts | escape instead, one form |
| XML comment | accepts | accepts | none (lost by the formatter) |
| no `xsi:schemaLocation` | accepts | accepts | always write it (self-describing file) |
| Assignment from a component to a Constraint (not allowed by ArchiMate) | accepts | accepts, stores it | `check_relationships.py` |
| diagram connection whose ends are not the relationship's ends | accepts | accepts, stores it | our check (the formatter generates connections) |

Archi never accepted a file the schema rejects. When its own validation fails, Archi prints the
error and then **hangs** instead of exiting (killed after 60 s), with or without a display. Hence
the rules: validate with `xmllint` first, start Archi only on a valid file, and under a timeout.
Things both accept that our own checks must catch: a relationship type ArchiMate does not allow,
a diagram connection whose ends are not the relationship's ends (Archi stores it as is), and a
`View` property naming a view that does not exist (properties are plain strings).

### 4. Diagram images
- Same machine, same display mode: **byte-identical**. Two runs under Xvfb gave identical PNGs,
  and two runs on the real display gave identical PNGs (also identical to `just model`).
- Same machine, real display versus Xvfb: **bytes differ**, dimensions equal. 0.6–1.8 % of the
  pixels differ, all inside text (anti-aliasing). So bytes depend on the display, not only on the
  machine: `just model` should always render under `xvfb-run` for a stable local result (step 4).
- Dimensions (both modes): `id-view-layered` 1299×1028, `id-view-lifecycle` 1010×432,
  `id-view-motivation` 833×387, `id-view-reservation-cancel` 1423×1246, spike view 620×375.
- Not established here: whether CI (Ubuntu 24.04, Xvfb, other fonts) gives the same dimensions;
  step 4 compares a CI run with the lock.
- The HTML report itself is not byte-reproducible: the folder identifiers in `model.html` are
  random on every run. Adding `<organizations>` with fixed identifiers does not help (Archi still
  generates new folder identifiers, and the order of "used in views" rows on element pages then
  varies too). The site is therefore a build artifact and is never compared.

### 5. Round trip through Archi's export
`--xmlexchange.import spike.xml --xmlexchange.export out.xml --xmlexchange.exportLang en`; the
output validates, and exporting it again gives a byte-identical file (one normalising pass, then a
fixed point). Compared with the input (84 KB → 121 KB, 1,148 → 2,173 lines):
- Kept: every element, relationship, view, node and connection identifier; names, documentation
  text (apart from the trailing newline), property values and their order, view properties, node
  coordinates and sizes, relationship order, section order.
- Changed: elements are reordered (by Archi folder and then type, no longer by our order);
  property definitions are renumbered `propid-1`… in alphabetical order of their names; every
  node and connection gains a `<style>` block (fill and line colours and the machine's font, here
  `Sans`, 144 blocks); attribute order on nodes changes; the trailing newline of each
  documentation is removed; `accessType="Write"` is added to every `Access` relationship that had
  none (7 today), which changes their meaning under the standard's default.
- So a later "edit in Archi" normaliser must: re-sort, map `propid-N` back to `propid-<slug>` by
  name, drop `<style>` unless the view is `Layout = manual`, and keep the explicit `accessType`.
  Nothing is lost that cannot be restored.
- Already true today: Archi shows the 7 `Access` relationships of the current model as *write*
  access, because the generated XML omits `accessType`; the cutover (step 2) should state the
  intended access type of each one.

### 6. Size
The 8 ADRs and 11 TOGAF files hold 43,761 bytes of text once XML-escaped (764 lines). Today's
generated file is 62,014 bytes / 783 lines. Adding the text, about 1 KB of element and property
markup per ADR, document and release, the relationships that replace today's ADR rows and header
lists, and the view nodes for the new elements gives about **125–150 KB and 2,000–2,200 lines**
(the upper end includes ADR 0009 itself, about 16 KB). This is somewhat above the plan's 110 KB /
1,700 lines and does not change the decision: the file stays far below what editors, `xmllint`
and Archi handle comfortably (the 84 KB spike file imports in 3.5 s).

### Requirements check
Every confirmed requirement can be met inside the standard. Nothing in the spike needed an
Archi-specific construct; the differences found are rules of our canonical form and our own
checks, listed above.

## Amendment 2026-11-16: as built in steps 1 and 2
Steps 1 (#44) and 2 (#46) built the tooling and the cutover. This amendment records the points
below, where the tooling as built refines the decision above; each is part of the decision from
now on. Anything not listed here is still decided by the text above, not by the code:
- **XML comments, processing instructions and a DOCTYPE are rejected** with a message naming
  them, not dropped. CDATA is accepted on input and written escaped.
- **Unused property definitions are dropped** by the formatter, with a note on stderr ("every
  definition is used" holds for the written file).
- **A missing `accessType` is written as `Access`** by the formatter (the schema's default), and
  the formatter prints a note on stderr naming the relationship, so the author sees it and can
  choose `Read`, `Write`, `ReadWrite` or `Access`. The committed file therefore always states the
  type; `model-check` cannot tell a chosen `Access` from a defaulted one, so the note is the only
  warning. The cutover states the type on all seven existing ones, and the human chooses them in
  the cutover PR.
- **Rejected for now**: `metadata`, `organizations`, `viewpoints`, `viewpointRef`, elements and
  attributes in foreign namespaces, and texts in a language other than `en`. A future normaliser
  for Archi exports must strip `organizations`, `metadata` and `<style>` (spike item 5) before
  formatting.
- **Views with `Layout = manual`** are copied as they are, so they are exempt from the
  `xml:lang` rule as well as from the layout; only their property-definition references are
  renamed.
- **`xml.xsd` is pinned too**: `tools/archi.env` holds four sha256 values (the three ArchiMate
  schemas and `xml.xsd`), and `xsd_check.py` fails when any of them differs.
- **Trailing whitespace**, not only a trailing newline, is removed from `documentation`; inner
  spaces and line breaks are kept.
- **An empty view** (no members) is valid and written without nodes.
- **View emission** lives in `scripts/archimate/exchange.py` (`add_diagram`, with
  `layout.py`); `build_exchange.py` and the CSV files are gone. `exchange.read` is the one reader
  the checks share.
- **The checks of `just model-check`**, in order: canonical form (`model_fmt.py --check`), schema
  (`xsd_check.py`), relationship rules (`check_relationships.py`), then `check_model.py`: the ID
  convention (before the cutover nothing checked it), every view member is an element, every
  diagram connection joins nodes of its relationship's ends (a plain line without a relationship,
  possible only in a `Layout = manual` view, is skipped), every `View` property names a view,
  every view's `viewpoint` is one of the `ViewpointsEnum` values of the pinned
  `archimate3_View.xsd` (the schema's viewpoint type is a union with `xs:string`, so it accepts
  any text; `build_exchange.py` had checked this against its own list), and every `` `id-…` `` in
  `docs/**/*.md` exists. `build.sh` runs all of them before Archi,
  also in `just model`. The checks for generated pages and the image lock come with steps 3–5.
- **New rule: the model's own identifier is `id-model-<slug>`** (today `id-model-factory`),
  next to `id-<layer>-<kind>-<slug>`, `id-rel-NNN` and `id-view-<slug>`; `CLAUDE.md` lists it.
- **Relationship types** are written without the `Relationship` suffix in the exchange format
  (`Serving`); `check_relationships.py` adds it to look up Archi's rules.
- The model's `Source` property now names `docs/architecture/model.xml`.
- The CI artifact `architecture-model` no longer carries a copy of `model.xml`: the source is in
  the repo.
