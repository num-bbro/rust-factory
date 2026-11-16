<!-- Generated from docs/architecture/model.xml (id-mot-adr-0004) by `just model-docs`. Do not edit: change the model, see docs/adr/template.md. -->
# 0004. Agent team with cost-aware model routing

- Status: Accepted
- Date: 2026-11-15
- Issue: #7
- Deciders: product owner, conductor
- ArchiMate elements: `id-app-comp-conductor`, `id-app-comp-hard`, `id-app-comp-scout`,
  `id-app-comp-simple`, `id-mot-goal-cost`, `id-mot-req-routing`

## Context and problem
The product owner wants a conductor that plans and designs, and hands each task to its own worker,
while keeping development cost under control: expensive models only where their reasoning pays off.
Per million tokens, Fable 5.2 costs 2× Opus 5.5, 4× Sonnet 5.5 and 80× Haiku 5.5
(tools/model-prices.toml).

## Decision drivers
- Cost per *completed* task, not per request: a cheap worker that fails and retries is not cheap.
- Routing must be explicit and auditable (who decided, why), not a hidden heuristic.
- Spend must be measurable per task and per model, so the routing rule can be tuned with data.

## Decision
- **Roles and pinned models** (exact IDs, never aliases): conductor `claude-fable-5-2` (main
  session, `.claude/settings.json`); `scout` Haiku 5.5 (read-only search); `implementer-simple`
  Sonnet 5.5; `implementer-hard` Opus 5.5; `architect` Opus 5.5; `reviewer` Sonnet 5.5, Opus for
  hard PRs. Implementers and the architect work in isolated git worktrees.
- **Routing rule**: `complexity:simple` only if the task has clear acceptance criteria, touches one
  crate and needs no design decision; else `complexity:hard`. The reason is written on the issue.
  When in doubt: hard.
- **Escalation**: the simple worker stops after its second failed `just check` (or on finding the
  task mislabelled) and reports `ESCALATE`; the conductor labels the issue `escalated`, comments the
  reason and hands the branch to the hard worker.
- **Lifecycle skills**: `/plan-epic`, `/split-tasks`, `/implement`, `/review`, with the human gates
  built in (plan approval, merge).
- **Cost measurement** (`just cost`): parse Claude Code's local transcripts, de-duplicated per API
  response, priced from `tools/model-prices.toml`. Tasks are identified by the worker launch
  description, which must start with `#<issue>`.

## Consequences
- Good: the conductor's expensive context is spent on planning and judgement; reading goes to Haiku
  (a scout answer cost $0.003 in testing) and routine code to Sonnet.
- Good: validated against Claude Code's own accounting: the report matched its per-model cost
  figures to the cent.
- Bad: a new conductor session costs about $1 to start (≈57K tokens of context written to the cache
  on Fable); keep conductor sessions long-lived rather than starting many.
- Bad: the transcript format is documented as internal and may change. The report stops with an
  error if required fields disappear. Upgrade path: Claude Code's OpenTelemetry metrics
  (`claude_code.cost.usage`, `claude_code.token.usage`).
- Lesson recorded: the `fable` alias resolved to Fable 5.1 (25% more expensive than 5.2) in testing.
  Pin exact model IDs.
- Follow-up: verify the sub-issue / blocked-by write calls of `scripts/issue-link.sh` on the first
  real `/split-tasks` run (only the read path was exercised in this stage).

## Amendment 2026-11-15: parallel workers
- **What changed**: `/implement` now runs ready tasks in waves of up to 3 concurrent workers, one
  git worktree each, instead of sequentially.
- **Why it is safe**: every worker already has its own worktree and branch; a task joins a wave only
  if it has no open "blocked by" link and shares no crate or file with another task of the wave
  (`/split-tasks` links tasks that edit the same files) or with any task whose PR is still open and
  unmerged. PRs are still reviewed and merged one by one by the human, and each later PR is brought
  up to date with `gh pr update-branch` and re-checked by CI before the merge request.
- **Why a cap of 3**: it limits the cost burst and the number of PRs the human has to review at
  once.
- **Cost effect**: the same total tokens, a shorter wall-clock time, and larger spending bursts.
