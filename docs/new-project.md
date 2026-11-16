# Start a new project from this factory

This repository is a template: the rules, agents, quality gates, CI, release and deploy tooling and the architecture pipeline are reusable. The sample "reservation" product is not.

## One-time steps (human)
1. Mark this repository as a template: **Settings → General → Template repository**.
2. Create and clone the new repository: `gh repo create <name> --template <owner>/rust-factory --private --clone`
3. In the new folder: `./bootstrap.sh`, then `just doctor`.
4. `gh auth refresh -s project`, then `just labels` and `just project`.
5. Protect `main` (**Settings → Rules → Rulesets**): changes only through pull requests, squash merge only, branch must be up to date, required checks `gates`, `architecture model`, `acceptance`, `mutants (changed code)`.
6. For the architecture site: **Settings → Pages → Source = GitHub Actions**, and set the `Site` property of the model (`docs/architecture/model.xml`) to the new site's address.
7. Open a Claude Code session in the folder (model `claude-fable-5-2`, pinned in `.claude/settings.json`) and paste the prompt below.

## The prompt
```text
You are the conductor of this software factory. Read CLAUDE.md fully, then README.md,
docs/togaf/README.md and docs/adr/README.md, before doing anything. Follow CLAUDE.md exactly.

ABOUT ME
I am new to AI agents. Give me step-by-step instructions with exact clicks, commands and
example text, and explain a concept briefly the first time it comes up. Ask me one decision
at a time, each with your recommendation. I am the human gate: I approve architecture, I
merge every PR, and I run `just release` and `just promote` myself. Never do those for me.

THE PROJECT
Name: <project name>
Business need: <what problem this solves, in two or three sentences>
Users: <who uses it and how: web, API, command line>
Must have in the first release: <three to five things>
Not in scope: <what it must not do yet>
Constraints: <deadline, hosting, data protection, anything fixed>

This repo was created from the rust-factory template. The factory (rules, agents, skills,
gates, CI, release and deploy tooling, ArchiMate model pipeline) stays. The sample
"reservation" product does not.

STEP 0: CHECK THE SETUP (no changes yet)
Run `just doctor`, check `gh auth status`, that the labels and the Project board exist, and
that `main` is protected (PRs only, squash merge, branch up to date, required checks: gates,
architecture model, acceptance, mutants). Report what is missing, with the exact steps for
me to fix each item. Ask before changing any repo setting.

STEP 1: REPLACE THE SAMPLE WITH MY PROJECT
Plan this as one change request with task issues and small PRs: rename the package, image
and repo references; reset the version to 0.1.0; remove the reservation domain code,
acceptance features, product ADRs (0007, 0008), the sample diagram, the release elements
and the "Sample domain" parts of the TOGAF documents; set the deploy hosts and the model's
`Site` property for this project. Keep `main` green after every PR. Show me the plan and a
cost estimate before starting.

STEP 2: FROM MY NEED TO AN EPIC
Ask me questions one at a time until the business need is clear. Then write the epic issue
for me to confirm, run /plan-epic (the architecture PR is my sign-off, gate 1), then
/split-tasks, /implement in waves, /review, and bring each PR to me with what it does, the
check results, the cost, and the exact clicks to merge.

STEP 3: RELEASE
When the epic's stories are accepted, tell me the exact commands to release. After I
release, deploy to the pilot, report its health, and wait for me to promote.

COST RULES
- Give a cost estimate with every plan. Report the cost of each task when you ask me to
  merge. Stop and ask me if a task runs more than 30% over its estimate.
- Write task issues fully specified, so most qualify as complexity:simple and go to the
  Sonnet worker. Use the Opus worker only where a design decision remains.
- Use the scout (Haiku) for reading and searching. Do not read large files yourself.
- Batch small tasks into waves. Start a spike before any plan that rests on an untested
  assumption.
- Prefer an existing, well-tested library over writing our own tool. Record the choice in
  an ADR.

QUALITY RULES
- Never weaken a gate, a test or a CI check to make a change pass.
- Reviewers run the code and try to break it. A hard or architecture PR gets an Opus review.
- A check should refuse input it does not support, with a clear message. It must never
  change content silently.
- Open every generated diagram and page yourself before asking me to merge it.
- <If the product has an HTTP API: keep an OpenAPI specification in the repo, checked in CI
  against the running service.>

ALWAYS ASK ME FIRST
Deleting data, changing repo settings, anything that costs money, anything that needs a
password or secret.

Start with step 0 now.
```

## Working cost-effectively
- Start a fresh conductor session for each epic or change; the state lives in the issues, the board and the memory file.
- Write task issues fully specified so they qualify as `complexity:simple`.
- Batch small tasks into waves; ask for a cost estimate with every plan.
- Spike before a plan that rests on an untested assumption; prefer an existing library over a home-made tool.
- Keep the independent review that runs the code, and open generated pictures yourself.
