# Preliminary

**Purpose:** Set up how architecture work is done: principles, governance, tools.

## Outputs
- Architecture principles (see Motivation view: `id-mot-pr-pr-only`)
- Who approves what (human gates in `CLAUDE.md`)
- Tools and repositories (`bootstrap.sh`, GitHub, Archi)

## Content
Principles for this factory:

1. **Every change through a reviewed PR** (`id-mot-pr-pr-only`): `main` is protected.
2. **Architecture as code**: the ArchiMate model and these documents live in git and change through PRs.
3. **Decisions are recorded**: every significant decision gets an ADR in `docs/adr/`.
4. **Right model for the job**: work is routed to AI models by difficulty (`id-mot-req-routing`).
5. **Business logic stays pure**: domain code has no IO, so business rules can change safely.

## Open questions
- _none yet_
