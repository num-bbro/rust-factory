# Software factory task runner. Run `just` to list recipes.
set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

# Prepare this machine (Arch or Ubuntu/WSL). Safe to re-run. Pass --dry-run to preview.
bootstrap *args:
    ./bootstrap.sh {{args}}

# Make the GitHub repo's labels match .github/labels.txt. Pass --prune to delete others.
labels *args:
    scripts/sync-labels.sh {{args}}

# Create or update the GitHub Project board for a repo (default: this one).
project repo="num-bbro/rust-factory" title="":
    scripts/setup-project.sh {{repo}} {{title}}

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
    if gh auth status >/dev/null 2>&1; then
      printf '  \033[32m✔\033[0m %-15s %s\n' "github login" "ok"
    else
      printf '  \033[33m!\033[0m %-15s %s\n' "github login" "not logged in — run: gh auth login"
    fi
    exit $fail
