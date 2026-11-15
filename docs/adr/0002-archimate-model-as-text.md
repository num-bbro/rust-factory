# 0002. ArchiMate model as text, built into Archi in CI

- Status: Accepted
- Date: 2026-11-15
- Issue: #3
- Deciders: product owner, conductor
- ArchiMate elements: id-mot-req-togaf, id-tech-sw-archi

## Context and problem
The architecture must be documented in ArchiMate (requirement `id-mot-req-togaf`). Agents write
the changes and the product owner reviews them in Archi. Archi's native `.archimate` file is a
large XML document with layout coordinates, which is hard for agents to edit and hard to review
as a diff.

## Decision drivers
- Agents can edit the model reliably, with small diffs reviewable in a PR.
- The product owner can open the result in Archi, the tool they already use.
- Builds work without a person present (CI).
- Thai text must work.

## Options considered
1. **Text source in Archi's CSV format + generated views**, built by Archi's command line.
2. **Agents edit `.archimate` directly**: one huge XML file with coordinates; error-prone, noisy diffs.
3. **coArchi (git plugin) with both humans and agents editing**: merge conflicts in model XML; agents can't use the GUI.
4. **jArchi scripts generate the model**: needs an extra plugin and JavaScript.

## Decision
Chosen: **option 1**.
- Source: `docs/architecture/model/{elements,relations,properties}.csv` in Archi's own CSV
  format, plus `views.csv` listing which elements appear on each view.
- `scripts/archimate/build_exchange.py` validates the model (unique IDs, valid types, existing
  ends) and writes Open Group **Exchange XML**, with diagrams laid out automatically in one band
  per ArchiMate layer.
- Archi's command line validates that XML against the Open Group schema and produces
  `model.archimate` plus an HTML report (`just model`).

## Consequences
- Good: small, readable diffs; agents edit CSV rows; Archi stays the review tool; tool-neutral
  Exchange XML is a by-product.
- Good: elements/relations round-trip with Archi's File › Export › CSV if the owner wants to
  model in the GUI and hand the result back.
- Diagram layout is automatic (`scripts/archimate/layout.py`), following hand-drawing
  conventions: one band per layer, one row per aspect (active structure / behaviour / passive),
  composition and aggregation inside a layer shown by nesting, elements ordered so related ones
  line up, triggering/flow chains kept left to right, lines routed at right angles around boxes.
- Bad: hand-tuned layouts made in Archi are not preserved, and very dense views can still have
  long detours. If a presentation-quality view is needed, a later ADR can add optional fixed
  coordinates per view.
- Bad: ArchiMate relationship-validity rules (which relationships are allowed between which
  types) are not checked yet; Archi's importer checks only the XML schema.
- Follow-up: CI needs a virtual display (Xvfb). Archi's command line exits with
  "Cannot open display" without one.

## Spike results (2026-11-15, Archi 5.11.0 on Arch Linux)
| Test | Result |
|---|---|
| Exchange XML import → `.archimate` → HTML report, with a display | works, view images rendered |
| Thai names and documentation | stored and rendered correctly |
| Same run with no display | fails: `Cannot open display` → needs `xvfb-run` |
| Archi CSV import of our `elements.csv` into a loaded model | works: our files are in Archi's CSV format |
| CSV import into `--createEmptyModel` | hung until killed after 3 min; not investigated, not needed |
| Diagrams | Archi's CSV format has no diagram data → views must come from Exchange XML |

## Amendment 2026-11-15: relationship validity is checked
Issue: #27 (bug) / task #39. This supersedes the "Bad" bullet above that says relationship
validity is not checked.

- **The check.** `just model-check` (and so `just check` and the CI `gates` job) now runs
  `scripts/archimate/check_relationships.py`. For every row of `relations.csv` it reports, with
  the relationship ID, an unknown source or target, an unknown relationship type, and a type that
  ArchiMate does not allow between the two element types (listing the types that are allowed).
  The rules are read from `relationships.xml` of the pinned Archi install, not copied into the
  repo: they are Archi's own copy of the ArchiMate 3.2 specification, they move together with the
  pinned version in `tools/archi.env`, and a copy would be a second source of truth that could
  drift. If the install is missing the check fails and points to `./bootstrap.sh`; it never
  passes silently.
- **Agents and roles.** The check found `id-rel-030`..`032`: Assignment from an
  `ApplicationComponent` to a `BusinessRole`, which ArchiMate does not allow (only Flow,
  Association, Triggering, Serving). They are now `ServingRelationship`, with documentation that
  the agent performs the work of the role. Alternatives rejected: *Association* is always valid
  but says nothing about the direction or meaning of the link; *an extra `BusinessActor` per
  agent* (actor assigned to role, component realizing the actor) adds three elements and three
  relationships for no new information and crowds the views.
- Also considered: *Realization* from the agent component to the business process it carries out
  (allowed by the rules, e.g. the workers realizing `id-bus-proc-implement`). Not chosen here
  because bug #27 is about the agent-to-role links and those IDs must keep their ends; it can be
  added later as additional relationships, not as a replacement.
