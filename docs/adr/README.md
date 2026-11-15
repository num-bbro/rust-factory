# Architecture Decision Records

An ADR records **one significant decision**: the context, the options considered, what was
chosen and why. ADRs are never edited after acceptance. To change a decision, write a new ADR
that supersedes the old one, and set the old one's status to `Superseded by NNNN`.

- Format: [MADR](https://adr.github.io/madr/), see [template.md](template.md).
- File name: `NNNN-short-title.md`, numbered in order.
- Status: `Proposed` (in an open PR) → `Accepted` (PR merged) → `Superseded by NNNN` / `Deprecated`.
- Every ADR links its issue and the ArchiMate element IDs it affects. Elements link back with an
  `ADR` property in `docs/architecture/model/properties.csv`.

| # | Decision | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions as ADRs | Accepted |
| [0002](0002-archimate-model-as-text.md) | ArchiMate model as text, built into Archi in CI | Accepted |
| [0003](0003-layered-cargo-workspace.md) | Layered Cargo workspace with enforced dependency direction | Accepted |
| [0004](0004-agent-team-and-cost-routing.md) | Agent team with cost-aware model routing | Accepted |
