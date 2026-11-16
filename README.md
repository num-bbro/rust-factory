# rust-factory

A software-factory template for Rust: an AI **conductor** plans and designs, then hands each
task to a **worker** agent. The work goes through GitHub issues, pull requests, CI, acceptance,
and pilot and production deploys. The business and architecture are documented with TOGAF and
ArchiMate.

[![CI](https://github.com/num-bbro/rust-factory/actions/workflows/ci.yml/badge.svg)](https://github.com/num-bbro/rust-factory/actions/workflows/ci.yml)

> Status: all build-out stages are done; the factory is complete as a template. See "Factory build-out status" in
> [CLAUDE.md](CLAUDE.md).

## Quick start (Arch Linux or Ubuntu on WSL)

```bash
git clone git@github.com:num-bbro/rust-factory.git ~/dev/rust-factory
cd ~/dev/rust-factory
./bootstrap.sh --dry-run   # see what it would change
./bootstrap.sh             # install what's missing (safe to re-run)
exec bash                  # reload the shell so mise is active
just doctor                # every line should show ✔
gh auth login              # once per machine
```

To start a new project from this template, see [docs/new-project.md](docs/new-project.md).

## Layout

| Path | Purpose |
|---|---|
| `bootstrap.sh` | Machine setup: OS packages → Rust → dev tools → Archi → shell hook |
| `rust-toolchain.toml` | Pinned Rust version |
| `mise.toml` | Pinned dev tool versions |
| `justfile` | Task runner: `just` lists the recipes |
| `CLAUDE.md` | Rules every agent follows: roles, model routing, gates, quality bar |
| `CONTRIBUTING.md` | Branching, commit and PR conventions |
| `.github/ISSUE_TEMPLATE/` | Forms for epic, user story, requirement, task, bug, change request, architecture decision |
| `.github/labels.txt` | Label set (`just labels`) |
| `.github/pull_request_template.md` | PR checklist: issue, ADR / ArchiMate links, tests, worker model |
| `scripts/setup-project.sh` | Creates the Project board with lifecycle columns (`just project`) |
| `Cargo.toml`, `crates/` | Layered Rust workspace: domain → application → adapters → app ([ADR 0003](docs/adr/0003-layered-cargo-workspace.md)) |
| `deny.toml`, `clippy.toml`, `rustfmt.toml`, `.config/nextest.toml` | Quality-gate configuration |
| `.claude/` | Claude Code hooks: format on edit, quick gate before an agent stops |
| `scripts/board.sh` | Put an issue/PR on the Project board and set its fields |
| `.claude/agents/` | Worker agents with pinned models: scout (Haiku), implementers (Sonnet / Opus), architect, reviewer |
| `.claude/skills/` | Conductor workflows: `/plan-epic`, `/split-tasks`, `/implement`, `/review` |
| `.github/workflows/ci.yml`, `.github/actions/setup/` | CI: same gates as `just check`, on every PR and on `main`; machines set up by `bootstrap.sh` |
| `Dockerfile` | Release image: 31 MB, non-root, health check ([ADR 0005](docs/adr/0005-release-image-and-acceptance.md)) |
| `crates/acceptance-tests/` | Gherkin acceptance tests run against the real container (`just acceptance`) |
| `docs/api/` | `openapi.yaml`, the hand-written OpenAPI contract of the HTTP API, and the Schemathesis config; checked against the running container by `just acceptance` ([ADR 0010](docs/adr/0010-openapi-specification-spec-first.md)) |
| `.github/workflows/release.yml` | Tag `vX.Y.Z` → build once → acceptance → GHCR + GitHub Release (`just release X.Y.Z`) |
| `deploy/` | Hosts per environment, Quadlet unit; `just deploy`, `just promote`, `just deploy-status` ([guide](deploy/README.md)) |
| `.github/dependabot.yml` | Weekly grouped dependency update PRs |
| `scripts/issue-link.sh` | Sub-issues and "blocked by" links between issues |
| `scripts/cost-report.py`, `tools/model-prices.toml` | `just cost`: agent spend per model, agent and task |
| `docs/togaf/` | One document per TOGAF ADM phase, with its diagrams and catalogs, generated from the model (`just model-docs`); [template.md](docs/togaf/template.md) says how to add or change one |
| `docs/architecture/model.xml` | ArchiMate model (Open Group exchange format), the single source of the architecture: elements, views, TOGAF documents, ADRs; built with `just model` |
| `docs/architecture/views/` | Archi's image of every view and `views.lock`, written by `just model` (never edit them) |
| `docs/adr/` | Architecture Decision Records, generated from the model (`just model-docs`); [template.md](docs/adr/template.md) says how to add one |
| `scripts/archimate/` | Model formatter, checks and builder: exchange XML → Archi model + HTML report |
| `tools/archi.env` | Pinned Archi version and checksum |

## Working on code

```bash
just run            # start the example service on :8080
just check-fast     # format, lint, tests: the quick loop
just check          # every gate CI runs: + dependencies, coverage, model
just coverage-html  # browsable coverage report
just mutants -p domain   # mutation testing: do the tests catch real bugs?
just acceptance     # build the release image, run Gherkin scenarios against it
```

## The agent team

Open Claude Code in this folder: the main session is the **conductor** (Fable). Typical flow:

```text
/plan-epic 12        epic → user stories (you approve the plan first)
/split-tasks 13      story → tasks, each routed simple (Sonnet) or hard (Opus)
/implement 14 15     each task → its worker → branch + PR (escalates Sonnet → Opus on 2 failed gates)
/review 16           reviewer agent checks the PR; you merge
just cost            what it cost, per model and per task
```

## Architecture model

```bash
just model-fmt      # sort, lay out the views and normalise docs/architecture/model.xml
just model-check    # fast: validate the model, the element IDs mentioned in docs, the ADR and
                    # TOGAF pages, the view images against views.lock
just model-docs     # write the ADR and TOGAF pages docs/adr/*.md, docs/togaf/*.md from the model
                    # (never edit them)
just model          # build build/architecture/model.archimate and report/index.html (Archi,
                    # under Xvfb); update docs/architecture/views/ for the views that changed
just model-dims     # compare the last build's image sizes with views.lock (CI runs it)
just model-report   # build, then open the HTML report in the browser
```
Open `build/architecture/model.archimate` in Archi to review. To change the model, edit
`docs/architecture/model.xml` and run `just model-fmt`, never the generated `.archimate`. When
`just model-check` reports a view image, run `just model` and commit `docs/architecture/views/`. See
[ADR 0009](docs/adr/0009-archimate-exchange-model-as-source.md).

## Architecture site

The architecture documents (TOGAF and ADRs), the diagrams and the clickable HTML report of the model
are published at <https://num-bbro.github.io/rust-factory/>, rebuilt on every merge to `main` by
`.github/workflows/pages.yml`. The model file is there too, for download. The site's base URL is the
`Site` property of the model. A "Clickable version" link under a diagram opens the
report's page for that diagram; the full report with its navigation is at `report/index.html`.
