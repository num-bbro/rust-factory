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
check: fmt-check lint test deny coverage model-check
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

# Run all tests (unit, property, HTTP, architecture rules).
test *args:
    cargo nextest run --workspace --locked {{args}}

# Dependency policy: vulnerabilities, licenses, sources (deny.toml).
deny:
    cargo deny --log-level error check

# Line coverage, failing below the threshold. HTML report: just coverage-html
coverage:
    cargo llvm-cov nextest --workspace --locked --summary-only \
      --ignore-filename-regex '{{coverage_ignore}}' --fail-under-lines {{coverage_min}}

# Open a browsable coverage report.
coverage-html:
    cargo llvm-cov nextest --workspace --locked --ignore-filename-regex '{{coverage_ignore}}' --open

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

# Build the ArchiMate model: text → build/architecture/model.archimate + report/index.html
model:
    scripts/archimate/build.sh

# Validate the ArchiMate text model and doc references only (fast, no Archi needed).
model-check:
    scripts/archimate/build.sh --check

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
    echo "Platform"
    check git            git --version
    check gh             gh --version
    check podman         podman --version
    check claude         claude --version
    echo "Architecture"
    check python3        python3 --version
    check archi          bash -c '. tools/archi.env; f="${ARCHI_HOME:-$HOME/.local/opt/archi-$ARCHI_VERSION}/Archi"; [[ -x $f ]] && echo "Archi $ARCHI_VERSION ($f)"'
    check xvfb-run       bash -c 'command -v xvfb-run'
    if gh auth status >/dev/null 2>&1; then
      printf '  \033[32m✔\033[0m %-15s %s\n' "github login" "ok"
    else
      printf '  \033[33m!\033[0m %-15s %s\n' "github login" "not logged in — run: gh auth login"
    fi
    exit $fail
