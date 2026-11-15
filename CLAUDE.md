# Rust Software Factory — rules for every agent

This repo is a **software factory template**: the tooling, rules and agent setup used to
take a business need all the way to a production rollout, in Rust, with the architecture
documented in TOGAF / ArchiMate. Read this file fully before doing any work here.

## Roles

| Role | Model | Does | Never does |
|---|---|---|---|
| **Conductor** (main session) | `claude-fable-5-2` | Plans, designs architecture, sets strategy, splits work into tasks, routes each task to a worker, checks results | Bulk file reading or routine coding itself — it delegates |
| **Hard worker** | `claude-opus-5-5` | Ambiguous or cross-crate tasks, domain modeling, tricky bugs, architecture review | Starts work without a task issue |
| **Simple worker** | `claude-sonnet-5-5` | Clear, well-specified tasks: one module, tests to spec, adapters, docs, small-diff review | Makes design decisions — it asks the conductor instead |
| **Scout** | `claude-haiku-5-5` | File/code search, log reading, gathering context; returns a short summary | Edits files |

### Routing rule (cost control)
Every task issue carries `complexity:simple` or `complexity:hard` plus a one-line reason.
A task is **simple only if all three hold**: clear acceptance criteria, touches one crate,
needs no new design decision. Everything else is **hard**.
**Escalation:** if a simple worker fails the quality gates twice on the same task, the conductor
reassigns it to the hard worker and comments the reason on the issue.

## Human gates — stop and ask the human
1. Architecture / plan sign-off (vision, ArchiMate model changes, new ADRs).
2. Merging a PR into `main`.
3. Promoting a release from pilot to production rollout.
Also always ask before: deleting data, changing repo settings, anything that costs money,
anything that needs a password or secret.

## Git workflow (trunk-based)
- `main` is always releasable and is protected: changes land **only through PRs**, squash-merged.
- One branch per issue: `<type>/<issue-number>-<short-slug>`, e.g. `feat/42-booking-cancel`.
- Each worker works in its **own git worktree**, never directly on `main`.
- Commits follow **Conventional Commits**: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`,
  `chore:`, `ci:`, `build:`, `perf:`; add `!` for breaking changes. Reference the issue: `(#42)`.
- Keep PRs small: one task, one PR. The PR body links the issue (`Closes #42`) and states the
  worker model used.
- Never force-push to `main`, never commit secrets, never commit build output (`target/`).

## Quality bar (non-negotiable)
- Code must pass: `cargo fmt --check`, `cargo clippy -- -D warnings`, all tests.
- Business rules live in a pure domain layer with no IO; adapters depend on the domain, never
  the reverse.
- Every behavior change comes with tests. Every user story has an acceptance test.
- Prefer simple, readable code over clever code. No dead code, no commented-out code, no TODOs
  without an issue number.
- Every significant decision is recorded as an ADR and linked from the PR.

## Traceability chain
Story/requirement issue → ADR → ArchiMate element id → crate/module → test → release.
Every artifact should link to its neighbors in this chain.

## Toolchain
- Rust version: pinned in `rust-toolchain.toml`. Dev tools: pinned in `mise.toml`.
- Machine setup: `./bootstrap.sh` (Arch Linux, Ubuntu/WSL). Health check: `just doctor`.
- GitHub: use the `gh` CLI for issues, PRs and repo operations.

## Factory build-out status
The factory is being built stage by stage. Only rely on what is marked done.
- [x] Stage 0 — machine bootstrap (`bootstrap.sh`, `mise.toml`, `rust-toolchain.toml`, `just doctor`)
- [x] Stage 1 — repo skeleton, conventions, protected `main`
- [ ] Stage 2 — issue templates, labels, Project board
- [ ] Stage 3 — TOGAF docs, ADRs, ArchiMate model pipeline
- [ ] Stage 4 — Rust workspace template + local quality gates
- [ ] Stage 5 — agent team (subagents, skills, routing, cost report)
- [ ] Stage 6 — CI/CD pipelines
- [ ] Stage 7 — acceptance builds
- [ ] Stage 8 — pilot and rollout deploys
- [ ] Stage 9 — sample domain end to end, parallel workers
