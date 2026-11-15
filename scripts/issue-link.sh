#!/usr/bin/env bash
# issue-link.sh — GitHub issue relationships the conductor uses for planning.
#
#   scripts/issue-link.sh sub <parent#> <child#>          make child a sub-issue (story→task, epic→story)
#   scripts/issue-link.sh blocked-by <issue#> <blocker#>  record "issue is blocked by blocker"
#   scripts/issue-link.sh open-blockers <issue#>          print open blockers (empty = ready to start)
#
# Works on the repo of the current directory (or GH_REPO). GitHub's link endpoints need the
# internal issue id, not the number; this script translates.
set -euo pipefail

REPO="${GH_REPO:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}"
id_of() { gh api "repos/$REPO/issues/$1" --jq .id; }

case "${1:-}" in
  sub)
    gh api -X POST "repos/$REPO/issues/$2/sub_issues" -F sub_issue_id="$(id_of "$3")" >/dev/null
    echo "#$3 is now a sub-issue of #$2"
    ;;
  blocked-by)
    gh api -X POST "repos/$REPO/issues/$2/dependencies/blocked_by" -F issue_id="$(id_of "$3")" >/dev/null
    echo "#$2 is now blocked by #$3"
    ;;
  open-blockers)
    gh api "repos/$REPO/issues/$2/dependencies/blocked_by" \
      --jq '.[] | select(.state == "open") | "#\(.number) \(.title)"'
    ;;
  *)
    sed -n '2,8p' "$0" >&2
    exit 2
    ;;
esac
