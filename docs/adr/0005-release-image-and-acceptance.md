# 0005. Release image built once, accepted, then promoted unchanged

- Status: Accepted
- Date: 2026-11-15
- Issue: #12
- Deciders: product owner, conductor
- ArchiMate elements: id-bus-proc-accept, id-tech-svc-ghcr, id-tech-sw-podman

## Context and problem
Unit and HTTP tests prove the code; they do not prove the thing we deploy: the binary's startup,
configuration, packaging and runtime behaviour. Pilot and production must run exactly what
was tested, not a rebuild of it.

## Decision drivers
- What is accepted is what is deployed, byte for byte.
- Acceptance criteria readable by the business (the user-story form already uses Gherkin).
- Small, low-attack-surface runtime; runs as non-root; works with Podman on the VMs.

## Decision
- **Image**: multi-stage `Dockerfile`. Rust 1.99 builder, runtime `distroless/cc-debian13:nonroot`
  (no shell, no package manager, uid 65532), both pinned by digest; Dependabot updates them.
  Built in Docker format so the `HEALTHCHECK` (`/app healthcheck`, a std-only probe built into the
  binary) is kept. About 31 MB.
- **Acceptance tests**: `crates/acceptance-tests`, Gherkin features run with cucumber over HTTP
  against a running container. Black-box by rule: the architecture tests forbid any dependency on
  workspace crates. `just acceptance` also checks the container health check and graceful shutdown
  on SIGTERM. Without `ACCEPTANCE_BASE_URL` the suite skips (so plain `cargo test` and mutation
  testing work); with `ACCEPTANCE_REQUIRED` set, as in CI, a missing service fails.
- **CI**: an `acceptance` job on every PR, required on `main`.
- **Release**: `just release X.Y.Z` tags a clean, current `main` whose `Cargo.toml` version
  matches. The Release workflow builds the image once, runs the acceptance tests against that
  image, pushes it to `ghcr.io/<owner>/<repo>` as `X.Y.Z` and `sha-<commit>`, and creates a GitHub
  Release with generated notes and the image digest. Deploy by digest.

## Consequences
- Good: `main.rs` (excluded from unit coverage and mutation testing) is exercised end to end:
  `PORT`, the health-check mode, graceful shutdown.
- Good: one artifact flows from acceptance to pilot to production (Stage 8).
- Bad: scenarios share one running service with in-memory state, so each scenario uses its own
  hours of the day. A project with a real database would reset state per scenario instead.
- Bad: no `latest` tag on purpose: deployments must name a version or digest.
