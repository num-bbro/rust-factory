<!-- Generated from docs/architecture/model.xml (id-impl-del-migration-planning) by `just model-docs`. Do not edit: change the model, see docs/togaf/template.md. -->
# F. Migration Planning

**Purpose:** Plan the sequence of releases from current to target state, and how each is rolled out.

## Outputs
- Release plan (milestones)
- Pilot plan and success criteria
- Rollback plan

## Content
Each release is built once as a container image, accepted, deployed to the pilot host, and rolled
out to production after human approval. Rollback means redeploying the previous image tag.

## Open questions
- _none yet_

## <a id="id-view-releases"></a>Releases

The releases in order and the decisions each one delivered; the Release column of the other catalogs
shows what else each release delivered.

![Releases](../architecture/views/id-view-releases.png)

| ID | Name | Type | Decisions | Issues | Crate / code | Release | Other documents |
|---|---|---|---|---|---|---|---|
| <a id="id-impl-plat-v0-1-0"></a>`id-impl-plat-v0-1-0` | Release v0.1.0 | Plateau |  |  |  |  |  |
| <a id="id-impl-plat-v0-2-0"></a>`id-impl-plat-v0-2-0` | Release v0.2.0 | Plateau |  |  |  |  |  |
| <a id="id-impl-plat-v0-2-1"></a>`id-impl-plat-v0-2-1` | Release v0.2.1 | Plateau |  |  |  |  |  |
| <a id="id-mot-adr-0003"></a>`id-mot-adr-0003` | ADR 0003: Layered Cargo workspace with enforced dependency direction | Constraint |  | #5 |  | Release v0.1.0 |  |
| <a id="id-mot-adr-0005"></a>`id-mot-adr-0005` | ADR 0005: Release image built once, accepted, then promoted unchanged | Constraint |  | #12 |  | Release v0.1.0 |  |
| <a id="id-mot-adr-0007"></a>`id-mot-adr-0007` | ADR 0007: Cancel a reservation by deleting it: \`DELETE /reservations/{id}\` | Constraint |  | #17 (stories #18, #19) |  | Release v0.2.0 |  |
| <a id="id-mot-adr-0008"></a>`id-mot-adr-0008` | ADR 0008: Atomic schedule changes through one \`update\` operation on the repository port | Constraint |  | #26 (bug), #37 (task) |  | Release v0.2.1 |  |
