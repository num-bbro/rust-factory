# How to add an ADR

ADRs live in the model (ADR 0009): each one is a `Constraint` element in
`docs/architecture/model.xml`, and its page `docs/adr/NNNN-<slug>.md` (and the index
`docs/adr/README.md`) are generated from it. Never edit a generated page; this guide is the one
hand-written file in `docs/adr/`.

## 1. Write the text
The ADR's text is the element's `documentation`: Markdown, starting at the first `##` heading
(the title and the header list are generated). Write **each paragraph and each list item on one
line** (ADR 0009, line breaks: option A); the page wraps them at 100 characters. Fenced code
blocks, tables and headings are kept as written. Body template:

```markdown
## Context and problem
<What forces a decision? Which stories or requirements are involved? 2–5 sentences, one line.>

## Decision drivers
- <criterion, e.g. operability on a single VM>
- <criterion>

## Options considered
1. **<Option A>**: <one line>
2. **<Option B>**: <one line>
3. **<Option C>**: <one line>

## Decision
Chosen: **<Option X>**, because <the reasons, tied to the drivers>.

## Consequences
- Good: <what gets easier>
- Bad: <what gets harder, the costs we accept>
- Follow-up: <issues created as a result, if any>

## Option details (optional)
<Pros and cons per option, measurements, spike results.>
```

## 2. Add the element and its links to `docs/architecture/model.xml`
Take the next free number `NNNN` and relationship ids `id-rel-NNN`. In the XML, escape `&` as
`&amp;`, `<` as `&lt;` and `>` as `&gt;`; no CDATA, no comments. The formatter sorts everything,
so add the element anywhere inside `<elements>` and the relationships anywhere inside
`<relationships>`. The example below is ADR 0010 with three relationships:

- a **Realization** from each core element (component, service, node, …) that implements the
  decision, here `id-app-comp-application`;
- an **Influence** from each motivation element (requirement, goal, driver, …) that shaped it,
  here `id-mot-req-togaf`;
- only when it replaces an older ADR: a directed **Association** named `supersedes` to that ADR,
  here 0008; then also set the old ADR's Status to `Superseded by 0010` (`just model-check`
  fails when the two do not agree).

```xml
<element identifier="id-mot-adr-0010" xsi:type="Constraint">
  <name xml:lang="en">ADR 0010: Short title of the decision</name>
  <documentation xml:lang="en">## Context and problem
One line per paragraph …</documentation>
  <properties>
    <property propertyDefinitionRef="propid-status"><value xml:lang="en">Proposed</value></property>
    <property propertyDefinitionRef="propid-date"><value xml:lang="en">YYYY-MM-DD</value></property>
    <property propertyDefinitionRef="propid-issue"><value xml:lang="en">#NN</value></property>
    <property propertyDefinitionRef="propid-deciders"><value xml:lang="en">human approver, architect agent</value></property>
    <property propertyDefinitionRef="propid-file"><value xml:lang="en">docs/adr/0010-short-title.md</value></property>
  </properties>
</element>

<relationship identifier="id-rel-114" xsi:type="Realization" source="id-app-comp-application" target="id-mot-adr-0010"/>
<relationship identifier="id-rel-115" xsi:type="Influence" source="id-mot-req-togaf" target="id-mot-adr-0010"/>
<relationship identifier="id-rel-116" xsi:type="Association" source="id-mot-adr-0010" target="id-mot-adr-0008" isDirected="true">
  <name xml:lang="en">supersedes</name>
</relationship>
```

The page's "ArchiMate elements" line lists the sources of the Realization and Influence
relationships; "Supersedes" / "Superseded by" come from the Association. Status goes `Proposed`
(open PR) → `Accepted` (PR merged) → `Superseded by NNNN` / `Deprecated`. The decision of an
accepted ADR is never rewritten: corrections and as-built notes are appended as a dated
`## Amendment YYYY-MM-DD` section, and a changed decision needs a new ADR that supersedes it.

## 3. Format, generate, check
```sh
just model-fmt     # canonical form (sorts, indents, lays out views)
just model-docs    # writes docs/adr/NNNN-*.md and docs/adr/README.md
just model-check   # fails if a page is stale, missing or an orphan, or a rule is broken
```

Commit `model.xml` and the generated pages together; the PR names the element id and the page.
