#!/usr/bin/env bash
# board.sh — put an issue/PR on the factory Project board and set its fields.
#
#   scripts/board.sh <issue-or-pr-url> [Field=Value ...]
#   scripts/board.sh https://github.com/o/r/issues/5 Status="In progress" Complexity=hard Model=opus
#
# Fields are the board's single-select fields: Status, Complexity, Model, Priority, ADM phase.
# Adding an item that is already on the board is a no-op, so this is safe to re-run.
# Board location: env BOARD_OWNER (default: repo owner) and BOARD_NUMBER (default: 1).
set -euo pipefail

URL="${1:?usage: $0 <issue-or-pr-url> [Field=Value ...]}"; shift
OWNER="${BOARD_OWNER:-$(sed -E 's#https://github.com/([^/]+)/.*#\1#' <<<"$URL")}"
NUMBER="${BOARD_NUMBER:-1}"

PROJECT_ID="$(gh project view "$NUMBER" --owner "$OWNER" --format json --jq .id)"
ITEM_ID="$(gh project item-add "$NUMBER" --owner "$OWNER" --url "$URL" --format json --jq .id)"
FIELDS="$(gh project field-list "$NUMBER" --owner "$OWNER" --format json \
          --jq '.fields[] | select(.options) | .name as $f | .id as $fid | .options[] | "\($f)\t\($fid)\t\(.name)\t\(.id)"')"

for kv in "$@"; do
  field="${kv%%=*}"; value="${kv#*=}"
  line="$(awk -F'\t' -v f="$field" -v v="$value" '$1 == f && $3 == v' <<<"$FIELDS")"
  [[ -n "$line" ]] || { echo "unknown field/value: $field=$value" >&2; exit 1; }
  IFS=$'\t' read -r _ fid _ oid <<<"$line"
  gh project item-edit --id "$ITEM_ID" --project-id "$PROJECT_ID" --field-id "$fid" \
    --single-select-option-id "$oid" >/dev/null
done
echo "board: ${URL##*/} ${*:-(added)}"
