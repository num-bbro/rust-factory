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
