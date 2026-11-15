//! Dependency rules of the layered workspace (ADR 0003).
//!
//! Dependencies point inward only:  app → adapters-* → application → domain.
//! The domain also stays free of infrastructure crates, so business rules never depend on
//! frameworks, async runtimes, serialization or databases.

use std::collections::{BTreeMap, BTreeSet};

use cargo_metadata::{DependencyKind, MetadataCommand};

/// Workspace crates each crate may depend on (normal dependencies, not dev-dependencies).
const ALLOWED_INTERNAL: &[(&str, &[&str])] = &[
    ("domain", &[]),
    ("application", &["domain"]),
    ("adapters-db", &["application", "domain"]),
    ("adapters-http", &["application", "domain"]),
    (
        "app",
        &["application", "domain", "adapters-db", "adapters-http"],
    ),
    ("architecture-tests", &[]),
    ("acceptance-tests", &[]),
];

/// External crates the domain may use. Keep this list tiny: anything here becomes part of every
/// business rule's dependencies.
const DOMAIN_EXTERNAL_ALLOWED: &[&str] = &["thiserror"];

/// Crates that mean "infrastructure" and must never appear in `domain` or `application`.
const INFRASTRUCTURE: &[&str] = &[
    "axum",
    "hyper",
    "tower",
    "tokio",
    "reqwest",
    "sqlx",
    "diesel",
    "sea-orm",
    "rusqlite",
    "serde_json",
    "tracing-subscriber",
];

struct Workspace {
    members: BTreeSet<String>,
    /// crate → normal dependency names
    deps: BTreeMap<String, BTreeSet<String>>,
    /// crate → all dependency names (normal, dev and build)
    all_deps: BTreeMap<String, BTreeSet<String>>,
}

fn workspace() -> Workspace {
    let manifest = concat!(env!("CARGO_MANIFEST_DIR"), "/../../Cargo.toml");
    let meta = MetadataCommand::new()
        .manifest_path(manifest)
        .no_deps()
        .exec()
        .expect("cargo metadata");
    let members: BTreeSet<String> = meta
        .workspace_packages()
        .iter()
        .map(|p| p.name.to_string())
        .collect();
    let deps = meta
        .workspace_packages()
        .iter()
        .map(|p| {
            let normal = p
                .dependencies
                .iter()
                .filter(|d| d.kind == DependencyKind::Normal)
                .map(|d| d.name.clone())
                .collect();
            (p.name.to_string(), normal)
        })
        .collect();
    let all_deps = meta
        .workspace_packages()
        .iter()
        .map(|p| {
            let all = p.dependencies.iter().map(|d| d.name.clone()).collect();
            (p.name.to_string(), all)
        })
        .collect();
    Workspace {
        members,
        deps,
        all_deps,
    }
}

#[test]
fn every_crate_has_a_layer_rule() {
    let ws = workspace();
    let ruled: BTreeSet<String> = ALLOWED_INTERNAL
        .iter()
        .map(|(c, _)| (*c).to_string())
        .collect();
    let missing: Vec<_> = ws.members.difference(&ruled).collect();
    assert!(
        missing.is_empty(),
        "new crate(s) {missing:?} have no entry in ALLOWED_INTERNAL; decide their layer first"
    );
}

#[test]
fn internal_dependencies_point_inward() {
    let ws = workspace();
    let mut violations = Vec::new();
    for (krate, allowed) in ALLOWED_INTERNAL {
        for dep in ws.deps.get(*krate).into_iter().flatten() {
            if ws.members.contains(dep) && !allowed.contains(&dep.as_str()) {
                violations.push(format!("{krate} → {dep}"));
            }
        }
    }
    assert!(
        violations.is_empty(),
        "dependencies pointing the wrong way (allowed: app → adapters → application → domain):\n  {}",
        violations.join("\n  ")
    );
}

#[test]
fn domain_uses_only_allowed_external_crates() {
    let ws = workspace();
    let extra: Vec<_> = ws.deps["domain"]
        .iter()
        .filter(|d| !ws.members.contains(*d) && !DOMAIN_EXTERNAL_ALLOWED.contains(&d.as_str()))
        .collect();
    assert!(
        extra.is_empty(),
        "domain must stay pure; these crates need an ADR before they may be added: {extra:?}"
    );
}

#[test]
fn core_layers_have_no_infrastructure() {
    let ws = workspace();
    let mut found = Vec::new();
    for krate in ["domain", "application"] {
        for dep in &ws.deps[krate] {
            if INFRASTRUCTURE.contains(&dep.as_str()) {
                found.push(format!("{krate} → {dep}"));
            }
        }
    }
    assert!(
        found.is_empty(),
        "infrastructure in a core layer:\n  {}",
        found.join("\n  ")
    );
}

#[test]
fn acceptance_tests_are_black_box() {
    // Acceptance tests must judge the service only from the outside (over HTTP), so they may not
    // depend on any workspace crate, not even as a dev-dependency.
    let ws = workspace();
    let internal: Vec<_> = ws.all_deps["acceptance-tests"]
        .iter()
        .filter(|d| ws.members.contains(*d))
        .collect();
    assert!(
        internal.is_empty(),
        "acceptance-tests must stay black-box; remove dependencies on {internal:?}"
    );
}
