# C. Information Systems Architecture

**Purpose:** Describe the applications and data that support the business: components, interfaces, data objects.

## Outputs
- Application components and their interfaces
- Data objects and ownership
- Mapping to Rust crates

## Content
Applications in the factory: conductor agent, hard / simple workers, scout, and GitHub (issues, PRs). Data objects: issue (`id-app-data-issue`) and pull request (`id-app-data-pr`).

For a project, each application component maps to a crate in the Cargo workspace (domain, application, adapters, app), and each data object to a domain type or table.

### Sample domain: reservations
The reservation service (`id-app-comp-reservation-svc`, crate `app`) is composed of one
component per crate, following ADR 0003: domain (`id-app-comp-domain`), use cases
(`id-app-comp-application`), HTTP adapter (`id-app-comp-http`) and persistence adapter
(`id-app-comp-db`). Customers use it through the reservations HTTP API
(`id-app-intf-reservation-api`), which offers two application services: book a slot
(`id-app-svc-book`) and, from epic #17, cancel a reservation (`id-app-svc-cancel`). The data is
the day's schedule (`id-app-data-schedule`), which realises the reservation business object.

Cancelling is `DELETE /reservations/{id}`: `204 No Content` on success, `404 Not Found` with the
usual `{error}` body for an unknown or already cancelled id. The reservation is removed, not
marked; see ADR 0007 for the options considered. The domain rule already exists
(`Schedule::cancel`); the change adds a use case and an HTTP route.

## Open questions
- _none yet_
