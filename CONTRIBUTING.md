# Contributing

These conventions apply to humans and agents alike. `CLAUDE.md` holds the agent-specific rules.

## Branching: trunk-based
- `main` is the trunk. It must always build, pass all checks and be releasable.
- `main` is protected: no direct pushes, no force-pushes, no deletion. Every change arrives via a
  pull request and is **squash-merged**, so `main` has one commit per PR (linear history).
- Short-lived branches, one per issue, named `<type>/<issue-number>-<short-slug>`:

  | Type | Use for |
  |---|---|
  | `feat` | new behavior for users |
  | `fix` | bug fix |
  | `docs` | documentation, ADRs, architecture model |
  | `test` | tests only |
  | `refactor` | restructuring without behavior change |
  | `chore` / `build` / `ci` | tooling, dependencies, pipelines |

  Example: `feat/42-booking-cancel`. Delete the branch after merge (GitHub does this automatically).

## Commit messages: Conventional Commits
```
<type>[optional scope][!]: <summary in imperative mood> (#<issue>)

[optional body: why, not what]

[optional footer: BREAKING CHANGE: ..., Refs: #12]
```
Examples:
- `feat(booking): allow cancelling a reservation (#42)`
- `fix(api): return 404 for unknown booking id (#57)`
- `refactor(domain)!: rename Slot to TimeSlot (#61)`

Why: the history becomes readable, and release notes and version bumps can be generated from it.

## Pull requests
- One task per PR, small enough to review in about 15 minutes.
- The title is a Conventional Commit line (it becomes the squash commit message).
- The body links the issue (`Closes #42`), the ADR / ArchiMate elements affected, test evidence,
  and the model of the agent that wrote it.
- All checks must pass before merge. A human approves the merge into `main`.

## Versioning
Semantic Versioning (`MAJOR.MINOR.PATCH`), with release tags `vX.Y.Z` on `main`.

## Line endings
All text files use LF (enforced by `.gitattributes`), so Arch, WSL and Windows editors agree.
On WSL, keep clones inside the Linux filesystem (`~/...`), not under `/mnt/c`.
