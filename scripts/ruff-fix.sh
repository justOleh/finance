#!/usr/bin/env bash
# Run `ruff check --fix` then `ruff format` sequentially on the backend.
# Usage: scripts/ruff-fix.sh [files...]   (no args = whole backend/)
# Shared by pre-commit and the Claude Code PostToolUse hook.
# Format always runs, even if lint finds unfixable issues; exit code is
# non-zero if either step fails.

set -uo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

targets=("$@")
[[ ${#targets[@]} -eq 0 ]] && targets=(backend)

ruff() { uv run --quiet --project backend --extra dev ruff "$@"; }

status=0
ruff check --fix "${targets[@]}" || status=$?
ruff format "${targets[@]}" || status=$?
exit "$status"
