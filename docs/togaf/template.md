# How to add or change a TOGAF document

TOGAF documents live in the model (ADR 0009): each one is a `Deliverable` element in
`docs/architecture/model.xml`, and its page `docs/togaf/<name>.md` (and the index
`docs/togaf/README.md`) are generated from it. Never edit a generated page; this guide is the one
hand-written file in `docs/togaf/`.

## 1. Write the narrative
The document's narrative is the element's `documentation`: Markdown, starting after the title
(the title is the element's name). Write **each paragraph and each list item on one line**, as for
ADRs (ADR 0009, line breaks: option A, and the Markdown subset of `docs/adr/template.md`); the
page wraps them at 100 characters. Refer to model elements, views, ADRs and other documents by ID
in single backticks (`` `id-bus-proc-review` ``) and never repeat the model: the page makes each
such ID a link to its catalog row, view section or page (an ID nothing on a page shows stays plain
code; IDs in code blocks, in longer code spans or in a link's text are never linked), and
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
formatter sorts the elements, so add a new one anywhere inside `<elements>`. A `Deliverable` is a
TOGAF document when it has a `File` property; one without `File` is an ordinary element, which the
page generator leaves alone. A document's properties:

- `File`: the generated page, `docs/togaf/<name>.md` (letters, digits and hyphens; existing file
  names never change);
- `Phase`: the ADM phase, one of `Preliminary`, `A`–`H`, `Requirements Management` (checked; the
  index shows the phase's name);
- `Viewpoints` (optional, Markdown, one line): the ArchiMate viewpoints suggested for the phase,
  shown in the index;
- `Artifacts` (optional, Markdown, one line): the factory artifacts of the phase, shown in the
  index;
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
    <property propertyDefinitionRef="propid-viewpoints"><value xml:lang="en">Project</value></property>
    <property propertyDefinitionRef="propid-artifacts"><value xml:lang="en">Milestones, task split</value></property>
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

## Recording a release
After `just release X.Y.Z`, a task adds the release to the model as a `Plateau` (ADR 0009): the
catalogs then show which release delivered each element, and the Releases view
(`id-view-releases`) shows the releases. Add the element, one link to each element the release
delivered, and a Triggering from the previous release; nothing else changes:

```xml
<element identifier="id-impl-plat-v0-2-1" xsi:type="Plateau">
  <name xml:lang="en">Release v0.2.1</name>
  <documentation xml:lang="en">Schedule changes are atomic (bug #26).</documentation>
  <properties>
    <property propertyDefinitionRef="propid-date">
      <value xml:lang="en">2026-11-15</value>
    </property>
    <property propertyDefinitionRef="propid-tag">
      <value xml:lang="en">v0.2.1</value>
    </property>
  </properties>
</element>
<relationship identifier="id-rel-NNN" xsi:type="Aggregation" source="id-impl-plat-v0-2-1" target="id-app-comp-db"/>
<relationship identifier="id-rel-NNN" xsi:type="Triggering" source="id-impl-plat-v0-2-0" target="id-impl-plat-v0-2-1"/>
```

- The identifier is `id-impl-plat-vX-Y-Z`, the name `Release vX.Y.Z`, `Date` the release date and
  `Tag` the git tag. Elements are shown in version order, so `v0-10-0` comes after `v0-2-1`.
- Use an **Aggregation** from the Plateau to each element (`just model-check` says which pairs
  ArchiMate allows; for a pair it does not allow, use an undirected Association). A catalog's
  Release column lists each Plateau once per element, and an ADR page's "Released in" line lists
  the tags of the Plateaus linked to the ADR.
- The Releases view (`id-view-releases`) is hand-arranged (`Layout = manual`): add the new Plateau's
  box to the right of the last one, a box for each ADR it delivers above it, and one connection
  per link, copying the existing nodes; the other elements a release delivers show in the
  catalogs' Release column and are not drawn. Then run `just model-fmt`, `just model-docs`,
  `just model-check` and `just model`, and commit the new image and its `views.lock` entry.
