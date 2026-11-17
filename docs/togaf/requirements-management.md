<!-- Generated from docs/architecture/model.xml (id-impl-del-requirements-management) by `just model-docs`. Do not edit: change the model, see docs/togaf/template.md. -->
# Requirements Management

**Purpose:** Keep requirements visible, prioritised and traceable through every phase.

## Outputs
- Requirement and story issues
- Priorities (MoSCoW)
- Traceability links

## Content
Requirements live as GitHub issues (forms in `.github/ISSUE_TEMPLATE/`), prioritised with MoSCoW
labels and tracked on the Project board through Backlog → Released. Important requirements are also
ArchiMate Requirement elements, linked to the elements that realise them.

Sample domain: the stories of epic #17 are requirements in the model, so the chain story →
requirement → application service is visible in
[`id-view-reservation-cancel`](#id-view-reservation-cancel): #18 is
[`id-mot-req-cancel`](#id-mot-req-cancel), #19 is
[`id-mot-req-cancel-refused`](#id-mot-req-cancel-refused), both realised by
[`id-app-svc-cancel`](#id-app-svc-cancel). Story #80 of epic #79 is
[`id-mot-req-list`](#id-mot-req-list), realised by [`id-app-svc-list`](#id-app-svc-list).

## Open questions
- _none yet_

## <a id="id-view-reservation-cancel"></a>Reservations 1/2: why and what (motivation, business)

Sample reservation domain, epics #17 and #79, part 1 of 2: why customers cancel and list, the
requirements of stories #18, #19 and #80, the business processes, and the application services that
realise and serve them. Part 2, id-view-reservation-app, shows the crates, API and data behind those
services.

![Reservations 1/2: why and what (motivation, business)](../architecture/views/id-view-reservation-cancel.png)

Clickable version:
[report](https://num-bbro.github.io/rust-factory/report/id-model-factory/views/id-view-reservation-cancel.html)

| ID | Name | Type | Decisions | Issues | Crate / code | Release | Other documents |
|---|---|---|---|---|---|---|---|
| <a id="id-app-svc-book"></a>`id-app-svc-book` | Book a slot | ApplicationService | [ADR 0010](../adr/0010-openapi-specification-spec-first.md) |  | `crates/application`, `BookSlot` | Release v0.1.0 | [A. Architecture Vision](A-architecture-vision.md#id-app-svc-book), [B. Business Architecture](B-business-architecture.md#id-app-svc-book), [C. Information Systems Architecture](C-information-systems-architecture.md#id-app-svc-book) |
| <a id="id-app-svc-cancel"></a>`id-app-svc-cancel` | Cancel a reservation | ApplicationService | [ADR 0007](../adr/0007-cancel-reservation-by-delete.md), [ADR 0010](../adr/0010-openapi-specification-spec-first.md) | #17 |  | Release v0.2.0 | [A. Architecture Vision](A-architecture-vision.md#id-app-svc-cancel), [B. Business Architecture](B-business-architecture.md#id-app-svc-cancel), [C. Information Systems Architecture](C-information-systems-architecture.md#id-app-svc-cancel) |
| <a id="id-app-svc-list"></a>`id-app-svc-list` | List the reservations | ApplicationService | [ADR 0010](../adr/0010-openapi-specification-spec-first.md), [ADR 0012](../adr/0012-list-reservations-by-get.md) | #79 | `crates/application`, `ListReservations` | Release v0.3.0 | [A. Architecture Vision](A-architecture-vision.md#id-app-svc-list), [B. Business Architecture](B-business-architecture.md#id-app-svc-list), [C. Information Systems Architecture](C-information-systems-architecture.md#id-app-svc-list) |
| <a id="id-bus-act-customer"></a>`id-bus-act-customer` | Customer | BusinessActor |  |  |  |  | [A. Architecture Vision](A-architecture-vision.md#id-bus-act-customer), [B. Business Architecture](B-business-architecture.md#id-bus-act-customer), [C. Information Systems Architecture](C-information-systems-architecture.md#id-bus-act-customer) |
| <a id="id-bus-obj-reservation"></a>`id-bus-obj-reservation` | Reservation | BusinessObject |  |  |  | Release v0.1.0 | [A. Architecture Vision](A-architecture-vision.md#id-bus-obj-reservation), [B. Business Architecture](B-business-architecture.md#id-bus-obj-reservation) |
| <a id="id-bus-proc-cancel"></a>`id-bus-proc-cancel` | Cancel a reservation | BusinessProcess | [ADR 0007](../adr/0007-cancel-reservation-by-delete.md) | #17 |  | Release v0.2.0 | [A. Architecture Vision](A-architecture-vision.md#id-bus-proc-cancel), [B. Business Architecture](B-business-architecture.md#id-bus-proc-cancel), [C. Information Systems Architecture](C-information-systems-architecture.md#id-bus-proc-cancel) |
| <a id="id-bus-proc-list"></a>`id-bus-proc-list` | List the reservations | BusinessProcess | [ADR 0012](../adr/0012-list-reservations-by-get.md) | #79 |  | Release v0.3.0 | [A. Architecture Vision](A-architecture-vision.md#id-bus-proc-list), [B. Business Architecture](B-business-architecture.md#id-bus-proc-list), [C. Information Systems Architecture](C-information-systems-architecture.md#id-bus-proc-list) |
| <a id="id-bus-proc-reserve"></a>`id-bus-proc-reserve` | Reserve a slot | BusinessProcess |  |  |  | Release v0.1.0 | [A. Architecture Vision](A-architecture-vision.md#id-bus-proc-reserve), [B. Business Architecture](B-business-architecture.md#id-bus-proc-reserve), [C. Information Systems Architecture](C-information-systems-architecture.md#id-bus-proc-reserve) |
| <a id="id-mot-drv-blocked-slots"></a>`id-mot-drv-blocked-slots` | Unused slots stay blocked | Driver |  | #17 |  |  | [A. Architecture Vision](A-architecture-vision.md#id-mot-drv-blocked-slots), [B. Business Architecture](B-business-architecture.md#id-mot-drv-blocked-slots) |
| <a id="id-mot-goal-free-slots"></a>`id-mot-goal-free-slots` | Customers can free slots they no longer need | Goal |  |  |  | Release v0.2.0 | [A. Architecture Vision](A-architecture-vision.md#id-mot-goal-free-slots), [B. Business Architecture](B-business-architecture.md#id-mot-goal-free-slots) |
| <a id="id-mot-out-rebook"></a>`id-mot-out-rebook` | Cancelled slot rebookable at once | Outcome | [ADR 0007](../adr/0007-cancel-reservation-by-delete.md) | #17 |  | Release v0.2.0 | [A. Architecture Vision](A-architecture-vision.md#id-mot-out-rebook), [B. Business Architecture](B-business-architecture.md#id-mot-out-rebook) |
| <a id="id-mot-req-cancel"></a>`id-mot-req-cancel` | Cancel a reservation by its id | Requirement | [ADR 0007](../adr/0007-cancel-reservation-by-delete.md) | #18 |  | Release v0.2.0 | [A. Architecture Vision](A-architecture-vision.md#id-mot-req-cancel), [B. Business Architecture](B-business-architecture.md#id-mot-req-cancel) |
| <a id="id-mot-req-cancel-refused"></a>`id-mot-req-cancel-refused` | Refuse cancelling an unknown reservation | Requirement | [ADR 0007](../adr/0007-cancel-reservation-by-delete.md) | #19 |  | Release v0.2.0 | [A. Architecture Vision](A-architecture-vision.md#id-mot-req-cancel-refused), [B. Business Architecture](B-business-architecture.md#id-mot-req-cancel-refused) |
| <a id="id-mot-req-list"></a>`id-mot-req-list` | List all reservations by start time | Requirement | [ADR 0012](../adr/0012-list-reservations-by-get.md) | #80 |  | Release v0.3.0 | [A. Architecture Vision](A-architecture-vision.md#id-mot-req-list), [B. Business Architecture](B-business-architecture.md#id-mot-req-list) |
| <a id="id-mot-sh-customer"></a>`id-mot-sh-customer` | Customer | Stakeholder |  |  |  |  | [A. Architecture Vision](A-architecture-vision.md#id-mot-sh-customer), [B. Business Architecture](B-business-architecture.md#id-mot-sh-customer) |
| <a id="id-mot-sh-front-desk"></a>`id-mot-sh-front-desk` | Front-desk manager | Stakeholder |  |  |  |  | [A. Architecture Vision](A-architecture-vision.md#id-mot-sh-front-desk), [B. Business Architecture](B-business-architecture.md#id-mot-sh-front-desk) |
