#!/usr/bin/env bash
# build.sh — docs/architecture/model.xml (the source, ADR 0009) → Archi model (.archimate) + HTML report.
#
#   scripts/archimate/build.sh            check, build into build/architecture/, then update the
#                                         committed view images docs/architecture/views/
#   scripts/archimate/build.sh --check    check only (fast; reads the relationship rules and the
#                                         exchange schema from the pinned Archi, does not start it)
#
# The checks: canonical form (model_fmt.py --check), the official ArchiMate 3.1 schema (xmllint),
# relationship rules, ID convention, views and their connections, `View` properties, viewpoints,
# document references, generated ADR and TOGAF pages current (gen_docs.py --check), view images
# and views.lock current (views.py --check), and a committed image for each view a TOGAF page
# shows. The build itself brings the images up to date, so before it the last two checks run
# only with --check (gen_docs.py runs with --no-images), and after it they run in full.
# Archi starts only on a file that passed the others, always under Xvfb (PNG bytes depend on the display, ADR 0009 spike item 4), and under a timeout of
# ARCHI_TIMEOUT seconds (default 300): its importer hangs instead of exiting when its own schema
# check fails.
#
# Outputs (not committed; regenerate any time):
#   build/architecture/model.archimate    open this in Archi
#   build/architecture/report/index.html  browsable HTML report with all views
# Committed (views.py --update rewrites a view's image and lock entry only when they are not
# current for the model, so a re-run on another machine changes nothing):
#   docs/architecture/views/<view-id>.png and views.lock
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
if [[ "${1:-}" == "--check" ]]; then
  python3 -I "$SCRIPTS/gen_docs.py" --check "$ROOT" 2>&1 | sed "s|$ROOT/||g" || status=1
  python3 -I "$SCRIPTS/views.py" --check "$ROOT" 2>&1 | sed "s|$ROOT/||g" || status=1
else
  python3 -I "$SCRIPTS/gen_docs.py" --check --no-images "$ROOT" 2>&1 | sed "s|$ROOT/||g" || status=1
fi
(( status == 0 )) || { echo "model check failed: docs/architecture/model.xml" >&2; exit 1; }
[[ "${1:-}" == "--check" ]] && exit 0

[[ -x "$ARCHI" ]] || { echo "Archi $ARCHI_VERSION not found at $ARCHI — run ./bootstrap.sh" >&2; exit 1; }

rm -rf "$OUT"
mkdir -p "$OUT"

# Archi is a desktop app even in command-line mode: it needs a display. Always a virtual one
# (Xvfb), as in CI, even when a real one is present: the PNG bytes depend on the display.
command -v xvfb-run >/dev/null || { echo "No xvfb-run — run ./bootstrap.sh" >&2; exit 1; }
# A Wayland session would win over Xvfb in GTK, so it is hidden from Archi and X11 forced.
RUN=(env -u WAYLAND_DISPLAY GDK_BACKEND=x11 xvfb-run -a)

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
python3 -I "$SCRIPTS/views.py" --update "$ROOT" "$OUT/report" 2>&1 | sed "s|$ROOT/||g"
python3 -I "$SCRIPTS/views.py" --check "$ROOT" 2>&1 | sed "s|$ROOT/||g"
python3 -I "$SCRIPTS/gen_docs.py" --check "$ROOT" 2>&1 | sed "s|$ROOT/||g"
echo "Model:  $OUT/model.archimate"
echo "Report: $OUT/report/index.html"
