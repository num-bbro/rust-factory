# C. Information Systems Architecture

**Purpose:** Describe the applications and data that support the business: components, interfaces, data objects.

## Outputs
- Application components and their interfaces
- Data objects and ownership
- Mapping to Rust crates

## Content
Applications in the factory: conductor agent, hard / simple workers, scout, and GitHub (issues, PRs). Data objects: issue (`id-app-data-issue`) and pull request (`id-app-data-pr`).

For a project, each application component maps to a crate in the Cargo workspace (domain, application, adapters, app), and each data object to a domain type or table.

## Open questions
- _none yet_
