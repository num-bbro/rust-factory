#!/usr/bin/env bash
# bootstrap.sh — prepare an Arch Linux or Ubuntu (incl. WSL) machine for the Rust software factory.
#
# Safe to re-run: every step checks first and acts only when something is missing.
# A second run on a ready machine reports "0 changes".
#
#   ./bootstrap.sh            install what is missing (asks for sudo only if OS packages are missing)
#   ./bootstrap.sh --dry-run  show what would change, change nothing
#
# Layers:
#   1. OS packages   (pacman on Arch, apt on Ubuntu)  — compilers, podman, gh, mise
#   2. Rust          (rustup + the toolchain pinned in rust-toolchain.toml)
#   3. Dev tools     (mise installs the versions pinned in mise.toml: just, cargo-* tools)
#   4. Shell hook    (mise activation in your shell rc file)
set -euo pipefail

DRY_RUN=0
case "${1:-}" in
  --dry-run) DRY_RUN=1 ;;
  "") ;;
  *) echo "usage: $0 [--dry-run]" >&2; exit 2 ;;
esac

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHANGES=0
# rustup would otherwise silently download the toolchain from rust-toolchain.toml the moment
# any rustup/cargo command runs in this folder — even during --dry-run. Installs stay explicit.
export RUSTUP_AUTO_INSTALL=0

log()  { printf '\n\033[1;34m==>\033[0m \033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mok\033[0m    %s\n' "$*"; }
todo() { printf '  \033[33mdo\033[0m    %s\n' "$*"; }
warn() { printf '  \033[35mwarn\033[0m  %s\n' "$*"; }
die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# run CMD...  — execute a change (or only print it with --dry-run) and count it.
run() {
  CHANGES=$((CHANGES + 1))
  if (( DRY_RUN )); then
    printf '        (dry-run) %s\n' "$*"
  else
    "$@"
  fi
}

have() { command -v "$1" >/dev/null 2>&1; }

# ---------------------------------------------------------------------------
log "Detecting platform"
[[ -r /etc/os-release ]] || die "/etc/os-release not found; unsupported system"
# shellcheck disable=SC1091
. /etc/os-release
case "${ID:-} ${ID_LIKE:-}" in
  *arch*)            DISTRO=arch ;;
  *ubuntu*|*debian*) DISTRO=ubuntu ;;
  *) die "unsupported distribution '${ID:-unknown}' (supported: Arch Linux, Ubuntu)" ;;
esac
IS_WSL=0
grep -qi microsoft /proc/version 2>/dev/null && IS_WSL=1
ok "distro: ${PRETTY_NAME:-$ID} ($DISTRO)$( (( IS_WSL )) && echo ', running in WSL')"

if (( IS_WSL )) && [[ "$REPO_DIR" == /mnt/* ]]; then
  warn "this repo is on the Windows filesystem ($REPO_DIR)."
  warn "Builds there are many times slower. Clone it under your Linux home (~/...) instead."
fi

# ---------------------------------------------------------------------------
log "Layer 1: OS packages"

if [[ $DISTRO == arch ]]; then
  PKGS=(base-devel git curl unzip pkgconf openssl podman github-cli mise)
  # pacman -T prints only the packages that are NOT installed.
  mapfile -t MISSING < <(pacman -T "${PKGS[@]}" || true)
  if (( ${#MISSING[@]} )); then
    todo "install: ${MISSING[*]}"
    if ! run sudo pacman -S --needed --noconfirm "${MISSING[@]}"; then
      # Usual cause: the local package database is older than the mirrors, which have already
      # deleted the old package files (HTTP 404). Arch forbids "pacman -Sy <pkg>" (partial upgrade),
      # so the only safe fix is a full system upgrade, which the user runs deliberately.
      die "pacman could not install packages. If you saw '404' errors, your package database is
       out of date. Run a full system upgrade yourself, then re-run this script:
           sudo pacman -Syu
       (Reboot afterwards if the kernel was upgraded.)"
    fi
  else
    ok "all present: ${PKGS[*]}"
  fi

else # ubuntu
  KEYRINGS=/etc/apt/keyrings
  NEED_APT_UPDATE=0

  if [[ ! -f /etc/apt/sources.list.d/github-cli.list ]]; then
    todo "add GitHub CLI apt repository (cli.github.com)"
    run sudo install -dm 755 "$KEYRINGS"
    run sudo bash -c "curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o $KEYRINGS/githubcli-archive-keyring.gpg && chmod go+r $KEYRINGS/githubcli-archive-keyring.gpg"
    run sudo bash -c "echo 'deb [arch=$(dpkg --print-architecture) signed-by=$KEYRINGS/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main' > /etc/apt/sources.list.d/github-cli.list"
    NEED_APT_UPDATE=1
  else
    ok "GitHub CLI apt repository configured"
  fi

  if [[ ! -f /etc/apt/sources.list.d/mise.list ]]; then
    todo "add mise apt repository (mise.jdx.dev)"
    run sudo install -dm 755 "$KEYRINGS"
    run sudo bash -c "curl -fsSL https://mise.jdx.dev/gpg-key.pub -o $KEYRINGS/mise-archive-keyring.asc"
    run sudo bash -c "echo 'deb [signed-by=$KEYRINGS/mise-archive-keyring.asc] https://mise.jdx.dev/deb stable main' > /etc/apt/sources.list.d/mise.list"
    NEED_APT_UPDATE=1
  else
    ok "mise apt repository configured"
  fi

  PKGS=(build-essential git curl unzip ca-certificates pkg-config libssl-dev podman gh mise)
  MISSING=()
  for p in "${PKGS[@]}"; do
    dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed" || MISSING+=("$p")
  done
  if (( ${#MISSING[@]} )); then
    todo "install: ${MISSING[*]}"
    NEED_APT_UPDATE=1
  else
    ok "all present: ${PKGS[*]}"
  fi
  (( NEED_APT_UPDATE )) && run sudo apt-get update -qq
  (( ${#MISSING[@]} )) && run sudo apt-get install -y -qq "${MISSING[@]}"
fi

# ---------------------------------------------------------------------------
log "Layer 2: Rust toolchain"

# shellcheck disable=SC1091
[[ -f "$HOME/.cargo/env" ]] && . "$HOME/.cargo/env"

if have rustup; then
  ok "rustup $(rustup --version 2>/dev/null | awk '{print $2}')"
else
  todo "install rustup (official installer from sh.rustup.rs)"
  run bash -c "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain none"
  # shellcheck disable=SC1091
  [[ -f "$HOME/.cargo/env" ]] && . "$HOME/.cargo/env"
fi

TOOLCHAIN="$(sed -n 's/^channel *= *"\(.*\)"/\1/p' "$REPO_DIR/rust-toolchain.toml")"
[[ -n "$TOOLCHAIN" ]] || die "could not read channel from rust-toolchain.toml"
if have rustup && rustup toolchain list | grep -q "^${TOOLCHAIN}[-.]"; then
  ok "toolchain $TOOLCHAIN installed"
  # Components listed in rust-toolchain.toml
  mapfile -t WANT < <(sed -n 's/^components *= *\[\(.*\)\]/\1/p' "$REPO_DIR/rust-toolchain.toml" | tr -d '" ' | tr ',' '\n')
  INSTALLED="$(rustup component list --installed --toolchain "$TOOLCHAIN" 2>/dev/null)"
  for c in "${WANT[@]}"; do
    [[ -z "$c" ]] && continue
    if grep -q "^${c}\(-preview\)\?-" <<<"$INSTALLED"; then
      ok "component $c"
    else
      todo "add component $c"
      run rustup component add --toolchain "$TOOLCHAIN" "$c"
    fi
  done
else
  todo "install toolchain $TOOLCHAIN with components from rust-toolchain.toml"
  run bash -c "cd '$REPO_DIR' && RUSTUP_AUTO_INSTALL=1 rustup toolchain install"
fi

# ---------------------------------------------------------------------------
log "Layer 3: Dev tools pinned in mise.toml"

if ! have mise; then
  if (( DRY_RUN )); then
    todo "install tools from mise.toml (mise is installed in layer 1)"
    CHANGES=$((CHANGES + 1))
  else
    die "mise not found on PATH after layer 1"
  fi
else
  # mise asks before using a config file from a new directory; trust ours explicitly.
  mise trust --quiet "$REPO_DIR/mise.toml" >/dev/null 2>&1 || true
  cd "$REPO_DIR"
  MISSING_TOOLS="$(mise ls --current --missing --no-header 2>/dev/null || true)"
  if [[ -n "$MISSING_TOOLS" ]]; then
    todo "install missing tools:"
    sed 's/^/          /' <<<"$MISSING_TOOLS"
    # cargo-binstall first, so the cargo:* tools download prebuilt binaries instead of compiling.
    run mise install --yes cargo-binstall
    if (( DRY_RUN )); then
      run mise install --yes
    else
      BINSTALL_DIR="$(dirname "$(mise which cargo-binstall)")"
      run env PATH="$BINSTALL_DIR:$PATH" mise install --yes
    fi
  else
    ok "all tools from mise.toml installed"
  fi
fi

# ---------------------------------------------------------------------------
log "Layer 4: Shell activation"

MARK="# >>> software-factory: mise >>>"
case "$(basename "${SHELL:-bash}")" in
  bash) RC="$HOME/.bashrc"; HOOK='eval "$(mise activate bash)"' ;;
  zsh)  RC="$HOME/.zshrc";  HOOK='eval "$(mise activate zsh)"' ;;
  fish) RC="$HOME/.config/fish/config.fish"; HOOK='mise activate fish | source' ;;
  *)    RC=""; warn "unknown shell ${SHELL:-?}: add mise activation yourself (https://mise.jdx.dev)" ;;
esac
if [[ -n "$RC" ]]; then
  if grep -qF "mise activate" "$RC" 2>/dev/null; then
    ok "mise activation present in $RC"
  else
    todo "add mise activation to $RC"
    run bash -c "printf '\n%s\n%s\n# <<< software-factory: mise <<<\n' '$MARK' '$HOOK' >> '$RC'"
  fi
fi

# ---------------------------------------------------------------------------
log "Manual steps (not automated on purpose)"
if have gh && gh auth status >/dev/null 2>&1; then
  ok "gh is logged in to GitHub"
else
  warn "run 'gh auth login' yourself (choose GitHub.com, HTTPS, browser login)."
fi

echo
if (( DRY_RUN )); then
  printf '\033[1m%d change(s) needed.\033[0m Run ./bootstrap.sh to apply.\n' "$CHANGES"
else
  printf '\033[1m%d change(s) made.\033[0m\n' "$CHANGES"
  (( CHANGES )) && echo "Open a new terminal (or: source $RC) so the shell picks up mise, then run: just doctor"
fi
