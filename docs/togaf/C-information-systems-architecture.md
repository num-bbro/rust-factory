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
(`id-app-comp-db`). The Serving relationships between these crate components show the run-time
call direction, not the Cargo dependency direction, which ADR 0003 governs. So
`id-rel-068` (the persistence adapter serves the use cases) is not a layering violation: at
run time the use cases call the adapter through their `ScheduleRepository` port, while in Cargo
`adapters-db` depends on `application` (dependency inversion).

Customers use the service through the reservations HTTP API (`id-app-intf-reservation-api`),
which is part of the HTTP adapter. The API offers two application services: book a slot
(`id-app-svc-book`) and, from epic #17, cancel a reservation (`id-app-svc-cancel`). The data is
the day's schedule (`id-app-data-schedule`), which realises the reservation business object.

Cancelling is `DELETE /reservations/{id}`: `204 No Content` on success, `404 Not Found` with the
usual `{error}` body for an unknown or already cancelled id; a non-numeric id gets the
framework's plain-text `400`. The reservation is removed, not marked; see ADR 0007 for the
options considered. The domain rule already exists
(`Schedule::cancel`); the change adds a use case and an HTTP route. Known risk, not fixed by
this epic: load, change and save of the schedule are not atomic, so concurrent requests can
lose or duplicate reservations (bug #26).

## Open questions
- _none yet_
