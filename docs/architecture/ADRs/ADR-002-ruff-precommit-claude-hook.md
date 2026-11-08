ADR-002: Ruff via one shared script, pre-commit and a Claude Code hook

**Status** Accepted
**Date** 2026-11-08

## Context
The backend had no linter or formatter. Code is edited both by hand and by Claude Code, and style drift would otherwise show up in later diffs.

## Decision
- Use Ruff (lint + format), configured in `backend/pyproject.toml` and pinned in the `dev` extra. Rules: `E`, `W`, `F`, `I`, `B`, `UP`.
- `scripts/ruff-fix.sh` runs `ruff check --fix` then `ruff format`. It is the single entry point.
- Pre-commit (local hook) and a Claude Code `PostToolUse` hook on `Edit|Write` both call that script, so a manual commit and an AI edit are formatted identically.
- FastAPI helpers (`Depends`, `Query`, `File`) are declared as immutable calls so bugbear `B008` does not flag route signatures.

## Consequences
- **+** One definition of "formatted"; edits by Claude are cleaned up immediately and unfixable errors come back as feedback.
- **+** Formatting-only changes are kept in their own commit.
- **−** Files can change on disk right after an edit, and a commit is aborted if the hook modifies files (re-stage and retry).
- **−** Hook scripts are not under `.git/hooks`: each clone must run `pre-commit install`.
- Revisit rule selection (e.g. `S`, `SIM`) as the codebase grows.
