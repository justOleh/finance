---
name: commit
description: Create a git commit with a message derived from this session's history and the changed files, with explicit user approval before any git state change. Use when the user asks to commit, or runs /commit.
disable-model-invocation: true
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git branch --show-current)
---

# Commit

The user wants full control over git. Read freely, but **never change git state without an explicit "yes" from the user.** A project hook (`.claude/hooks/confirm-git.sh`) also forces an approval prompt on every `git add` / `git commit`; do not try to work around it.

## Steps

1. **Inspect (read-only).** Run `git status --short`, `git diff --stat`, `git diff` (and `git diff --staged` if anything is staged), `git branch --show-current`, and `git log --oneline -10` to learn the repo's message style.

2. **Classify every changed/untracked file** into one of:
   - *Include*: part of the work done in this session.
   - *Exclude*: unrelated changes, or files that should not be committed (Terraform state `*.tfstate*`, `.env` files, secrets, build output, large/binary data, `.DS_Store`). Say why.
   - *Unsure*: ask.

3. **Draft the message** from two sources: what we did and why in this session (the conversation), and what the diff actually contains. If they disagree, trust the diff and mention the discrepancy.
   - Subject: imperative mood, <= 72 chars, no trailing period, matching the style in `git log`.
   - Body (only if useful): short bullets on what and why, wrapped at ~72 chars.
   - Append any attribution trailer the session's instructions require (e.g. `Co-Authored-By`).

4. **Present a proposal and stop.** Show the branch, the explicit list of files to stage, the files left out (with reasons), the full commit message, and the exact commands. Ask the user to approve, edit the message, or change the file list. Do not run `git add` or `git commit` until they answer.

5. **Execute only what was approved**, as two separate commands so each gets its own approval prompt:
   - `git add <file> <file>` with explicit paths. Never `git add -A`, `git add .` or `git commit -a`.
   - `git commit -m "<subject>" -m "<body>"`.
   - Then `git status --short` and `git log -1 --stat`, and report the result.

6. **Stop.** Never push, open a PR, or create/switch branches unless the user asks in a separate request.

## Hard rules

- No `--amend`, `--no-verify`, `--force`, `reset`, `stash`, `rebase`, or history rewriting unless the user explicitly asks for that exact thing.
- If a pre-commit hook fails, report the output and ask what to do. Don't bypass it or retry blindly.
- If on `main`, say so and ask whether to create a branch first.
- If the user edits the message or file list, show the revised proposal before executing.
- If there is nothing to commit, say so and stop.
