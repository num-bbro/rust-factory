#!/usr/bin/env bash
# setup-project.sh — create (or update) the factory's GitHub Project board for a repo.
#
#   scripts/setup-project.sh <owner/repo> [project title]
#
# Safe to re-run: finds the project by title, adds only missing fields, and replaces the
# Status options only if they differ (replacing them would clear existing items' statuses).
# Needs the gh "project" permission:  gh auth refresh -s project
set -euo pipefail

REPO="${1:?usage: $0 <owner/repo> [project title]}"
OWNER="${REPO%%/*}"
TITLE="${2:-${REPO#*/}}"

ok()   { printf '  \033[32mok\033[0m    %s\n' "$*"; }
todo() { printf '  \033[33mdo\033[0m    %s\n' "$*"; }

# --- Status columns: the factory lifecycle ---------------------------------
# name | color | meaning
STATUS=(
  "Backlog|GRAY|Captured, not yet refined"
  "Ready|BLUE|Refined: acceptance criteria clear, dependencies known"
  "In progress|YELLOW|A worker is on it (branch + worktree exist)"
  "In review|ORANGE|PR open, gates running, waiting for human merge"
  "Accepted|GREEN|Merged and acceptance tests pass on the release build"
  "Piloted|PURPLE|Running on the pilot environment"
  "Released|PINK|Rolled out to production"
)

# --- Extra single-select fields ---------------------------------------------
declare -A FIELDS=(
  [Complexity]="simple,hard"
  [Model]="fable,opus,sonnet,haiku,human"
  [Priority]="Must,Should,Could,Won't"
  ["ADM phase"]="Preliminary,A Vision,B Business,C Information Systems,D Technology,E Opportunities & Solutions,F Migration Planning,G Implementation Governance,H Change Management,Requirements Management"
)

# --- Project ----------------------------------------------------------------
NUMBER="$(gh project list --owner "$OWNER" --limit 100 --format json \
          --jq ".projects[] | select(.title == \"$TITLE\") | .number" | head -1)"
if [[ -n "$NUMBER" ]]; then
  ok "project '$TITLE' exists (#$NUMBER)"
else
  todo "create project '$TITLE'"
  NUMBER="$(gh project create --owner "$OWNER" --title "$TITLE" --format json --jq .number)"
fi
PROJECT_URL="$(gh project view "$NUMBER" --owner "$OWNER" --format json --jq .url)"

# Link it to the repo so it shows in the repo's Projects tab (no-op if already linked).
gh project link "$NUMBER" --owner "$OWNER" --repo "$REPO" >/dev/null 2>&1 || true
ok "linked to $REPO"

# fields JQ-FILTER — query the project's fields with gh's built-in jq (no jq install needed).
fields() { gh project field-list "$NUMBER" --owner "$OWNER" --limit 100 --format json --jq "$1"; }

# --- Status options ------------------------------------------------------------
STATUS_ID="$(fields '.fields[] | select(.name == "Status") | .id')"
HAVE="$(fields '[.fields[] | select(.name == "Status") | .options[].name] | join("|")')"
WANT="$(printf '%s\n' "${STATUS[@]}" | cut -d'|' -f1 | paste -sd'|')"
if [[ "$HAVE" == "$WANT" ]]; then
  ok "Status columns: ${WANT//|/ → }"
else
  todo "set Status columns: ${WANT//|/ → }"
  OPTS=""
  for s in "${STATUS[@]}"; do
    IFS='|' read -r name color desc <<<"$s"
    OPTS+="{name: \"$name\", color: $color, description: \"$desc\"},"
  done
  gh api graphql -f field="$STATUS_ID" -f query="
    mutation(\$field: ID!) {
      updateProjectV2Field(input: {fieldId: \$field, singleSelectOptions: [${OPTS%,}]}) {
        projectV2Field { ... on ProjectV2SingleSelectField { name } }
      }
    }" >/dev/null
fi

# --- Extra fields ---------------------------------------------------------------
EXISTING="$(fields '.fields[].name')"
for f in "Complexity" "Model" "Priority" "ADM phase"; do
  if grep -Fxq "$f" <<<"$EXISTING"; then
    ok "field '$f'"
  else
    todo "add field '$f'"
    gh project field-create "$NUMBER" --owner "$OWNER" --name "$f" \
      --data-type SINGLE_SELECT --single-select-options "${FIELDS[$f]}" >/dev/null
  fi
done

echo "Project: $PROJECT_URL"
