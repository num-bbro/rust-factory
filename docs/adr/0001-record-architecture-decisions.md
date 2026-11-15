# 0001. Record architecture decisions as ADRs

- Status: Accepted
- Date: 2026-11-15
- Issue: #3
- Deciders: product owner, conductor
- ArchiMate elements: id-bus-obj-adr, id-mot-goal-traceable

## Context and problem
In past projects, the reasons behind design choices were lost. Later changes broke assumptions
nobody remembered. With AI agents writing much of the code, the reasoning would be lost even
faster unless it is written down where agents and humans both look.

## Decision drivers
- Decisions must survive staff and agent turnover.
- Agents must be able to read and write them as plain text in the repo.
- Business-side reviewers must be able to follow them.

## Options considered
1. **ADRs in the repo** (Markdown, MADR format), reviewed in PRs.
2. **Wiki pages**, separate from code.
3. **Nothing formal**, only PR descriptions.

## Decision
Chosen: **ADRs in the repo**, because they are versioned with the code, reviewed through the
same PR gate, and readable by agents without extra tools.

## Consequences
- Good: every significant decision has a findable, linked record.
- Bad: writing an ADR takes a few minutes per decision.
- Follow-up: the conductor writes an ADR whenever a task needs a new design decision; the
  "Architecture decision" issue form starts the process.
