# TOGAF architecture documents

The factory follows the **TOGAF Architecture Development Method (ADM)**. Each phase has one
document here. The documents hold the *narrative*: purpose, decisions, open questions. The
*structure* (actors, processes, applications, nodes and how they relate) lives in the ArchiMate
model under [`../architecture/model/`](../architecture/model/). Documents refer to model
elements by ID (e.g. `id-bus-proc-review`) instead of repeating them.

| ADM phase | Document | Main ArchiMate views | Factory artifacts |
|---|---|---|---|
| Preliminary | [00-preliminary.md](00-preliminary.md) | — | `CLAUDE.md`, `CONTRIBUTING.md` |
| A. Architecture Vision | [A-architecture-vision.md](A-architecture-vision.md) | Motivation | Epic issues |
| B. Business Architecture | [B-business-architecture.md](B-business-architecture.md) | Business Process Cooperation, Organization | User stories |
| C. Information Systems | [C-information-systems-architecture.md](C-information-systems-architecture.md) | Application Cooperation, Information Structure | Crates, data model |
| D. Technology Architecture | [D-technology-architecture.md](D-technology-architecture.md) | Technology, Implementation and Deployment | `deploy/`, CI |
| E. Opportunities & Solutions | [E-opportunities-and-solutions.md](E-opportunities-and-solutions.md) | Project | Milestones, task split |
| F. Migration Planning | [F-migration-planning.md](F-migration-planning.md) | Migration | Releases, pilot plan |
| G. Implementation Governance | [G-implementation-governance.md](G-implementation-governance.md) | — | PR gates, reviews |
| H. Architecture Change Mgmt | [H-architecture-change-management.md](H-architecture-change-management.md) | — | Change-request issues |
| Requirements Management (centre) | [requirements-management.md](requirements-management.md) | Requirements Realization | Requirement issues, board |

**How the phases run in practice:** A–D are done for each epic, iterated lightly as stories are
refined. E–F happen when the conductor splits work and plans releases. G is every PR. H is every
change request. Requirements management runs continuously on the GitHub Project board.

In this template, the documents describe **the factory itself**. A project created from the
template replaces their content with its own business case and keeps the structure.
Each document also has a short **Sample domain** part for the reservation service the factory
builds as its worked example (epics from #17 on).
