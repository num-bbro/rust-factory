<!-- Generated from docs/architecture/model.xml (the Deliverable elements) by `just model-docs`. Do not edit: change the model, see docs/togaf/template.md. -->
# TOGAF architecture documents

The factory follows the **TOGAF Architecture Development Method (ADM)**. Each phase has one document
here. The documents hold the *narrative*: purpose, decisions, open questions. The *structure*
(actors, processes, applications, nodes and how they relate) lives in the ArchiMate model
[`../architecture/model.xml`](../architecture/model.xml). Documents refer to model elements by ID
(e.g. `id-bus-proc-review`) instead of repeating them.

Architecture site: <https://num-bbro.github.io/rust-factory/>

Each document is a `Deliverable` element of that model, and these pages are generated from it by
`just model-docs`, never edited by hand ([template.md](template.md) says how to add or change one).
A page shows the views its document names, each with its diagram and a catalog of the elements
drawn.

| ADM phase | Document | Views | Suggested viewpoints | Factory artifacts |
|---|---|---|---|---|
| Preliminary | [00-preliminary.md](00-preliminary.md) | [Why the factory exists](00-preliminary.md#id-view-motivation) | — | `CLAUDE.md`, `CONTRIBUTING.md` |
| A. Architecture Vision | [A-architecture-vision.md](A-architecture-vision.md) | [Why the factory exists](A-architecture-vision.md#id-view-motivation), [Reservations: cancel a reservation](A-architecture-vision.md#id-view-reservation-cancel) | Motivation | Epic issues |
| B. Business Architecture | [B-business-architecture.md](B-business-architecture.md) | [Delivery lifecycle](B-business-architecture.md#id-view-lifecycle), [Reservations: cancel a reservation](B-business-architecture.md#id-view-reservation-cancel) | Business Process Cooperation, Organization | User stories |
| C. Information Systems | [C-information-systems-architecture.md](C-information-systems-architecture.md) | [Factory overview](C-information-systems-architecture.md#id-view-layered), [Reservations: cancel a reservation](C-information-systems-architecture.md#id-view-reservation-cancel) | Application Cooperation, Information Structure | Crates, data model |
| D. Technology Architecture | [D-technology-architecture.md](D-technology-architecture.md) | [Factory overview](D-technology-architecture.md#id-view-layered) | Technology, Implementation and Deployment | `deploy/`, CI |
| E. Opportunities & Solutions | [E-opportunities-and-solutions.md](E-opportunities-and-solutions.md) | — | Project | Milestones, task split |
| F. Migration Planning | [F-migration-planning.md](F-migration-planning.md) | [Releases](F-migration-planning.md#id-view-releases) | Migration | Releases, pilot plan |
| G. Implementation Governance | [G-implementation-governance.md](G-implementation-governance.md) | [Delivery lifecycle](G-implementation-governance.md#id-view-lifecycle) | — | PR gates, reviews |
| H. Architecture Change Mgmt | [H-architecture-change-management.md](H-architecture-change-management.md) | — | — | Change-request issues |
| Requirements Management (centre) | [requirements-management.md](requirements-management.md) | [Reservations: cancel a reservation](requirements-management.md#id-view-reservation-cancel) | Requirements Realization | Requirement issues, board |

**How the phases run in practice:** A–D are done for each epic, iterated lightly as stories are
refined. E–F happen when the conductor splits work and plans releases. G is every PR. H is every
change request. Requirements management runs continuously on the GitHub Project board.

In this template, the documents describe **the factory itself**. A project created from the template
replaces their content with its own business case and keeps the structure. Each document also has a
short **Sample domain** part for the reservation service the factory builds as its worked example
(epics from #17 on).
