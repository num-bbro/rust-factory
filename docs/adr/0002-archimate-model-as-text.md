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
- Bad: diagram layout is automatic and simple (straight lines can cross). Hand-tuned layouts
  made in Archi are not preserved. If a presentation-quality view is needed, a later ADR can add
  optional coordinates.
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
