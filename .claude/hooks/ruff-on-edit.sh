#!/usr/bin/env bash
# PostToolUse hook for Edit|Write: run scripts/ruff-fix.sh on the edited
# Python file if it lives under backend/. Lint problems ruff can't auto-fix
# are sent back to Claude on stderr (exit 2) so it can correct them.

set -uo pipefail

file="$(jq -r '.tool_input.file_path // empty')"
[[ -z "$file" ]] && exit 0
[[ "$file" != *.py ]] && exit 0
[[ "$file" != "$CLAUDE_PROJECT_DIR"/backend/* ]] && exit 0
[[ -f "$file" ]] || exit 0

if ! out="$("$CLAUDE_PROJECT_DIR"/scripts/ruff-fix.sh "$file" 2>&1)"; then
    printf '%s\n' "$out" >&2
    exit 2
fi
exit 0
