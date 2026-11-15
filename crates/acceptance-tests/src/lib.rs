//! Black-box acceptance tests. Nothing to call here: see `tests/acceptance.rs` (the steps) and
//! `tests/features/*.feature` (the specification, in Gherkin).
//!
//! The tests talk HTTP to a running service at `ACCEPTANCE_BASE_URL` and know nothing about the
//! code. `just acceptance` builds the release image, starts it, runs them and stops it; CI does the
//! same in the `acceptance` job and before every release.
