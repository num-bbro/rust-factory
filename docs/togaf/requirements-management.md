# Requirements Management

**Purpose:** Keep requirements visible, prioritised and traceable through every phase.

## Outputs
- Requirement and story issues
- Priorities (MoSCoW)
- Traceability links

## Content
Requirements live as GitHub issues (forms in `.github/ISSUE_TEMPLATE/`), prioritised with MoSCoW labels and tracked on the Project board through Backlog → Released. Important requirements are also ArchiMate Requirement elements, linked to the elements that realise them.

Sample domain: the stories of epic #17 are requirements in the model, so the chain
story → requirement → application service is visible in `id-view-reservation-cancel`:
#18 is `id-mot-req-cancel`, #19 is `id-mot-req-cancel-refused`, both realised by
`id-app-svc-cancel`.

## Open questions
- _none yet_
