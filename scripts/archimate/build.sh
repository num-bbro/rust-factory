#!/usr/bin/env bash
# build.sh — docs/architecture/model.xml (the source, ADR 0009) → Archi model (.archimate) + HTML report.
#
#   scripts/archimate/build.sh            check, then build into build/architecture/
#   scripts/archimate/build.sh --check    check only (fast; reads the relationship rules and the
#                                         exchange schema from the pinned Archi, does not start it)
#
# The checks: canonical form (model_fmt.py --check), the official ArchiMate 3.1 schema (xmllint),
# relationship rules, ID convention, views and their connections, `View` properties, viewpoints,
# document references. Archi starts only on a file that passed them, and runs under a timeout of
# ARCHI_TIMEOUT seconds (default 300): its importer hangs instead of exiting when its own schema
# check fails.
#
# Outputs (not committed; regenerate any time):
#   build/architecture/model.archimate    open this in Archi
#   build/architecture/report/index.html  browsable HTML report with all views
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPTS="$ROOT/scripts/archimate"
MODEL="$ROOT/docs/architecture/model.xml"
OUT="$ROOT/build/architecture"
# shellcheck disable=SC1091
. "$ROOT/tools/archi.env"
ARCHI_DIR="${ARCHI_HOME:-$HOME/.local/opt/archi-$ARCHI_VERSION}"
ARCHI="$ARCHI_DIR/Archi"

# Run every check and report all of them, then fail if any failed.
status=0
python3 -I "$SCRIPTS/model_fmt.py" --check "$MODEL" 2>&1 | sed "s|$ROOT/||g" || status=1
python3 -I "$SCRIPTS/xsd_check.py" "$MODEL" 2>&1 | sed "s|$ROOT/||g" || status=1
python3 -I "$SCRIPTS/check_relationships.py" "$MODEL" "$ARCHI_DIR" 2>&1 | sed "s|$ROOT/||g" || status=1
python3 -I "$SCRIPTS/check_model.py" "$MODEL" "$ROOT/docs" "$ARCHI_DIR" 2>&1 | sed "s|$ROOT/||g" || status=1
(( status == 0 )) || { echo "model check failed: docs/architecture/model.xml" >&2; exit 1; }
[[ "${1:-}" == "--check" ]] && exit 0

[[ -x "$ARCHI" ]] || { echo "Archi $ARCHI_VERSION not found at $ARCHI — run ./bootstrap.sh" >&2; exit 1; }

rm -rf "$OUT"
mkdir -p "$OUT"

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
  --xmlexchange.import "$MODEL" \
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
