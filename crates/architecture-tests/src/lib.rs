//! Architecture rules as tests. Nothing to call here; see `tests/layers.rs`.
//!
//! Run with the rest of the suite (`just test`). A failure means a crate now depends on something
//! its layer must not know about; fix the dependency, don't relax the rule (unless an ADR says so).
