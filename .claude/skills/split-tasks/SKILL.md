---
name: split-tasks
description: Conductor workflow — split one user story into worker-sized task issues, each labelled complexity:simple or complexity:hard with a reason (cost routing), with dependencies recorded. Use when the user says "split story #N".
argument-hint: <story issue number>
disable-model-invocation: true
---

# /split-tasks $ARGUMENTS

You are the **conductor**. Split story **#$ARGUMENTS** into tasks a single worker can finish in one
PR. Do not write code.

1. **Read** the story (`gh issue view $ARGUMENTS`) and any linked ADR. For codebase facts (where
   things live, what a change touches), ask the **scout** agent (description
   `#$ARGUMENTS scout: <question>`). Do not read source files yourself.
2. **Design the split**: usually domain rule → use case → adapter → acceptance test, but follow the
   story. Each task: one clear outcome, checkable "Done when" items, the crates it touches.
   Tasks that edit the same files or crate get a "blocked by" link even when there is no logical
   order between them, because `/implement` runs unblocked tasks in parallel. Tasks in different
   crates with no dependency get no link, so they can run together.
3. **Route each task** with the rule from `CLAUDE.md`:
   - `complexity:simple` (→ Sonnet) only if **all three** hold: clear acceptance criteria, touches
     **one crate**, needs **no new design decision**;
   - otherwise `complexity:hard` (→ Opus).
   Write a one-line reason. When in doubt, choose hard: a wrong "simple" costs a failed attempt
   plus the Opus run.
4. **Show the plan** as a table (task, crates, complexity, reason, blocked by) and wait for the
   human's OK. Keep it brief; the human may approve with a word.
5. **Create** each task with the task form's sections (`gh issue create --label
   type:task,complexity:<c>,priority:<p>`), then:
   - `scripts/issue-link.sh sub $ARGUMENTS <task>`
   - `scripts/issue-link.sh blocked-by <task> <blocker>` for every dependency
   - `scripts/board.sh <task-url> Status=Ready Complexity=<c> Model=<sonnet|opus> Priority=<P> "ADM phase=E Opportunities & Solutions"`
   - set the story's card to `Status=Ready`.
6. **Report** the created tasks and which are ready now (no open blockers):
   `scripts/issue-link.sh open-blockers <task>` prints nothing for a ready task.
