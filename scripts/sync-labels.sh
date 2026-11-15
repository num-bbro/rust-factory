#!/usr/bin/env bash
# sync-labels.sh — make a GitHub repo's labels match .github/labels.txt.
#
#   scripts/sync-labels.sh                 create/update labels in the current repo
#   scripts/sync-labels.sh --prune         also delete labels that are not in the file
#   scripts/sync-labels.sh --repo o/r      target another repo (e.g. a project made from this template)
#
# Safe to re-run: existing labels are updated in place, so issues keep their labels.
set -euo pipefail

PRUNE=0
REPO_ARGS=()
while (( $# )); do
  case "$1" in
    --prune) PRUNE=1 ;;
    --repo)  REPO_ARGS=(--repo "$2"); shift ;;
    *) echo "usage: $0 [--prune] [--repo owner/name]" >&2; exit 2 ;;
  esac
  shift
done

FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.github/labels.txt"
declare -A WANT=()
trim() { local s="$1"; s="${s#"${s%%[![:space:]]*}"}"; printf '%s' "${s%"${s##*[![:space:]]}"}"; }

while IFS='|' read -r name color desc; do
  name="$(trim "$name")"; color="$(trim "$color")"; desc="$(trim "$desc")"
  [[ -z "$name" || "$name" == \#* ]] && continue
  WANT["$name"]=1
  gh label create "$name" --color "$color" --description "$desc" --force "${REPO_ARGS[@]}" >/dev/null
  echo "  ok    $name"
done < "$FILE"

if (( PRUNE )); then
  while read -r existing; do
    [[ -z "$existing" || -n "${WANT[$existing]:-}" ]] && continue
    gh label delete "$existing" --yes "${REPO_ARGS[@]}" >/dev/null
    echo "  del   $existing"
  done < <(gh label list --limit 200 --json name --jq '.[].name' "${REPO_ARGS[@]}")
fi
echo "${#WANT[@]} labels in sync."
