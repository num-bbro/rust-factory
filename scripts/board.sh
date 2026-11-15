#!/usr/bin/env bash
# board.sh — put issues/PRs on the factory Project board and set their fields.
#
#   scripts/board.sh <issue-or-pr-url>... [Field=Value ...]
#   scripts/board.sh https://github.com/o/r/issues/5 Status="In progress" Complexity=hard Model=opus
#   scripts/board.sh https://github.com/o/r/issues/5 https://github.com/o/r/pull/6 Status=Released
#
# Fields are the board's single-select fields: Status, Complexity, Model, Priority, ADM phase.
# Adding an item that is already on the board is a no-op, so this is safe to re-run.
# Any number of URLs (same repository) costs a constant five API calls: board, fields, content
# lookup, add, and field updates are each one batched GraphQL request.
# Board location: env BOARD_OWNER (default: repo owner) and BOARD_NUMBER (default: 1).
set -euo pipefail

URLS=(); SETS=()
for arg in "$@"; do
  if [[ "$arg" == https://* ]]; then URLS+=("$arg"); else SETS+=("$arg"); fi
done
(( ${#URLS[@]} )) || { echo "usage: $0 <issue-or-pr-url>... [Field=Value ...]" >&2; exit 2; }
read -r OWNER REPO_NAME < <(sed -E 's#https://github.com/([^/]+)/([^/]+)/.*#\1 \2#' <<<"${URLS[0]}")
BOARD_OWNER="${BOARD_OWNER:-$OWNER}"
NUMBER="${BOARD_NUMBER:-1}"

PROJECT_ID="$(gh project view "$NUMBER" --owner "$BOARD_OWNER" --format json --jq .id)"
FIELDS="$(gh project field-list "$NUMBER" --owner "$BOARD_OWNER" --format json \
          --jq '.fields[] | select(.options) | .name as $f | .id as $fid | .options[] | "\($f)\t\($fid)\t\(.name)\t\(.id)"')"

# Resolve every Field=Value to (field id, option id) before touching anything.
EDITS=()
for kv in "${SETS[@]}"; do
  field="${kv%%=*}"; value="${kv#*=}"
  line="$(awk -F'\t' -v f="$field" -v v="$value" '$1 == f && $3 == v' <<<"$FIELDS")"
  [[ -n "$line" ]] || { echo "unknown field/value: $field=$value" >&2; exit 1; }
  IFS=$'\t' read -r _ fid _ oid <<<"$line"
  EDITS+=("$fid $oid")
done

# 1) content node ids for all issue/PR numbers, one query
q="query { repository(owner: \"$OWNER\", name: \"$REPO_NAME\") {"
for url in "${URLS[@]}"; do
  n="${url##*/}"
  q+=" n$n: issueOrPullRequest(number: $n) { ... on Issue { id } ... on PullRequest { id } }"
done
q+=" } }"
mapfile -t CONTENT < <(gh api graphql -f query="$q" --jq '.data.repository | to_entries[] | "\(.key) \(.value.id)"')

# 2) add all to the board (no-op if present), one mutation -> item ids
m="mutation {"
for c in "${CONTENT[@]}"; do
  read -r key cid <<<"$c"
  m+=" $key: addProjectV2ItemById(input: {projectId: \"$PROJECT_ID\", contentId: \"$cid\"}) { item { id } }"
done
m+=" }"
mapfile -t ITEMS < <(gh api graphql -f query="$m" --jq '.data | to_entries[] | .value.item.id')

# 3) set every field on every item, one mutation
if (( ${#EDITS[@]} )); then
  m="mutation {"; i=0
  for item in "${ITEMS[@]}"; do
    for e in "${EDITS[@]}"; do
      read -r fid oid <<<"$e"
      m+=" e$((i++)): updateProjectV2ItemFieldValue(input: {projectId: \"$PROJECT_ID\", itemId: \"$item\", fieldId: \"$fid\", value: {singleSelectOptionId: \"$oid\"}}) { projectV2Item { id } }"
    done
  done
  m+=" }"
  gh api graphql -f query="$m" >/dev/null
fi
names=(); for url in "${URLS[@]}"; do names+=("${url##*/}"); done
echo "board: ${names[*]} ${SETS[*]:-(added)}"
