---
name: implement
description: Conductor workflow — send one or more ready task issues to the right worker (Sonnet for complexity:simple, Opus for complexity:hard), handle escalation, and report the resulting PRs. Use when the user says "implement #N" or "implement the ready tasks of story #N".
argument-hint: <task issue number(s)>
disable-model-invocation: true
---

# /implement $ARGUMENTS

You are the **conductor**. You dispatch and supervise; workers write the code.

For each task number in `$ARGUMENTS`, **one at a time** (parallel workers come later, in Stage 9):

1. **Check readiness**
   - `gh issue view <N> --json state,labels,title`: must be open and have `type:task` and exactly
     one `complexity:*` label. Missing label → ask the human or run `/split-tasks` rules first.
   - `scripts/issue-link.sh open-blockers <N>` must print nothing. Otherwise skip it and say which
     blocker is open.
2. **Route**
   - `complexity:simple` → agent **implementer-simple** (Claude Sonnet 5.5)
   - `complexity:hard` → agent **implementer-hard** (Claude Opus 5.5)
3. **Launch the worker.** The agent description **must start with `#<N> `** (e.g.
   `#42 implement booking cancel`); `just cost` attributes spend by it. The prompt: the task
   number, the repo, and nothing the worker can read from the issue itself.
4. **Handle the worker's final report**
   - `DONE pr=<url>` → check the PR exists (`gh pr view <url> --json number,state,body`) and its
     body states the model. Then suggest `/review <pr>`.
   - `ESCALATE reason=…` (simple worker only; it failed `just check` twice or the task was
     mislabelled) →
     `gh issue edit <N> --add-label escalated`;
     `gh issue comment <N> --body "Escalated from implementer-simple to implementer-hard: <reason>. Branch: <branch>."`;
     `scripts/board.sh <issue-url> Model=opus`;
     relaunch as **implementer-hard** with description `#<N> escalated: <title>`, passing the branch.
   - `BLOCKED reason=…` → `gh issue edit <N> --add-label needs-human`, comment the reason, and tell
     the human what decision is needed. Do not retry.
5. **Never** merge PRs (human gate 2) and never implement code yourself, even if it looks quick.

**Report** a table: task, worker model, result (PR / escalated / blocked), and the next step.
Escalations that recur for the same kind of task mean the routing rule needs tuning; say so.
