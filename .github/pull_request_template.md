<!-- PR title = a Conventional Commit line, e.g. "feat(booking): allow cancelling a reservation (#42)".
     It becomes the squash-commit message on main. -->

## What and why
<!-- One or two sentences. -->

Closes #

## Traceability
- Story / requirement: #
- ADR: <!-- element id-mot-adr-NNNN and its generated page docs/adr/NNNN-....md, or "none" -->
- ArchiMate elements: <!-- element ids, or "none" -->

## Test evidence
<!-- New or changed tests, acceptance scenarios covered, anything checked by hand. -->
- [ ] `cargo fmt --check` and `cargo clippy -- -D warnings` pass
- [ ] Tests added or updated for every behavior change
- [ ] Acceptance scenarios for the story pass

## Worker
- Model: <!-- claude-sonnet-5-5 / claude-opus-5-5 / human -->
- Complexity label: <!-- simple / hard -->
- Escalated: <!-- no / yes: reason -->
