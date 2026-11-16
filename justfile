# Software factory task runner. Run `just` to list recipes.
set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

# --- Code quality gates -------------------------------------------------------------------
# `just check` is the full local gate: the same checks CI runs. Fix what it reports; never
# bypass it. `just check-fast` is the quick subset agents run before handing work back.

# Lines-covered threshold (%). main.rs is startup wiring, covered by acceptance tests instead.
coverage_min := "85"
coverage_ignore := "crates/app/src/main.rs"

# Run every gate: format, lint, tests, dependency policy, coverage, architecture model.
check: fmt-check lint test deny coverage model-test model-check
    @echo "✔ all gates passed"

# Quick gate for the edit loop: format, lint, tests.
check-fast: fmt-check lint test

# Format all code in place.
fmt:
    cargo fmt --all

# Fail if any file is not formatted.
fmt-check:
    cargo fmt --all --check

# Clippy with the workspace lint set; any warning fails.
lint:
    cargo clippy --workspace --all-targets --locked -- -D warnings

# Run all tests (unit, property, HTTP, architecture rules). Acceptance tests need a running
# service and have their own recipe: just acceptance
test *args:
    cargo nextest run --workspace --exclude acceptance-tests --locked {{args}}

# Dependency policy: vulnerabilities, licenses, sources (deny.toml).
deny:
    cargo deny --log-level error check

# Line coverage, failing below the threshold. HTML report: just coverage-html
coverage:
    cargo llvm-cov nextest --workspace --exclude acceptance-tests --locked --summary-only \
      --ignore-filename-regex '{{coverage_ignore}}' --fail-under-lines {{coverage_min}}

# Open a browsable coverage report.
coverage-html:
    cargo llvm-cov nextest --workspace --exclude acceptance-tests --locked --ignore-filename-regex '{{coverage_ignore}}' --open

# Mutation testing: are the tests really testing? Slow; pass e.g. `-p domain` to narrow it.
mutants *args:
    cargo mutants --workspace {{args}}

# Mutation-test only the code changed against main (what CI will run on PRs).
mutants-diff base="origin/main":
    git diff {{base}} > target/mutants.diff
    cargo mutants --workspace --in-diff target/mutants.diff

# Run the service locally (PORT defaults to 8080).
run:
    cargo run -p app

# --- Release image & acceptance -------------------------------------------------------------

image_name := "localhost/rust-factory"

# Build the release image (Docker format, so the HEALTHCHECK is kept). Extra podman flags can be
# passed in IMAGE_BUILD_FLAGS (e.g. "--network host" where rootless networking is unavailable).
image tag="dev":
    podman build --format docker {{env_var_or_default("IMAGE_BUILD_FLAGS", "")}} \
      --build-arg VERSION={{tag}} -t {{image_name}}:{{tag}} -f Dockerfile .

# Run the acceptance tests against a container of the given image, then check the container's
# health check and graceful shutdown. Default: build and test the local dev image.
acceptance image=(image_name + ":dev"):
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "{{image}}" == "{{image_name}}:dev" ]]; then just image dev; fi
    port=$(python3 -I -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')
    name="acceptance-$port"
    # Host networking: no port mapping or tun device needed; the service listens on $port.
    podman run -d --name "$name" --network host -e PORT="$port" "{{image}}" >/dev/null
    trap 'podman rm -f "$name" >/dev/null 2>&1 || true' EXIT
    echo "service under test: {{image}} on http://127.0.0.1:$port"
    ACCEPTANCE_BASE_URL="http://127.0.0.1:$port" ACCEPTANCE_REQUIRED=1 \
      cargo test --locked -p acceptance-tests --test acceptance
    just api-check "http://127.0.0.1:$port"
    echo "container health check (/app healthcheck inside the image):"
    podman healthcheck run "$name" && echo "  healthy"
    echo "graceful shutdown on SIGTERM (what podman stop sends):"
    podman stop -t 10 "$name" >/dev/null
    code=$(podman inspect "$name" --format '{{{{.State.ExitCode}}')
    podman logs "$name" 2>&1 | grep -q 'stopped' && [[ "$code" == 0 ]] \
      && echo "  stopped cleanly (exit code 0)" \
      || { echo "  did not shut down cleanly (exit code $code)"; podman logs "$name"; exit 1; }

# Check that a running service answers as docs/api/openapi.yaml says (ADR 0010). Fixed seed and
# deterministic generation: the same requests on every run. The tool currently ignores the seed in
# deterministic mode; the flag is kept as ADR 0010 fixes it.
api-check base_url:
    st --config-file docs/api/schemathesis.toml run docs/api/openapi.yaml --url {{base_url}} \
      --seed 1 --generation-deterministic --no-color

# Cut a release: tag vVERSION on an up-to-date, clean main. The Release workflow then builds,
# accepts and publishes the image. Bump [workspace.package] version in Cargo.toml via a PR first.
release version:
    #!/usr/bin/env bash
    set -euo pipefail
    git fetch -q origin main --tags
    [[ "$(git branch --show-current)" == main ]] || { echo "switch to main first"; exit 1; }
    [[ -z "$(git status --porcelain)" ]] || { echo "working tree not clean"; exit 1; }
    [[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]] || { echo "main is not up to date with origin (git pull)"; exit 1; }
    current=$(python3 -I -c 'import tomllib; print(tomllib.load(open("Cargo.toml","rb"))["workspace"]["package"]["version"])')
    [[ "{{version}}" == "$current" ]] || { echo "Cargo.toml says $current; bump it in a PR first"; exit 1; }
    git rev-parse -q --verify "refs/tags/v{{version}}" >/dev/null && { echo "v{{version}} already exists"; exit 1; }
    git tag -a "v{{version}}" -m "Release v{{version}}"
    git push origin "v{{version}}"
    echo "Tagged v{{version}}. Follow the release: gh run watch \$(gh run list --workflow Release --limit 1 --json databaseId --jq '.[0].databaseId')"

# --- Deploy: pilot, then production (see deploy/ and ADR 0006) ----------------------------------

# Deploy a released version (or a test image) to an environment, with health check and rollback.
deploy env version:
    scripts/deploy.sh deploy {{env}} {{version}}

# HUMAN GATE 3: promote a version that is healthy on the pilot to production, one host at a time.
promote version:
    scripts/deploy.sh promote {{version}}

# What runs where, and is it healthy?
deploy-status env="":
    scripts/deploy.sh status {{env}}

# --- Agent team -----------------------------------------------------------------------------

# Agent spend per model, agent and task (estimate at API list price). e.g. just cost --issue 42
cost *args:
    python3 -I scripts/cost-report.py {{args}}

# --- Factory setup ----------------------------------------------------------------------------

# Prepare this machine (Arch or Ubuntu/WSL). Safe to re-run. Pass --dry-run to preview.
bootstrap *args:
    ./bootstrap.sh {{args}}

# Make the GitHub repo's labels match .github/labels.txt. Pass --prune to delete others.
labels *args:
    scripts/sync-labels.sh {{args}}

# Create or update the GitHub Project board for a repo (default: this one).
project repo="num-bbro/rust-factory" title="":
    scripts/setup-project.sh {{repo}} {{title}}

# Check docs/architecture/model.xml, build build/architecture/model.archimate + report/index.html (Archi under Xvfb), then update the committed view images docs/architecture/views/*.png and views.lock where a view changed. Commit docs/architecture/views/ afterwards.
model:
    scripts/archimate/build.sh

# Check docs/architecture/model.xml: canonical form, official schema, relationship rules, IDs, views, doc references, generated ADR and TOGAF pages and view images current (fast; reads the rules and schema from the pinned Archi install, does not start Archi).
model-check:
    scripts/archimate/build.sh --check

# Write the ADR pages docs/adr/NNNN-*.md and docs/adr/README.md and the TOGAF pages docs/togaf/*.md (with their diagrams and catalogs) and docs/togaf/README.md from the model (ADR 0009). Never edit them by hand.
model-docs:
    python3 -I scripts/archimate/gen_docs.py

# Put an ArchiMate exchange file in canonical form and lay out its views (ADR 0009); --check only
# reports. Default file: docs/architecture/model.xml.
[positional-arguments]
model-fmt *args:
    python3 -I scripts/archimate/model_fmt.py "$@"

# Unit tests of the architecture model scripts (standard-library unittest, fixtures in tests/).
model-test:
    python3 -I -m unittest discover -s scripts/archimate/tests -t scripts/archimate/tests

# Compare the dimensions of the view PNGs rendered by the last `just model` (build/) with docs/architecture/views/views.lock; CI runs it after its own build.
model-dims:
    python3 -I scripts/archimate/views.py --dims . build/architecture/report

# Build the model, then open the HTML report in your browser.
model-report: model
    xdg-open build/architecture/report/index.html >/dev/null 2>&1 &

# Show every factory tool's version and flag anything missing.
doctor:
    #!/usr/bin/env bash
    set -uo pipefail
    fail=0
    check() {  # check NAME VERSION-COMMAND...
      local name=$1; shift
      if out=$("$@" 2>/dev/null | head -1) && [[ -n $out ]]; then
        printf '  \033[32m✔\033[0m %-15s %s\n' "$name" "$out"
      else
        printf '  \033[31m✘\033[0m %-15s missing — run ./bootstrap.sh\n' "$name"; fail=1
      fi
    }
    echo "Toolchain"
    check rustc          rustc --version
    check cargo          cargo --version
    check rustfmt        rustfmt --version
    check clippy         cargo clippy --version
    check llvm-tools     bash -c 'ls "$(rustc --print sysroot)"/lib/rustlib/*/bin/llvm-profdata >/dev/null && echo present'
    echo "Factory tools"
    check just           just --version
    check mise           mise --version
    check cargo-binstall cargo binstall -V
    check cargo-nextest  cargo nextest --version
    check cargo-deny     cargo deny --version
    check cargo-llvm-cov cargo llvm-cov --version
    check cargo-mutants  cargo mutants --version
    check uv             uv --version
    check schemathesis   st --version
    echo "Platform"
    check git            git --version
    check gh             gh --version
    check podman         podman --version
    check claude         claude --version
    echo "Architecture"
    check python3        python3 --version
    check archi          bash -c '. tools/archi.env; f="${ARCHI_HOME:-$HOME/.local/opt/archi-$ARCHI_VERSION}/Archi"; [[ -x $f ]] && echo "Archi $ARCHI_VERSION ($f)"'
    check xvfb-run       bash -c 'command -v xvfb-run'
    check xmllint        bash -c 'command -v xmllint >/dev/null && xmllint --version 2>&1 | head -1'
    if gh auth status >/dev/null 2>&1; then
      printf '  \033[32m✔\033[0m %-15s %s\n' "github login" "ok"
    else
      printf '  \033[33m!\033[0m %-15s %s\n' "github login" "not logged in — run: gh auth login"
    fi
    exit $fail
