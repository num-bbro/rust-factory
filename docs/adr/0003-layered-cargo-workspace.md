<!-- Generated from docs/architecture/model.xml (id-mot-adr-0003) by `just model-docs`. Do not edit: change the model, see docs/adr/template.md. -->
# 0003. Layered Cargo workspace with enforced dependency direction

- Status: Accepted
- Date: 2026-11-15
- Issue: #5
- Deciders: product owner, conductor
- ArchiMate elements: `id-app-comp-reservation-svc`, `id-mot-goal-healthy`, `id-tech-sw-rust`
- Released in: vv0.1.0

## Context and problem
The product owner's experience: in long-lived projects, business logic mixed with database and HTTP
code made every change ripple everywhere, weak tests made people afraid to change code, and nobody
remembered why things were built as they were. AI workers write code fast, so structure decays fast
unless something enforces it automatically.

## Decision drivers
- Business rules must be changeable without touching infrastructure (and vice versa).
- Violations must fail the build, not rely on reviewers noticing.
- The same structure in every project made from this template.
- Simple enough for a worker agent to follow from `CLAUDE.md` alone.

## Options considered
1. **Layered ("hexagonal") Cargo workspace, one crate per layer, with an architecture test.**
2. **Single crate with modules per layer**: Rust's module privacy can't stop `domain` from importing
   `axum`; the rule lives only in reviews.
3. **No prescribed structure**: fastest start, the decay we have seen before.

## Decision
Chosen: **option 1**.
- Crates: `domain` (pure business rules: no IO, no async, no frameworks) → `application` (use cases
  and the ports/traits they need) → `adapters-db`, `adapters-http` (implement ports) → `app`
  (binary: wiring, config, server).
- `crates/architecture-tests` reads `cargo metadata` and fails if a dependency points outward, an
  adapter depends on another adapter, the domain uses any external crate except `thiserror`, or
  `domain`/`application` depend on infrastructure crates. A new crate must be given a layer.
- The workspace sits at the **repo root** (not in a `template/` folder): the whole repository is the
  template, so CI, hooks and docs use the same paths in every project.

## Consequences
- Good: a business-rule change is a `domain` change plus its tests; adapters can be swapped.
- Good: the layering is proven, not promised: a deliberately added `domain → tokio` and `adapters-db
  → adapters-http` both failed the architecture tests with clear messages.
- Bad: more crates and some boilerplate (ports and test doubles) for small features.
- Follow-up: projects decide their database in an ADR; it goes in `adapters-db`.

## Quality gates that go with it (`just check`)
| Gate | Tool | Fails when |
|---|---|---|
| Format | rustfmt | any file not formatted |
| Lint | clippy (workspace lints, pedantic + `unwrap_used` and others) | any warning |
| Tests | cargo-nextest | any test fails (unit, property, HTTP, architecture) |
| Dependencies | cargo-deny | known vulnerability, disallowed license, unknown source |
| Coverage | cargo-llvm-cov | lines covered < 85% (excluding `app/src/main.rs`) |
| Model | `scripts/archimate` | ArchiMate model or doc references broken |

Mutation testing (`just mutants`, `just mutants-diff`) is available on demand; CI runs it on changed
code (Stage 6). It earned its place on day one: with 95% line coverage, 8 of 25 mutants in `domain`
still survived, including `<` → `<=` in `TimeSlot::overlaps`, which would have rejected back-to-back
bookings without any test failing. After adding the missing tests, all 22 viable mutants are caught.
