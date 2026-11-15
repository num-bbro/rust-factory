#!/usr/bin/env bash
# build.sh — text model → Open Exchange XML → Archi model (.archimate) + HTML report.
#
#   scripts/archimate/build.sh            build into build/architecture/
#   scripts/archimate/build.sh --check    validate the text model only (fast, no Archi needed)
#
# Outputs (not committed; regenerate any time):
#   build/architecture/model.xml          Open Exchange XML (standard, tool-neutral)
#   build/architecture/model.archimate    open this in Archi
#   build/architecture/report/index.html  browsable HTML report with all views
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
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

if [[ "${1:-}" == "--check" ]]; then
  TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
  python3 -I "$ROOT/scripts/archimate/build_exchange.py" "$MODEL_DIR" "$TMP/model.xml" | sed "s|$TMP/||"
  check_doc_refs
  exit
fi
check_doc_refs

[[ -x "$ARCHI" ]] || { echo "Archi $ARCHI_VERSION not found at $ARCHI — run ./bootstrap.sh" >&2; exit 1; }

rm -rf "$OUT"
python3 -I "$ROOT/scripts/archimate/build_exchange.py" "$MODEL_DIR" "$OUT/model.xml"

# Archi is a desktop app even in command-line mode: it needs a display.
# Use the real one if present; otherwise a virtual one (Xvfb), as in CI.
RUN=()
if [[ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
  command -v xvfb-run >/dev/null || { echo "No display and no xvfb-run — run ./bootstrap.sh" >&2; exit 1; }
  RUN=(xvfb-run -a)
fi

# Archi keeps its workspace in ~/.archi by default; use a private one so builds never touch
# (or are confused by) your interactive Archi settings.
"${RUN[@]}" "$ARCHI" -application com.archimatetool.commandline.app -consoleLog -nosplash \
  -data "$OUT/.workspace" \
  --abortOnException \
  --xmlexchange.import "$OUT/model.xml" \
  --saveModel "$OUT/model.archimate" \
  --html.createReport "$OUT/report" \
  2>&1 | grep -v -e 'incubator modules' -e 'no such template: /IGNORE_ERROR_' -e '^\[HTMLReport\] \(Copying\|Creating\|Generating\)' || true

[[ -f "$OUT/model.archimate" && -f "$OUT/report/index.html" ]] || { echo "Archi build failed" >&2; exit 1; }
rm -rf "$OUT/.workspace"
echo "Model:  $OUT/model.archimate"
echo "Report: $OUT/report/index.html"
