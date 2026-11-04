#!/usr/bin/env bash
# PreToolUse hook for Bash: force an explicit approval prompt for any
# state-changing git command, regardless of allow rules in settings.
# Read-only git commands (status, diff, log, ...) pass through untouched.

set -euo pipefail

cmd="$(jq -r '.tool_input.command // empty')"
[[ -z "$cmd" ]] && exit 0

# Matches `git [global opts] <subcommand>` at the start or after ; & | ( or newline.
pattern='(^|[;&|(]|\n)[[:space:]]*git([[:space:]]+-[^[:space:]]+([[:space:]]+[^-[:space:]][^[:space:]]*)?)*[[:space:]]+(add|commit|push|pull|merge|rebase|reset|checkout|switch|restore|stash|tag|rm|mv|cherry-pick|revert|clean|branch[[:space:]]+-[dDmM])\b'

if printf '%s' "$cmd" | grep -Eq "$pattern"; then
    jq -n --arg cmd "$cmd" '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "ask",
        permissionDecisionReason: ("Git state change requires your explicit approval:\n" + $cmd)
      }
    }'
fi
exit 0
