# How to add or change a TOGAF document

TOGAF documents live in the model (ADR 0009): each one is a `Deliverable` element in
`docs/architecture/model.xml`, and its page `docs/togaf/<name>.md` (and the index
`docs/togaf/README.md`) are generated from it. Never edit a generated page; this guide is the one
hand-written file in `docs/togaf/`.

## 1. Write the narrative
The document's narrative is the element's `documentation`: Markdown, starting after the title
(the title is the element's name). Write **each paragraph and each list item on one line**, as for
ADRs (ADR 0009, line breaks: option A, and the Markdown subset of `docs/adr/template.md`); the
page wraps them at 100 characters. Refer to model elements, views and ADRs by ID in backticks
(`` `id-bus-proc-review` ``) and never repeat the model: the page makes each ID a link to its
catalog row, view section or ADR page (an ID nothing on a page shows stays plain code), and
`just model-check` fails on an ID that is not in the model. Body template:

```markdown
**Purpose:** <What this phase is for, one line.>

## Outputs
- <output of the phase>

## Content
<The narrative for this phase, citing element IDs in backticks.>

### Sample domain: <name>
<The part about the worked example, if any.>

## Open questions
- _none yet_
```

## 2. Add or edit the element in `docs/architecture/model.xml`
In the XML, escape `&` as `&amp;`, `<` as `&lt;` and `>` as `&gt;`; no CDATA, no comments. The
formatter sorts the elements, so add a new one anywhere inside `<elements>`. Properties:

- `File`: the generated page, `docs/togaf/<name>.md` (letters, digits and hyphens; existing file
  names never change);
- `Phase`: the ADM phase, shown in the index (`Preliminary`, `A`–`H`, `Requirements Management`);
- `View`, repeated, in the order the page shows them: the views that belong to the document. Each
  gets a section with its name, its documentation, its image and a catalog of the elements it
  draws. A document may have none. Which views belong to which document is the human's decision.

The example below is a document for phase E with one view:

```xml
<element identifier="id-impl-del-opportunities-and-solutions" xsi:type="Deliverable">
  <name xml:lang="en">E. Opportunities &amp; Solutions</name>
  <documentation xml:lang="en">**Purpose:** Decide how to deliver the target architecture.

## Content
One line per paragraph, citing `id-bus-proc-plan` …</documentation>
  <properties>
    <property propertyDefinitionRef="propid-file"><value xml:lang="en">docs/togaf/E-opportunities-and-solutions.md</value></property>
    <property propertyDefinitionRef="propid-phase"><value xml:lang="en">E</value></property>
    <property propertyDefinitionRef="propid-view"><value xml:lang="en">id-view-lifecycle</value></property>
  </properties>
</element>
```

A catalog row shows, for each element a view draws: its id, name and type, its decisions (the
ADRs it realizes or influences), its `Issue`, `Crate` and `Code` properties, and the other
documents whose views draw it. A release column appears once the model has `Plateau` elements.

## 3. Format, generate, check
```sh
just model-fmt     # canonical form (sorts, indents, lays out views)
just model-docs    # writes docs/togaf/*.md, docs/togaf/README.md and the ADR pages
just model-check   # fails if a page is stale, missing or an orphan, a View has no image, or a
                   # rule is broken
just model         # only if a view changed or a new view needs its image; commit
                   # docs/architecture/views/ afterwards
```

Commit `model.xml` and the generated pages together; the PR names the element id and the page.
