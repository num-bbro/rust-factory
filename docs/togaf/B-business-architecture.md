# B. Business Architecture

**Purpose:** Describe how the business works: actors, roles, processes, information they use.

## Outputs
- Actors and roles
- Business processes
- Business objects
- Gaps between current and target

## Content
The factory's delivery lifecycle (`id-bus-proc-lifecycle`) consists of plan and design, implement task, review and merge, accept build, and pilot and roll out. The human approver (`id-bus-act-human`) holds the review and deploy gates; the conductor and worker roles are filled by AI agents.

For a project, each **user story** maps to business behaviour here; business rules become domain-layer code.

### Sample domain: reservations
A customer (`id-bus-act-customer`) reserves a slot (`id-bus-proc-reserve`) and, since epic #17,
can cancel it again (`id-bus-proc-cancel`); both work on a reservation (`id-bus-obj-reservation`).
Business rules for cancelling (stories #18, #19): only the named reservation is removed, its
slot is free at once, no history is kept, and cancelling a reservation that does not exist (or
no longer exists) is refused and changes nothing. Decision and alternatives: ADR 0007.

## Open questions
- _none yet_
