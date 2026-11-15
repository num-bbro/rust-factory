#!/usr/bin/env bash
# build.sh — text model → Open Exchange XML → Archi model (.archimate) + HTML report.
#
#   scripts/archimate/build.sh            build into build/architecture/
#   scripts/archimate/build.sh --check    validate the text model only (fast; reads the relationship rules
#                                         and the exchange schema from the pinned Archi, does not start it)
#
# Both validate the generated exchange XML against the official ArchiMate 3.1 schema (xmllint);
# --check also puts it in the canonical form of ADR 0009 (model_fmt.py) and checks that formatting
# again changes nothing. Archi itself runs under a timeout of ARCHI_TIMEOUT seconds (default 300):
# its importer hangs instead of exiting when its own schema check fails.
#
# Outputs (not committed; regenerate any time):
#   build/architecture/model.xml          Open Exchange XML (standard, tool-neutral)
#   build/architecture/model.archimate    open this in Archi
#   build/architecture/report/index.html  browsable HTML report with all views
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPTS="$ROOT/scripts/archimate"
MODEL_DIR="$ROOT/docs/architecture/model"
OUT="$ROOT/build/architecture"
# shellcheck disable=SC1091
. "$ROOT/tools/archi.env"
ARCHI="${ARCHI_HOME:-$HOME/.local/opt/archi-$ARCHI_VERSION}/Archi"

# Every `id-...` mentioned in the TOGAF documents and ADRs must exist in the model,
# so the narrative and the model cannot silently drift apart.
check_doc_refs() {
  local known missing=0 ref
  known="$(cut -d, -f1 "$MODEL_DIR"/{elements,relations,views}.csv | tr -d '"')"
  while read -r ref; do
    if ! grep -Fxq "$ref" <<<"$known"; then
      echo "  - $ref is mentioned in docs but not in the model:" >&2
      grep -rln --include='*.md' -- "\`$ref\`" "$ROOT/docs" | sed "s|$ROOT/|      |" >&2
      missing=1
    fi
  done < <(grep -rhoE --include='*.md' '`id-[a-z0-9-]+`' "$ROOT/docs" | tr -d '`' | sort -u)
  (( missing == 0 )) && echo "docs: all element references resolve"
  return $missing
}

# Every relationship must be allowed by ArchiMate between its two element types. The rules are
# read from the pinned Archi install, not copied into the repo.
check_relationships() {
  python3 -I "$SCRIPTS/check_relationships.py" "$MODEL_DIR" \
    "${ARCHI_HOME:-$HOME/.local/opt/archi-$ARCHI_VERSION}"
}

if [[ "${1:-}" == "--check" ]]; then
  TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
  python3 -I "$SCRIPTS/build_exchange.py" "$MODEL_DIR" "$TMP/model.xml" | sed "s|$TMP/||"
  check_doc_refs
  check_relationships
  # The exchange-model tooling of ADR 0009, exercised on today's model before the cutover:
  # canonical form, idempotent formatting, official schema.
  python3 -I "$SCRIPTS/model_fmt.py" "$TMP/model.xml" 2>&1 | sed "s|$TMP/||"
  python3 -I "$SCRIPTS/model_fmt.py" --check "$TMP/model.xml" 2>&1 | sed "s|$TMP/||"
  python3 -I "$SCRIPTS/xsd_check.py" "$TMP/model.xml" 2>&1 | sed "s|$TMP/||"
  exit
fi
check_doc_refs

[[ -x "$ARCHI" ]] || { echo "Archi $ARCHI_VERSION not found at $ARCHI — run ./bootstrap.sh" >&2; exit 1; }

rm -rf "$OUT"
python3 -I "$SCRIPTS/build_exchange.py" "$MODEL_DIR" "$OUT/model.xml"
# Start Archi only on a schema-valid file (Archi hangs when its own schema check fails).
python3 -I "$SCRIPTS/xsd_check.py" "$OUT/model.xml"

# Archi is a desktop app even in command-line mode: it needs a display.
# Use the real one if present; otherwise a virtual one (Xvfb), as in CI.
RUN=()
if [[ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
  command -v xvfb-run >/dev/null || { echo "No display and no xvfb-run — run ./bootstrap.sh" >&2; exit 1; }
  RUN=(xvfb-run -a)
fi

# Archi keeps its workspace in ~/.archi by default; use a private one so builds never touch
# (or are confused by) your interactive Archi settings. The timeout runs inside xvfb-run, so it
# stops Archi itself and xvfb-run then cleans up its display.
ARCHI_TIMEOUT="${ARCHI_TIMEOUT:-300}"
set +e
"${RUN[@]}" timeout --kill-after=10 "$ARCHI_TIMEOUT" "$ARCHI" \
  -application com.archimatetool.commandline.app -consoleLog -nosplash \
  -data "$OUT/.workspace" \
  --abortOnException \
  --xmlexchange.import "$OUT/model.xml" \
  --saveModel "$OUT/model.archimate" \
  --html.createReport "$OUT/report" \
  2>&1 | grep -v -e 'incubator modules' -e 'no such template: /IGNORE_ERROR_' -e '^\[HTMLReport\] \(Copying\|Creating\|Generating\)'
archi_status=${PIPESTATUS[0]}
set -e
if (( archi_status == 124 || archi_status == 137 )); then
  echo "Archi did not finish within ${ARCHI_TIMEOUT}s and was stopped (set ARCHI_TIMEOUT to allow longer)" >&2
  exit 1
fi

[[ -f "$OUT/model.archimate" && -f "$OUT/report/index.html" ]] || { echo "Archi build failed" >&2; exit 1; }
rm -rf "$OUT/.workspace"
echo "Model:  $OUT/model.archimate"
echo "Report: $OUT/report/index.html"
