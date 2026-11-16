<!-- Generated from docs/architecture/model.xml (id-impl-del-information-systems-architecture) by `just model-docs`. Do not edit: change the model, see docs/togaf/template.md. -->
# C. Information Systems Architecture

**Purpose:** Describe the applications and data that support the business: components, interfaces,
data objects.

## Outputs
- Application components and their interfaces
- Data objects and ownership
- Mapping to Rust crates

## Content
Applications in the factory: conductor agent, hard / simple workers, scout, and GitHub (issues,
PRs). Data objects: issue ([`id-app-data-issue`](#id-app-data-issue)) and pull request
([`id-app-data-pr`](#id-app-data-pr)).

For a project, each application component maps to a crate in the Cargo workspace (domain,
application, adapters, app), and each data object to a domain type or table.

### Sample domain: reservations
The reservation service ([`id-app-comp-reservation-svc`](#id-app-comp-reservation-svc), crate `app`)
is composed of one component per crate, following ADR 0003: domain
([`id-app-comp-domain`](#id-app-comp-domain)), use cases
([`id-app-comp-application`](#id-app-comp-application)), HTTP adapter
([`id-app-comp-http`](#id-app-comp-http)) and persistence adapter
([`id-app-comp-db`](#id-app-comp-db)). The Serving relationships between these crate components show
the run-time call direction, not the Cargo dependency direction, which ADR 0003 governs. So
`id-rel-068` (the persistence adapter serves the use cases) is not a layering violation: at run time
the use cases call the adapter through their `ScheduleRepository` port, while in Cargo `adapters-db`
depends on `application` (dependency inversion).

Customers use the service through the reservations HTTP API
([`id-app-intf-reservation-api`](#id-app-intf-reservation-api)), which is part of the HTTP adapter.
The API offers two application services: book a slot ([`id-app-svc-book`](#id-app-svc-book)) and,
from epic #17, cancel a reservation ([`id-app-svc-cancel`](#id-app-svc-cancel)). The data is the
day's schedule ([`id-app-data-schedule`](#id-app-data-schedule)), which realises the reservation
business object.

Cancelling is `DELETE /reservations/{id}`: `204 No Content` on success, `404 Not Found` with the
usual `{error}` body for an unknown or already cancelled id; a non-numeric id gets the framework's
plain-text `400`. The reservation is removed, not marked; see ADR 0007 for the options considered.
The domain rule already exists (`Schedule::cancel`); the change adds a use case and an HTTP route.

Every change to the schedule goes through one atomic `update` operation on the `ScheduleRepository`
port: reading, changing and storing the schedule happen as one step, and a change refused by a
business rule stores nothing. Concurrent requests therefore cannot lose, duplicate or bring back
reservations (bug #26, fixed by ADR 0008). Each host still keeps its own in-memory schedule.

## Open questions
- _none yet_

## <a id="id-view-layered"></a>Factory overview

Business, application and technology layers of the factory, top to bottom.

![Factory overview](../architecture/views/id-view-layered.png)

| ID | Name | Type | Decisions | Issues | Crate / code | Release | Other documents |
|---|---|---|---|---|---|---|---|
| <a id="id-app-comp-conductor"></a>`id-app-comp-conductor` | Conductor agent (Fable) | ApplicationComponent | [ADR 0004](../adr/0004-agent-team-and-cost-routing.md) |  |  |  | [D. Technology Architecture](D-technology-architecture.md#id-app-comp-conductor) |
| <a id="id-app-comp-github"></a>`id-app-comp-github` | GitHub | ApplicationComponent |  |  |  |  | [D. Technology Architecture](D-technology-architecture.md#id-app-comp-github) |
| <a id="id-app-comp-hard"></a>`id-app-comp-hard` | Hard worker (Opus) | ApplicationComponent | [ADR 0004](../adr/0004-agent-team-and-cost-routing.md) |  |  |  | [D. Technology Architecture](D-technology-architecture.md#id-app-comp-hard) |
| <a id="id-app-comp-scout"></a>`id-app-comp-scout` | Scout (Haiku) | ApplicationComponent | [ADR 0004](../adr/0004-agent-team-and-cost-routing.md) |  |  |  | [D. Technology Architecture](D-technology-architecture.md#id-app-comp-scout) |
| <a id="id-app-comp-simple"></a>`id-app-comp-simple` | Simple worker (Sonnet) | ApplicationComponent | [ADR 0004](../adr/0004-agent-team-and-cost-routing.md) |  |  |  | [D. Technology Architecture](D-technology-architecture.md#id-app-comp-simple) |
| <a id="id-app-data-issue"></a>`id-app-data-issue` | Issue | DataObject |  |  |  |  | [D. Technology Architecture](D-technology-architecture.md#id-app-data-issue) |
| <a id="id-app-data-pr"></a>`id-app-data-pr` | Pull request | DataObject |  |  |  |  | [D. Technology Architecture](D-technology-architecture.md#id-app-data-pr) |
| <a id="id-bus-act-human"></a>`id-bus-act-human` | Human approver | BusinessActor |  |  |  |  | [B. Business Architecture](B-business-architecture.md#id-bus-act-human), [D. Technology Architecture](D-technology-architecture.md#id-bus-act-human), [G. Implementation Governance](G-implementation-governance.md#id-bus-act-human) |
| <a id="id-bus-proc-deploy"></a>`id-bus-proc-deploy` | Pilot and roll out | BusinessProcess | [ADR 0006](../adr/0006-pilot-and-rollout-with-quadlet.md) |  |  |  | [B. Business Architecture](B-business-architecture.md#id-bus-proc-deploy), [D. Technology Architecture](D-technology-architecture.md#id-bus-proc-deploy), [G. Implementation Governance](G-implementation-governance.md#id-bus-proc-deploy) |
| <a id="id-bus-proc-implement"></a>`id-bus-proc-implement` | Implement task | BusinessProcess |  |  |  |  | [B. Business Architecture](B-business-architecture.md#id-bus-proc-implement), [D. Technology Architecture](D-technology-architecture.md#id-bus-proc-implement), [G. Implementation Governance](G-implementation-governance.md#id-bus-proc-implement) |
| <a id="id-bus-proc-plan"></a>`id-bus-proc-plan` | Plan and design | BusinessProcess |  |  |  |  | [B. Business Architecture](B-business-architecture.md#id-bus-proc-plan), [D. Technology Architecture](D-technology-architecture.md#id-bus-proc-plan), [G. Implementation Governance](G-implementation-governance.md#id-bus-proc-plan) |
| <a id="id-bus-proc-review"></a>`id-bus-proc-review` | Review and merge | BusinessProcess |  |  |  |  | [B. Business Architecture](B-business-architecture.md#id-bus-proc-review), [D. Technology Architecture](D-technology-architecture.md#id-bus-proc-review), [G. Implementation Governance](G-implementation-governance.md#id-bus-proc-review) |
| <a id="id-bus-role-conductor"></a>`id-bus-role-conductor` | Conductor | BusinessRole |  |  |  |  | [B. Business Architecture](B-business-architecture.md#id-bus-role-conductor), [D. Technology Architecture](D-technology-architecture.md#id-bus-role-conductor), [G. Implementation Governance](G-implementation-governance.md#id-bus-role-conductor) |
| <a id="id-bus-role-worker"></a>`id-bus-role-worker` | Worker | BusinessRole |  |  |  |  | [B. Business Architecture](B-business-architecture.md#id-bus-role-worker), [D. Technology Architecture](D-technology-architecture.md#id-bus-role-worker), [G. Implementation Governance](G-implementation-governance.md#id-bus-role-worker) |
| <a id="id-mot-req-routing"></a>`id-mot-req-routing` | Route tasks to models by difficulty | Requirement | [ADR 0004](../adr/0004-agent-team-and-cost-routing.md) |  |  |  | [Preliminary](00-preliminary.md#id-mot-req-routing), [A. Architecture Vision](A-architecture-vision.md#id-mot-req-routing), [D. Technology Architecture](D-technology-architecture.md#id-mot-req-routing) |
| <a id="id-mot-req-togaf"></a>`id-mot-req-togaf` | Architecture documented in TOGAF / ArchiMate | Requirement | [ADR 0002](../adr/0002-archimate-model-as-text.md), [ADR 0009](../adr/0009-archimate-exchange-model-as-source.md) |  |  |  | [Preliminary](00-preliminary.md#id-mot-req-togaf), [A. Architecture Vision](A-architecture-vision.md#id-mot-req-togaf), [D. Technology Architecture](D-technology-architecture.md#id-mot-req-togaf) |
| <a id="id-tech-node-pilot"></a>`id-tech-node-pilot` | Pilot host | Node | [ADR 0006](../adr/0006-pilot-and-rollout-with-quadlet.md) |  |  |  | [D. Technology Architecture](D-technology-architecture.md#id-tech-node-pilot) |
| <a id="id-tech-node-prod"></a>`id-tech-node-prod` | Production hosts | Node | [ADR 0006](../adr/0006-pilot-and-rollout-with-quadlet.md) |  |  |  | [D. Technology Architecture](D-technology-architecture.md#id-tech-node-prod) |
| <a id="id-tech-node-workstation"></a>`id-tech-node-workstation` | Developer workstation | Node |  |  |  |  | [D. Technology Architecture](D-technology-architecture.md#id-tech-node-workstation) |
| <a id="id-tech-svc-ghcr"></a>`id-tech-svc-ghcr` | Container registry (GHCR) | TechnologyService | [ADR 0005](../adr/0005-release-image-and-acceptance.md) |  |  |  | [D. Technology Architecture](D-technology-architecture.md#id-tech-svc-ghcr) |
| <a id="id-tech-sw-archi"></a>`id-tech-sw-archi` | Archi | SystemSoftware | [ADR 0002](../adr/0002-archimate-model-as-text.md), [ADR 0009](../adr/0009-archimate-exchange-model-as-source.md) |  |  |  | [D. Technology Architecture](D-technology-architecture.md#id-tech-sw-archi) |
| <a id="id-tech-sw-podman"></a>`id-tech-sw-podman` | Podman | SystemSoftware | [ADR 0005](../adr/0005-release-image-and-acceptance.md), [ADR 0006](../adr/0006-pilot-and-rollout-with-quadlet.md) |  |  |  | [D. Technology Architecture](D-technology-architecture.md#id-tech-sw-podman) |
| <a id="id-tech-sw-rust"></a>`id-tech-sw-rust` | Rust toolchain | SystemSoftware | [ADR 0003](../adr/0003-layered-cargo-workspace.md) |  |  |  | [D. Technology Architecture](D-technology-architecture.md#id-tech-sw-rust) |

## <a id="id-view-reservation-cancel"></a>Reservations: cancel a reservation

Sample reservation domain, epic #17: why customers cancel, the business processes, and the crates
and API that serve them. Technology is unchanged (see id-view-layered).

![Reservations: cancel a reservation](../architecture/views/id-view-reservation-cancel.png)

| ID | Name | Type | Decisions | Issues | Crate / code | Release | Other documents |
|---|---|---|---|---|---|---|---|
| <a id="id-app-comp-application"></a>`id-app-comp-application` | Use cases (crate application) | ApplicationComponent | [ADR 0008](../adr/0008-atomic-schedule-update-through-the-port.md) |  | `crates/application` | Release v0.1.0, Release v0.2.0, Release v0.2.1 | [A. Architecture Vision](A-architecture-vision.md#id-app-comp-application), [B. Business Architecture](B-business-architecture.md#id-app-comp-application), [F. Migration Planning](F-migration-planning.md#id-app-comp-application), [Requirements Management](requirements-management.md#id-app-comp-application) |
| <a id="id-app-comp-db"></a>`id-app-comp-db` | Persistence adapter (crate adapters-db) | ApplicationComponent | [ADR 0008](../adr/0008-atomic-schedule-update-through-the-port.md) |  | `crates/adapters-db` | Release v0.1.0, Release v0.2.1 | [A. Architecture Vision](A-architecture-vision.md#id-app-comp-db), [B. Business Architecture](B-business-architecture.md#id-app-comp-db), [F. Migration Planning](F-migration-planning.md#id-app-comp-db), [Requirements Management](requirements-management.md#id-app-comp-db) |
| <a id="id-app-comp-domain"></a>`id-app-comp-domain` | Domain (crate domain) | ApplicationComponent |  |  | `crates/domain` | Release v0.1.0 | [A. Architecture Vision](A-architecture-vision.md#id-app-comp-domain), [B. Business Architecture](B-business-architecture.md#id-app-comp-domain), [F. Migration Planning](F-migration-planning.md#id-app-comp-domain), [Requirements Management](requirements-management.md#id-app-comp-domain) |
| <a id="id-app-comp-http"></a>`id-app-comp-http` | HTTP adapter (crate adapters-http) | ApplicationComponent |  |  | `crates/adapters-http` | Release v0.1.0, Release v0.2.0 | [A. Architecture Vision](A-architecture-vision.md#id-app-comp-http), [B. Business Architecture](B-business-architecture.md#id-app-comp-http), [F. Migration Planning](F-migration-planning.md#id-app-comp-http), [Requirements Management](requirements-management.md#id-app-comp-http) |
| <a id="id-app-comp-reservation-svc"></a>`id-app-comp-reservation-svc` | Reservation service | ApplicationComponent | [ADR 0003](../adr/0003-layered-cargo-workspace.md) |  | `crates/app` | Release v0.1.0 | [A. Architecture Vision](A-architecture-vision.md#id-app-comp-reservation-svc), [B. Business Architecture](B-business-architecture.md#id-app-comp-reservation-svc), [F. Migration Planning](F-migration-planning.md#id-app-comp-reservation-svc), [Requirements Management](requirements-management.md#id-app-comp-reservation-svc) |
| <a id="id-app-data-schedule"></a>`id-app-data-schedule` | Schedule | DataObject | [ADR 0007](../adr/0007-cancel-reservation-by-delete.md), [ADR 0008](../adr/0008-atomic-schedule-update-through-the-port.md) | #26 | `crates/domain`, `Schedule` | Release v0.1.0, Release v0.2.1 | [A. Architecture Vision](A-architecture-vision.md#id-app-data-schedule), [B. Business Architecture](B-business-architecture.md#id-app-data-schedule), [F. Migration Planning](F-migration-planning.md#id-app-data-schedule), [Requirements Management](requirements-management.md#id-app-data-schedule) |
| <a id="id-app-intf-reservation-api"></a>`id-app-intf-reservation-api` | Reservations HTTP API | ApplicationInterface | [ADR 0007](../adr/0007-cancel-reservation-by-delete.md) |  |  | Release v0.1.0, Release v0.2.0 | [A. Architecture Vision](A-architecture-vision.md#id-app-intf-reservation-api), [B. Business Architecture](B-business-architecture.md#id-app-intf-reservation-api), [F. Migration Planning](F-migration-planning.md#id-app-intf-reservation-api), [Requirements Management](requirements-management.md#id-app-intf-reservation-api) |
| <a id="id-app-svc-book"></a>`id-app-svc-book` | Book a slot | ApplicationService |  |  | `crates/application`, `BookSlot` | Release v0.1.0 | [A. Architecture Vision](A-architecture-vision.md#id-app-svc-book), [B. Business Architecture](B-business-architecture.md#id-app-svc-book), [F. Migration Planning](F-migration-planning.md#id-app-svc-book), [Requirements Management](requirements-management.md#id-app-svc-book) |
| <a id="id-app-svc-cancel"></a>`id-app-svc-cancel` | Cancel a reservation | ApplicationService | [ADR 0007](../adr/0007-cancel-reservation-by-delete.md) | #17 |  | Release v0.2.0 | [A. Architecture Vision](A-architecture-vision.md#id-app-svc-cancel), [B. Business Architecture](B-business-architecture.md#id-app-svc-cancel), [F. Migration Planning](F-migration-planning.md#id-app-svc-cancel), [Requirements Management](requirements-management.md#id-app-svc-cancel) |
| <a id="id-bus-act-customer"></a>`id-bus-act-customer` | Customer | BusinessActor |  |  |  |  | [A. Architecture Vision](A-architecture-vision.md#id-bus-act-customer), [B. Business Architecture](B-business-architecture.md#id-bus-act-customer), [Requirements Management](requirements-management.md#id-bus-act-customer) |
| <a id="id-bus-obj-reservation"></a>`id-bus-obj-reservation` | Reservation | BusinessObject |  |  |  | Release v0.1.0 | [A. Architecture Vision](A-architecture-vision.md#id-bus-obj-reservation), [B. Business Architecture](B-business-architecture.md#id-bus-obj-reservation), [Requirements Management](requirements-management.md#id-bus-obj-reservation) |
| <a id="id-bus-proc-cancel"></a>`id-bus-proc-cancel` | Cancel a reservation | BusinessProcess | [ADR 0007](../adr/0007-cancel-reservation-by-delete.md) | #17 |  | Release v0.2.0 | [A. Architecture Vision](A-architecture-vision.md#id-bus-proc-cancel), [B. Business Architecture](B-business-architecture.md#id-bus-proc-cancel), [Requirements Management](requirements-management.md#id-bus-proc-cancel) |
| <a id="id-bus-proc-reserve"></a>`id-bus-proc-reserve` | Reserve a slot | BusinessProcess |  |  |  | Release v0.1.0 | [A. Architecture Vision](A-architecture-vision.md#id-bus-proc-reserve), [B. Business Architecture](B-business-architecture.md#id-bus-proc-reserve), [Requirements Management](requirements-management.md#id-bus-proc-reserve) |
| <a id="id-mot-drv-blocked-slots"></a>`id-mot-drv-blocked-slots` | Unused slots stay blocked | Driver |  | #17 |  |  | [A. Architecture Vision](A-architecture-vision.md#id-mot-drv-blocked-slots), [B. Business Architecture](B-business-architecture.md#id-mot-drv-blocked-slots), [Requirements Management](requirements-management.md#id-mot-drv-blocked-slots) |
| <a id="id-mot-goal-free-slots"></a>`id-mot-goal-free-slots` | Customers can free slots they no longer need | Goal |  |  |  | Release v0.2.0 | [A. Architecture Vision](A-architecture-vision.md#id-mot-goal-free-slots), [B. Business Architecture](B-business-architecture.md#id-mot-goal-free-slots), [Requirements Management](requirements-management.md#id-mot-goal-free-slots) |
| <a id="id-mot-out-rebook"></a>`id-mot-out-rebook` | Cancelled slot rebookable at once | Outcome | [ADR 0007](../adr/0007-cancel-reservation-by-delete.md) | #17 |  | Release v0.2.0 | [A. Architecture Vision](A-architecture-vision.md#id-mot-out-rebook), [B. Business Architecture](B-business-architecture.md#id-mot-out-rebook), [Requirements Management](requirements-management.md#id-mot-out-rebook) |
| <a id="id-mot-req-cancel"></a>`id-mot-req-cancel` | Cancel a reservation by its id | Requirement | [ADR 0007](../adr/0007-cancel-reservation-by-delete.md) | #18 |  | Release v0.2.0 | [A. Architecture Vision](A-architecture-vision.md#id-mot-req-cancel), [B. Business Architecture](B-business-architecture.md#id-mot-req-cancel), [Requirements Management](requirements-management.md#id-mot-req-cancel) |
| <a id="id-mot-req-cancel-refused"></a>`id-mot-req-cancel-refused` | Refuse cancelling an unknown reservation | Requirement | [ADR 0007](../adr/0007-cancel-reservation-by-delete.md) | #19 |  | Release v0.2.0 | [A. Architecture Vision](A-architecture-vision.md#id-mot-req-cancel-refused), [B. Business Architecture](B-business-architecture.md#id-mot-req-cancel-refused), [Requirements Management](requirements-management.md#id-mot-req-cancel-refused) |
| <a id="id-mot-sh-customer"></a>`id-mot-sh-customer` | Customer | Stakeholder |  |  |  |  | [A. Architecture Vision](A-architecture-vision.md#id-mot-sh-customer), [B. Business Architecture](B-business-architecture.md#id-mot-sh-customer), [Requirements Management](requirements-management.md#id-mot-sh-customer) |
| <a id="id-mot-sh-front-desk"></a>`id-mot-sh-front-desk` | Front-desk manager | Stakeholder |  |  |  |  | [A. Architecture Vision](A-architecture-vision.md#id-mot-sh-front-desk), [B. Business Architecture](B-business-architecture.md#id-mot-sh-front-desk), [Requirements Management](requirements-management.md#id-mot-sh-front-desk) |
