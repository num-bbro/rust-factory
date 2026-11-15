#!/usr/bin/env bash
# deploy.sh — deploy a released image to the pilot, promote it to production, or show status.
#
#   scripts/deploy.sh deploy  <env> <version|image-ref>   e.g. deploy pilot 0.1.0
#   scripts/deploy.sh promote <version>                     pilot-verified version -> production
#   scripts/deploy.sh status  [env]
#
# Hosts come from deploy/hosts/<env>.txt ("name target port"); target is "local" (this machine,
# a simulated host) or "ssh:user@host" (a real VM with rootless Podman, systemd --user and
# lingering enabled). Each host runs the image as a Podman Quadlet service
# (deploy/rust-factory.container.in) and keeps its current and previous image in
# ~/.local/state/rust-factory/<name>/.
#
# Safety rules:
# * a version (X.Y.Z) is resolved to ghcr.io/...@sha256:<digest>; hosts always run digests
# * after each deploy the host must answer /health within HEALTH_WAIT seconds, else it is rolled
#   back to its previous image (and that is verified too)
# * production: only a version that pilot is running healthily; one host at a time; stop at the
#   first failure, leaving the remaining hosts untouched
# * every deployment is recorded in GitHub (Deployments, Environments) when gh is logged in
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGISTRY_IMAGE="${REGISTRY_IMAGE:-ghcr.io/num-bbro/rust-factory}"
HEALTH_WAIT="${HEALTH_WAIT:-30}"
REPO="${GH_REPO:-num-bbro/rust-factory}"

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '  \033[32mok\033[0m    %s\n' "$*"; }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$*"; }
die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# --- transport: run a command / write a file on a host ------------------------------------------
on_host() {  # on_host <target> <command>
  if [[ "$1" == local ]]; then bash -c "$2"; else ssh -o BatchMode=yes "${1#ssh:}" "$2"; fi
}
put_file() {  # put_file <target> <path> < content   (path may start with a literal $HOME)
  if [[ "$1" == local ]]; then
    local p="${2/#\$HOME/$HOME}"
    mkdir -p "$(dirname "$p")" && cat > "$p"
  else ssh -o BatchMode=yes "${1#ssh:}" "mkdir -p \"\$(dirname $2)\" && cat > $2"; fi
}

hosts() {  # hosts <env>  -> lines "name target port"
  local f="$ROOT/deploy/hosts/$1.txt"
  [[ -f "$f" ]] || die "unknown environment '$1' (no $f)"
  grep -vE '^\s*(#|$)' "$f"
}

# --- image resolution ---------------------------------------------------------------------------
resolve() {  # resolve <version|image-ref> -> image pinned by digest (local test images: as is)
  local arg="$1" ref digest
  if [[ "$arg" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then ref="$REGISTRY_IMAGE:$arg"; else ref="$arg"; fi
  if [[ "$ref" == *@sha256:* ]]; then echo "$ref"; return; fi
  if [[ "$ref" == localhost/* ]]; then
    echo "  warn  $ref is a local test image, not pinned by digest" >&2
    echo "$ref"; return
  fi
  podman pull -q "$ref" >/dev/null || die "cannot pull $ref"
  digest="$(podman image inspect "$ref" --format '{{range .RepoDigests}}{{println .}}{{end}}' \
            | grep -m1 "^${ref%:*}@sha256:")" || die "no registry digest for $ref"
  echo "$digest"
}

# --- one host -----------------------------------------------------------------------------------
unit_name() { echo "rust-factory-$1"; }

write_unit() {  # write_unit <env> <name> <target> <port> <image>
  sed -e "s|@ENV@|$1|g" -e "s|@NAME@|$2|g" -e "s|@PORT@|$4|g" -e "s|@IMAGE@|$5|g" \
      "$ROOT/deploy/rust-factory.container.in" \
    | put_file "$3" "\$HOME/.config/containers/systemd/$(unit_name "$2").container"
}

start_and_check() {  # start_and_check <name> <target> <port> <image> -> 0 if healthy
  local unit; unit="$(unit_name "$1")"
  # Blocking restart (bounded): returns once the NEW container is started (Notify=healthy) or the
  # start failed. Never check health before this returns: the old instance may still be answering.
  on_host "$2" "systemctl --user daemon-reload && timeout 90 systemctl --user restart $unit.service" \
    >/dev/null 2>&1 || true            # a failed start is caught by the checks below
  local deadline=$((SECONDS + HEALTH_WAIT))
  while (( SECONDS < deadline )); do
    start_check_only "$1" "$2" "$3" "$4" && return 0
    sleep 1
  done
  return 1
}

start_check_only() {  # start_check_only <name> <target> <port> [image]: check, never restart
  # Healthy = the container runs the expected image AND systemd reports the unit "active" (with
  # Notify=healthy only after the container's own health check passed) AND /health answers.
  # An HTTP answer alone is not enough: an old instance or a restart loop can answer too.
  local unit; unit="$(unit_name "$1")"
  if [[ -n "${4:-}" ]]; then
    [[ "$(on_host "$2" "podman inspect $unit --format '{{.ImageName}}'" 2>/dev/null)" == "$4" ]] || return 1
  fi
  [[ "$(on_host "$2" "systemctl --user is-active $unit.service" 2>/dev/null)" == active ]] &&
  [[ "$(on_host "$2" "curl -fsS --max-time 2 http://127.0.0.1:$3/health" 2>/dev/null)" == ok ]]
}

state() {  # state <target> <name> <current|previous>
  on_host "$1" "cat \$HOME/.local/state/rust-factory/$2/$3 2>/dev/null" || true
}
set_state() {  # set_state <target> <name> <current> <previous>
  on_host "$1" "d=\$HOME/.local/state/rust-factory/$2; mkdir -p \$d; printf '%s\n' '$3' > \$d/current; printf '%s\n' '$4' > \$d/previous"
}

deploy_host() {  # deploy_host <env> <name> <target> <port> <image>  -> 0 ok, 1 rolled back, 2 broken
  local env=$1 name=$2 target=$3 port=$4 image=$5 prev
  prev="$(state "$target" "$name" current)"
  if [[ "$prev" == "$image" ]] && start_check_only "$name" "$target" "$port" "$image"; then
    ok "$name already runs this image and is healthy"; return 0
  fi
  write_unit "$env" "$name" "$target" "$port" "$image"
  if start_and_check "$name" "$target" "$port" "$image"; then
    set_state "$target" "$name" "$image" "$prev"
    ok "$name healthy on :$port"
    return 0
  fi
  bad "$name did not become healthy within ${HEALTH_WAIT}s"
  if [[ -z "$prev" ]]; then
    on_host "$target" "systemctl --user stop $(unit_name "$name").service; rm -f \$HOME/.config/containers/systemd/$(unit_name "$name").container; systemctl --user daemon-reload; systemctl --user reset-failed $(unit_name "$name").service" >/dev/null 2>&1 || true
    bad "$name had no previous version; service stopped and removed"
    return 1
  fi
  say "rolling $name back to ${prev##*/}"
  write_unit "$env" "$name" "$target" "$port" "$prev"
  if start_and_check "$name" "$target" "$port" "$prev"; then
    ok "$name rolled back and healthy"
    return 1
  fi
  bad "$name rollback ALSO unhealthy; needs a human now"
  return 2
}

# --- GitHub records: deployments and the board ----------------------------------------------------
gh_ok() { command -v gh >/dev/null && gh auth status >/dev/null 2>&1; }

record() {  # record <env> <version|ref> <state: success|failure|error> <description>
  gh_ok || return 0
  local ref="main" id
  [[ "$2" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] && ref="v$2"
  id="$(printf '{"ref":"%s","environment":"%s","auto_merge":false,"required_contexts":[],"description":"%s","transient_environment":false,"production_environment":%s}' \
        "$ref" "$1" "$4" "$([[ $1 == production ]] && echo true || echo false)" \
      | gh api -X POST "repos/$REPO/deployments" --input - --jq .id 2>/dev/null)" || return 0
  gh api -X POST "repos/$REPO/deployments/$id/statuses" -f state="$3" -f description="$4" >/dev/null 2>&1 || true
}

move_cards() {  # move_cards <version> <Status>: issues/PRs released in this version
  gh_ok && [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || return 0
  git -C "$ROOT" fetch -q --tags origin 2>/dev/null || true
  local tag="v$1" prev range n prs urls=()
  prev="$(git -C "$ROOT" describe --tags --abbrev=0 "$tag^" 2>/dev/null || true)"
  range="${prev:+$prev..}$tag"
  prs=" $(gh pr list --repo "$REPO" --state all --limit 1000 --json number --jq '[.[].number] | join(" ")') "
  for n in $(git -C "$ROOT" log --format=%s "$range" | grep -oE '#[0-9]+' | tr -d '#' | sort -un); do
    if [[ "$prs" == *" $n "* ]]; then urls+=("https://github.com/$REPO/pull/$n")
    else urls+=("https://github.com/$REPO/issues/$n"); fi
  done
  (( ${#urls[@]} )) || return 0
  "$ROOT/scripts/board.sh" "${urls[@]}" Status="$2" >/dev/null 2>&1 \
    && ok "board: ${#urls[@]} items released in $tag moved to $2" \
    || echo "  warn  could not update the board (deploy itself succeeded)" >&2
}

# --- commands --------------------------------------------------------------------------------
cmd_deploy() {  # cmd_deploy <env> <version|image>
  local env=$1 image failed=0 rc
  image="$(resolve "$2")"
  say "deploying ${image} to $env"
  while read -r name target port; do
    rc=0; deploy_host "$env" "$name" "$target" "$port" "$image" || rc=$?
    if (( rc != 0 )); then failed=$rc; break; fi    # rolling: stop at the first failure
  done < <(hosts "$env")
  if (( failed == 0 )); then
    record "$env" "$2" success "deployed $image"
    [[ $env == pilot ]] && move_cards "$2" Piloted
    [[ $env == production ]] && move_cards "$2" Released
    say "$env now runs ${image##*/}"
  else
    record "$env" "$2" failure "deploy of $image failed; rolled back"
    die "deploy to $env failed (see above); remaining hosts were not touched"
  fi
}

cmd_promote() {  # cmd_promote <version>: human gate 3
  [[ "${1:-}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "promote takes a released version, e.g. 0.1.0"
  local image name target port
  image="$(resolve "$1")"
  read -r name target port < <(hosts pilot | head -1)
  [[ "$(state "$target" "$name" current)" == "$image" ]] \
    || die "pilot is not running $1 (${image##*/}); deploy it to pilot first"
  start_check_only "$name" "$target" "$port" "$image" \
    || die "pilot is running $1 but is not healthy; not promoting"
  ok "pilot runs $1 and is healthy"
  cmd_deploy production "$1"
}

cmd_status() {  # cmd_status [env]
  local envs=("${1:-pilot}" ) cur health unit
  [[ -z "${1:-}" ]] && envs=(pilot production)
  for env in "${envs[@]}"; do
    say "$env"
    while read -r name target port; do
      cur="$(state "$target" "$name" current)"
      health="$(on_host "$target" "curl -fsS --max-time 2 http://127.0.0.1:$port/health" 2>/dev/null || true)"
      unit="$(on_host "$target" "systemctl --user is-active $(unit_name "$name").service" 2>/dev/null || true)"
      printf '  %-8s %-11s %-6s :%-6s %s\n' "$name" "${unit:-inactive}" "${health:-DOWN}" "$port" "${cur:-<not deployed>}"
    done < <(hosts "$env")
  done
}

case "${1:-}" in
  deploy)  [[ $# -eq 3 ]] || die "usage: $0 deploy <env> <version|image>"; cmd_deploy "$2" "$3" ;;
  promote) [[ $# -eq 2 ]] || die "usage: $0 promote <version>"; cmd_promote "$2" ;;
  status)  cmd_status "${2:-}" ;;
  *) sed -n '2,8p' "$0" >&2; exit 2 ;;
esac
