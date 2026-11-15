#!/usr/bin/env bash
# PostToolUse hook (Edit|Write|MultiEdit): format the Rust file an agent just edited.
#
# Input: the tool call as JSON on stdin. Formats only *.rs files that exist; anything else is
# ignored. Never blocks: a file that does not parse yet is left for the compiler to report.
set -uo pipefail

file="$(python3 -I -c 'import json,sys; d=json.load(sys.stdin); print((d.get("tool_input") or {}).get("file_path",""))' 2>/dev/null)"
[[ "$file" == *.rs && -f "$file" ]] || exit 0

# rustfmt finds rustfmt.toml by walking up from the file, so project settings apply.
rustfmt --edition 2024 "$file" 2>/dev/null || true
exit 0
