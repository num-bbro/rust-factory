#!/usr/bin/env bash
# Stop hook: before an agent hands work back, run the quick gate (format, lint, tests).
#
# * Runs only when Rust code or manifests changed in the working tree (vs HEAD), so plain
#   conversation and doc edits stay fast.
# * On failure: exit 2 with the errors on stderr. Claude Code shows them to the agent, which
#   keeps working until the gate passes.
# * If the agent is already continuing because of this hook (stop_hook_active), it reports but
#   does not block again, so a stuck agent cannot loop forever; the human sees the failure.
set -uo pipefail

input="$(cat)"
active="$(python3 -I -c 'import json,sys; print(json.loads(sys.stdin.read() or "{}").get("stop_hook_active", False))' <<<"$input" 2>/dev/null)"

root="$(git -C "${CLAUDE_PROJECT_DIR:-.}" rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$root" || exit 0

changed="$(git status --porcelain --untracked-files=all | grep -E '\.rs$|Cargo\.(toml|lock)$|clippy\.toml$|rustfmt\.toml$' || true)"
[[ -n "$changed" ]] || exit 0

# `just` and the cargo tools come from mise; hooks may run without the shell's activation.
if command -v mise >/dev/null 2>&1; then RUN=(mise exec --); else RUN=(); fi

if out="$("${RUN[@]}" just check-fast 2>&1)"; then
  exit 0
fi

summary="$(grep -E '^(error|warning)(\[|:)|FAIL \[|panicked at|^Diff in|test result: FAILED|Summary' <<<"$out" | head -40)"
if [[ "$active" == "True" ]]; then
  echo "Quality gate still failing after a retry; leaving it for the human. Run: just check-fast" >&2
  echo "$summary" >&2
  exit 0
fi
{
  echo "Quality gate failed (just check-fast). Fix these before finishing:"
  echo "${summary:-$(tail -40 <<<"$out")}"
} >&2
exit 2
