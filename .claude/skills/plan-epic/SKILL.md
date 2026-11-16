---
name: plan-epic
description: Conductor workflow — turn an approved business epic into user stories (and architecture work if needed), after the human approves the plan. Use when the user says "plan epic #N" or a new epic issue needs breaking down.
argument-hint: <epic issue number>
disable-model-invocation: true
---

# /plan-epic $ARGUMENTS

You are the **conductor**. Plan epic **#$ARGUMENTS** into user stories. Do not write code.

1. **Read** the epic (`gh issue view $ARGUMENTS`). For codebase or model context, delegate to the
   **scout** agent (description `#$ARGUMENTS scout: <question>`) instead of reading files yourself.
2. **Draft** (in chat, not yet on GitHub):
   - 3–8 user stories, each in the user-story form's shape: *As a / I want / so that*, Gherkin
     acceptance scenarios, business rules, MoSCoW priority. Each story must be independently
     valuable and testable; split anything bigger than ~3 tasks.
   - **Architecture impact**: which ArchiMate elements/views change, which decisions need an ADR
     (an ADR is an element of `docs/architecture/model.xml`, the one edited source; the ADR and
     TOGAF pages and the view images are generated from it).
   - Suggested order and dependencies between stories.
3. **Human gate 1**: show the draft and ask for approval or changes. **Stop here until the human
   approves.** Revise as asked.
4. **After approval**:
   - If architecture changes: launch the **architect** agent (description
     `#$ARGUMENTS architecture for <epic title>`), and tell the human its PR needs sign-off. The
     architect edits the model, then runs `just model-fmt`, `just model-docs`, `just model-check`
     and `just model`, and commits the generated pages and images with it.
   - Create each story with `gh issue create --label type:story,priority:<p>` (body in the form's
     section order), then `scripts/issue-link.sh sub $ARGUMENTS <story>` and
     `scripts/board.sh <story-url> Status=Backlog Priority=<P> "ADM phase=B Business"`.
   - Record story-to-story dependencies: `scripts/issue-link.sh blocked-by <story> <blocker>`.
5. **Report**: a table of created stories (number, title, priority, blocked by) and the next step
   (`/split-tasks <story>` for the first ready story).
