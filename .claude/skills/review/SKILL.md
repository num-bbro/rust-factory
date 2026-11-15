---
name: review
description: Conductor workflow — have the reviewer agent review a pull request against the factory rules, then summarise for the human's merge decision. Use when the user says "review PR #N" or after /implement reports a PR.
argument-hint: <pr number>
disable-model-invocation: true
---

# /review $ARGUMENTS

You are the **conductor**. Prepare PR **#$ARGUMENTS** for the human's merge decision.

1. `gh pr view $ARGUMENTS --json number,title,body,headRefName` and find the linked task
   (`Closes #N`) and its complexity label.
2. Launch the **reviewer** agent with description `#<task> review PR $ARGUMENTS`.
   Use the reviewer's default model (Sonnet) for `complexity:simple` tasks and docs-only PRs;
   pass **model opus** for `complexity:hard` tasks, escalated tasks and architecture PRs.
3. When it reports:
   - verdict `changes` with must-fix items → relaunch the **original worker type** for the task
     with description `#<task> fix review on PR $ARGUMENTS`, telling it to push fixes to the same
     branch. Then review again (at most twice; after that, hand it to the human).
   - verdict `ready` → `scripts/board.sh <pr-url> Status="In review"` (unchanged) and summarise
     for the human: what the PR does, gate results, reviewer notes, cost so far
     (`python3 -I scripts/cost-report.py --issue <task>`).
4. **Human gate 2**: ask the human to merge (Squash and merge → Confirm). Never merge yourself.
   After they say it is merged, verify on GitHub (`gh pr view $ARGUMENTS --json state`) before
   moving the cards to `Accepted`.
