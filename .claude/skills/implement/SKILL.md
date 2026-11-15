---
name: implement
description: Conductor workflow — send ready task issues to the right worker (Sonnet for complexity:simple, Opus for complexity:hard) in parallel waves of up to 3 non-overlapping tasks, handle escalation, and report the resulting PRs. Use when the user says "implement #N" or "implement the ready tasks of story #N".
argument-hint: <task issue number(s)>
disable-model-invocation: true
---

# /implement $ARGUMENTS

You are the **conductor**. You dispatch and supervise; workers write the code.

Work in **waves**: a wave is a set of ready tasks that run concurrently, one worker (and one git
worktree) each. A single ready task is simply a wave of one.

1. **Check readiness** of every task in `$ARGUMENTS` first
   - `gh issue view <N> --json state,labels,title`: must be open and have `type:task` and exactly
     one `complexity:*` label. Missing label → ask the human or run `/split-tasks` rules first.
   - `scripts/issue-link.sh open-blockers <N>` must print nothing. Otherwise the task is *held*;
     say which blocker is open.
2. **Pick the wave.** Of the ready tasks, take them in the order given and add a task to the wave
   only if its "Crates / modules touched" field shares no crate or file with a task already in the
   wave. A task that overlaps is *held* ("touches the same crate as #N; run it after that PR is
   merged"), because two branches editing the same files conflict when the second PR is updated.
   A task is also *held* if it shares a crate or file with a task that is already running or whose
   PR is still open and unmerged (earlier wave or earlier `/implement`). To see them:
   `gh pr list --state open --json number,title,body`, then for each PR's `Closes #N` task read
   its "Crates / modules touched" field. Held reason: "touches the same crate as #N, whose PR #P
   is still open; run it after that PR is merged".
   A task whose "Crates / modules touched" field is empty or too vague to compare (e.g.
   "several") counts as overlapping everything: it runs alone, as a wave of one, when nothing else
   is running or open. Say so in the report so the human can fix the task issue.
   At most **3** workers per wave (cost burst and the human's review load); the rest are held for
   the next wave.
3. **Route** each task of the wave
   - `complexity:simple` → agent **implementer-simple** (Claude Sonnet 5.5)
   - `complexity:hard` → agent **implementer-hard** (Claude Opus 5.5)
4. **Launch the wave in one message**: one Agent call per task, all in the same response, so the
   workers run concurrently. Each agent description **must start with `#<N> `** (e.g.
   `#42 implement booking cancel`); `just cost` attributes spend by it. The prompt: the task
   number, the repo, and nothing the worker can read from the issue itself.
5. **Handle each worker's final report as it arrives**, independently of the others. One task
   failing never cancels the others.
   - `DONE pr=<url>` → check the PR exists (`gh pr view <url> --json number,state,body`) and its
     body states the model. Then suggest `/review <pr>`.
   - `ESCALATE reason=…` (simple worker only; it failed `just check` twice or the task was
     mislabelled) →
     `gh issue edit <N> --add-label escalated`;
     `gh issue comment <N> --body "Escalated from implementer-simple to implementer-hard: <reason>. Branch: <branch>."`;
     `scripts/board.sh <issue-url> Model=opus`;
     relaunch as **implementer-hard** with description `#<N> escalated: <title>`, passing the
     branch, without waiting for the rest of the wave. The relaunch takes over the slot of the
     worker it replaces: it is not an extra worker against the cap of 3, and no new task is added
     to the wave because of it.
   - `BLOCKED reason=…` → `gh issue edit <N> --add-label needs-human`, comment the reason, and tell
     the human what decision is needed. Do not retry.
6. **After a merge, later PRs fall behind `main`** (the ruleset requires an up-to-date branch).
   Before asking the human to merge the next PR of the wave, run `gh pr update-branch <pr>`, wait
   for CI to pass again, and only then ask. If the update conflicts, send it back to the task's
   worker type with description `#<N> resolve conflict with main on PR <pr>`.
7. **Next wave**: when PRs are merged, held tasks whose blockers are now closed become ready; say
   so and offer to run `/implement` on them. Never start a wave on your own after a human gate.
8. **Never** merge PRs (human gate 2) and never implement code yourself, even if it looks quick.

**Report** a table: task, worker model, wave / held (with reason), result (PR / escalated /
blocked), and the next step. Escalations that recur for the same kind of task mean the routing
rule needs tuning; say so.
