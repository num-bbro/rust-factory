# 0007. Cancel a reservation by deleting it: `DELETE /reservations/{id}`

- Status: Proposed
- Date: 2026-11-15
- Issue: #17 (stories #18, #19)
- Deciders: human approver (plan approved at gate 1 on 2026-11-15), architect agent
- ArchiMate elements: `id-app-svc-cancel`, `id-app-intf-reservation-api`, `id-bus-proc-cancel`,
  `id-mot-req-cancel`, `id-mot-req-cancel-refused`, `id-mot-out-rebook`, `id-app-data-schedule`

## Context and problem
Customers who can no longer come have no way to free their slot (`id-mot-drv-blocked-slots`).
Epic #17 asks that a customer can cancel a reservation by its id, and measures success as "a
cancelled slot can be booked again immediately" (`id-mot-out-rebook`). We must decide what
"cancel" means for the stored data and what the HTTP API looks like, both for success
(story #18, `id-mot-req-cancel`) and for an id that does not exist or was already cancelled
(story #19, `id-mot-req-cancel-refused`). Refunds, notifications and cancellation deadlines are
out of scope.

## Decision drivers
- The freed slot must be bookable at once, with no extra rule in the overlap check.
- Smallest change that meets the stories: the domain already has `Schedule::cancel`, which
  removes the reservation and answers `NotFound` for an unknown id.
- The API stays consistent with the existing `POST /reservations` resource and its `{error}`
  body for failures.
- A customer must be told clearly when nothing was cancelled (story #19).

## Options considered
1. **Remove the reservation; `DELETE /reservations/{id}` → `204 No Content`; unknown id →
   `404 Not Found` with `{error}`.**
2. **Soft delete: keep the reservation with status "cancelled" (history)**: the overlap check
   and every later query must skip cancelled reservations; storage grows; nobody asked for the
   history.
3. **Return `200 OK` with a body** (the cancelled reservation or its slot): more to specify and
   test; the client already knows what it cancelled.
4. **Idempotent delete: `204` also for an unknown or already-cancelled id**: simple for retrying
   clients, but a typo in the id would look like success, which contradicts story #19.

## Decision
Chosen: **option 1**, because it is what the domain already does (`Schedule::cancel`), it frees
the slot with no change to the overlap rule, it fits the REST resource that `POST /reservations`
creates, and it gives a clear refusal for ids that do not exist.

- `DELETE /reservations/{id}` on the reservation API (`id-app-intf-reservation-api`), realised
  by a new cancel use case in `crates/application` (`id-app-svc-cancel`).
- Success: `204 No Content`, no body.
- Unknown id, or an id that was already cancelled: `404 Not Found` with the existing
  `{"error": "..."}` body. Cancelling twice therefore gives `404` the second time.
- Cancelling removes the reservation from the schedule (`id-app-data-schedule`). No history is
  kept. Reservation ids are never reused, so an old id can never cancel someone else's newer
  reservation.
- Storage failures map to `503`, as for booking. An id that is not a number is rejected by the
  HTTP adapter before any use case runs (axum's path extraction answers `400`).

## Consequences
- Good: no domain change; the use case and the HTTP handler are thin; the acceptance scenarios
  of #18 and #19 map one to one onto status codes.
- Good: the overlap check stays the only rule for booking, so a cancelled slot is free at once.
- Bad: no record that a reservation ever existed once it is cancelled: no audit trail, no
  "no-show" statistics, and no way to undo a cancellation. If such a need appears, a new ADR
  supersedes this one (likely option 2).
- Bad: a client that retries a successful `DELETE` (e.g. after a timeout) sees `404`; it must
  treat `404` after its own earlier attempt as "already cancelled".
- Bad: anyone who knows a reservation id can cancel it; there is no authentication in the
  sample domain yet. Out of scope of #17.
- Follow-up: implementation in the task issues under stories #18 and #19.
