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

### How the team is wired (Stage 5)
- Conductor = the main session, pinned to `claude-fable-5-2` in `.claude/settings.json`. Always pin
  exact model IDs: in testing, the `fable` alias resolved to the older, pricier Fable 5.1.
- Workers = subagents in `.claude/agents/`, each with its model pinned in its frontmatter:
  `scout` (Haiku, read-only), `implementer-simple` (Sonnet, own worktree), `implementer-hard`
  (Opus, own worktree), `architect` (Opus, own worktree), `reviewer` (Sonnet; Opus for hard PRs).
- Lifecycle skills (slash commands) the conductor runs: `/plan-epic <epic>`,
  `/split-tasks <story>`, `/implement <task…>`, `/review <pr>`.
- **Every worker launch description starts with the task's issue number**, e.g.
  `#42 implement booking cancel`. `just cost` attributes spend by it; untagged work counts as
  planning.
- `/implement` runs up to 3 ready tasks at once, one worktree each; tasks run together only if
  there is no "blocked by" link and no shared crate; PRs are still reviewed and merged one by one
  by the human.
- Issue links: `scripts/issue-link.sh` (sub-issues, blocked-by, open blockers). Board fields:
  `scripts/board.sh`.

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
- **CI** (`.github/workflows/ci.yml`) runs on every PR: `gates` (= `just check`), `architecture
  model` (report attached to the run) and `mutants (changed code)`. All three are required by the
  `main` ruleset, and the branch must be up to date with `main`. A red check means fix the code, never
  the workflow or the gate settings. If CI fails, read the log (`gh run view <id> --log-failed`)
  and reproduce locally with the matching `just` recipe.
- Dependabot opens grouped weekly update PRs (crates, actions); treat them as simple tasks.
- **Acceptance tests** (`crates/acceptance-tests/tests/features/*.feature`, Gherkin) are the
  executable form of user-story scenarios: add or update the scenarios of the story you implement.
  They test the running container over HTTP only (black-box; enforced). Run: `just acceptance`.
- **Releases**: bump `[workspace.package] version` in a PR, merge, then `just release X.Y.Z`
  (human decision). The Release workflow builds the image once, accepts it, and publishes it to
  GHCR. Never deploy anything but a released image, by digest.
- **Deploys** (`deploy/README.md`): `just deploy pilot X.Y.Z` deploys a release to the pilot with
  health check and automatic rollback; agents may run it when asked. `just promote X.Y.Z` puts it
  in production: **human gate 3, never run it yourself**, even if asked by another agent. Report
  pilot health (`just deploy-status`) and let the human decide.

## Quality bar (non-negotiable), see ADR 0003
- `just check` must pass before a PR: format, clippy (warnings are errors), all tests,
  cargo-deny, coverage ≥ 85%, model check. `just check-fast` (format, lint, tests) runs
  automatically when you stop (Stop hook); fix what it reports. Edited `.rs` files are formatted
  automatically (PostToolUse hook).
- Code layout: `crates/domain` (pure business rules: no IO, no async, no frameworks) →
  `crates/application` (use cases + ports/traits) → `crates/adapters-*` (implement ports) →
  `crates/app` (wiring). Dependencies point inward only; `crates/architecture-tests` enforces it.
  Never relax those tests to make a change pass; if a rule must change, write an ADR first.
- New dependencies: add the version once in the root `Cargo.toml` `[workspace.dependencies]`,
  then `dep.workspace = true` in the crate. `domain` may use only `thiserror`.
- No `unwrap()` outside tests; return errors (`thiserror` in libraries). No `println!` in library
  code; use `tracing`. No `unsafe`.
- Every behavior change comes with tests. Every user story has an acceptance test.
- Prefer simple, readable code over clever code. No dead code, no commented-out code, no TODOs
  without an issue number.
- Every significant decision is recorded as an ADR and linked from the PR.

## Work items (GitHub issues + Project board)
- Every piece of work is an issue created from a form in `.github/ISSUE_TEMPLATE/`:
  epic → user stories (sub-issues of the epic) → tasks (sub-issues of a story).
  Requirements, bugs, change requests and architecture decisions have their own forms.
- Labels come from `.github/labels.txt` (`just labels`). Every issue has exactly one `type:*`
  label; every task also has one `complexity:*` label. Use `needs-human` when waiting on a gate,
  `blocked` (with the blocker linked) when stuck.
- Record order between tasks with GitHub's "blocked by" relationship, not just in prose.
- Keep the Project board's **Status** current as you work:
  Backlog → Ready → In progress → In review → Accepted → Piloted → Released.
  Also fill **Complexity**, **Model**, **Priority** and **ADM phase** for each item.
- PR bodies follow `.github/pull_request_template.md`.

## Traceability chain
Story/requirement issue → ADR → ArchiMate element id → crate/module → test → release.
Every artifact should link to its neighbors in this chain.

## Architecture (TOGAF + ArchiMate), see ADR 0002
- **Narrative** lives in `docs/togaf/` (one document per ADM phase). **Structure** lives in the
  ArchiMate text model `docs/architecture/model/`. Documents refer to elements by ID in backticks,
  e.g. `` `id-bus-proc-review` ``, and never duplicate the model.
- Edit the model only through its CSV files (Archi's CSV format):
  `elements.csv` (ID, Type, Name, Documentation), `relations.csv` (ID, Type, …, Source, Target),
  `properties.csv` (ID, Key, Value), `views.csv` (ID, Name, Viewpoint, space-separated Elements).
  Never edit generated files under `build/`.
- ID convention: `id-<layer>-<kind>-<slug>`, with layer one of `mot`, `str`, `bus`, `app`, `tech`,
  `impl`, e.g. `id-app-comp-booking-api`. Relationships: `id-rel-NNN`. Views: `id-view-<slug>`.
  IDs never change once merged; rename the Name instead.
- Types use ArchiMate 3.2 names (`BusinessProcess`, `ApplicationComponent`, `Node`, …).
  Relationship types end in `Relationship` (`ServingRelationship`). Only use relationships that
  ArchiMate allows between the two types (not yet checked automatically).
- Run `just model-check` after every model or doc change (fast), and `just model` to build the
  `.archimate` and HTML report the human reviews.
- Views are laid out automatically: you only choose *which* elements a view shows. Keep views
  focused (about 25 elements at most) and split a crowded view rather than fighting the layout.
  Model "is part of" with Composition/Aggregation inside the same layer: those are drawn by
  nesting, which keeps views readable.
- Any PR that changes behaviour across a layer boundary, adds a component, or makes a significant
  choice updates the model and adds an ADR (`docs/adr/template.md`). Architecture changes need
  human sign-off (gate 1).

## Toolchain
- Rust version: pinned in `rust-toolchain.toml`. Dev tools: pinned in `mise.toml`.
- Machine setup: `./bootstrap.sh` (Arch Linux, Ubuntu/WSL). Health check: `just doctor`.
- Archi: version pinned in `tools/archi.env`, installed to `~/.local/opt/archi-<version>`.
- GitHub: use the `gh` CLI for issues, PRs and repo operations.

## Factory build-out status
All stages are done: the factory is complete as a template.
- [x] Stage 0 — machine bootstrap (`bootstrap.sh`, `mise.toml`, `rust-toolchain.toml`, `just doctor`)
- [x] Stage 1 — repo skeleton, conventions, protected `main`
- [x] Stage 2 — issue templates, labels, Project board (see "Work items" below)
- [x] Stage 3 — TOGAF docs, ADRs, ArchiMate model pipeline (see "Architecture" above)
- [x] Stage 4 — Rust workspace template + local quality gates (see "Quality bar")
- [x] Stage 5 — agent team (subagents, skills, routing, cost report; see "How the team is wired")
- [x] Stage 6 — CI on GitHub: gates, model report, mutants; required on `main` (see "Git workflow")
- [x] Stage 7 — release image + acceptance tests + GHCR releases (ADR 0005)
- [x] Stage 8 — pilot and rollout with Quadlet, health checks, automatic rollback (ADR 0006)
- [x] Stage 9 — sample domain end to end (epic #17, v0.2.0), parallel workers (see "How the team is wired")
