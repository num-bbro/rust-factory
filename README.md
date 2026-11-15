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
| `bootstrap.sh` | Machine setup: OS packages → Rust → dev tools → shell hook |
| `rust-toolchain.toml` | Pinned Rust version |
| `mise.toml` | Pinned dev tool versions |
| `justfile` | Task runner: `just` lists the recipes |
| `CLAUDE.md` | Rules every agent follows: roles, model routing, gates, quality bar |
| `CONTRIBUTING.md` | Branching, commit and PR conventions |
