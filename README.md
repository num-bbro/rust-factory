# rust-factory

A software-factory template for Rust: an AI **conductor** plans and designs, then hands each
task to a **worker** agent. The work goes through GitHub issues, pull requests, CI, acceptance,
and pilot and production deploys. The business and architecture are documented with TOGAF and
ArchiMate.

> Status: under construction, built stage by stage. See "Factory build-out status" in
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
| `docs/togaf/` | One document per TOGAF ADM phase (narrative) |
| `docs/architecture/model/` | ArchiMate model as text (CSV), built with `just model` |
| `docs/adr/` | Architecture Decision Records |
| `scripts/archimate/` | Model builder: CSV → Open Exchange XML → Archi model + HTML report |
| `tools/archi.env` | Pinned Archi version and checksum |

## Working on code

```bash
just run            # start the example service on :8080
just check-fast     # format, lint, tests: the quick loop
just check          # every gate CI runs: + dependencies, coverage, model
just coverage-html  # browsable coverage report
just mutants -p domain   # mutation testing: do the tests catch real bugs?
```

## Architecture model

```bash
just model-check    # fast: validate the model and the element IDs mentioned in docs
just model          # build build/architecture/model.archimate and report/index.html
just model-report   # build, then open the HTML report in the browser
```
Open `build/architecture/model.archimate` in Archi to review. To change the model, edit the CSV
files, not the generated `.archimate`. See [ADR 0002](docs/adr/0002-archimate-model-as-text.md).
