# A. Architecture Vision

**Purpose:** Agree the business goal, scope, stakeholders and success measures before design starts.

## Outputs
- Stakeholders and concerns
- Drivers and goals
- Scope (in / out)
- Success measures

## Content
Vision for the factory: a business need becomes healthy, rolled-out Rust software, with every change traceable and AI cost under control.

- Stakeholder: product owner (`id-mot-sh-product-owner`)
- Driver: business needs change often (`id-mot-drv-change`)
- Goals: healthy software (`id-mot-goal-healthy`), traceability (`id-mot-goal-traceable`), cost control (`id-mot-goal-cost`)

For a project, the vision is captured first as an **Epic** issue, then reflected here and in the Motivation view.

### Sample domain: reservations (epic #17)
The factory's sample product is a reservation service for time slots. Epic #17, "Customers can
cancel a reservation", is its first change after booking:

- Stakeholders: customers (`id-mot-sh-customer`), who use it, and the front-desk manager
  (`id-mot-sh-front-desk`), who decides.
- Driver: unused slots stay blocked (`id-mot-drv-blocked-slots`).
- Goal: customers can free slots they no longer need (`id-mot-goal-free-slots`), measured by the
  outcome "a cancelled slot can be booked again immediately" (`id-mot-out-rebook`).
- Out of scope: refunds, notifications, cancellation deadlines.

View: `id-view-reservation-cancel`.

## Open questions
- _none yet_
