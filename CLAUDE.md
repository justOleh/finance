# my-finance

## Git and commits

- Use the `/commit` skill (`.claude/skills/commit/SKILL.md`) whenever the user asks to commit, save, or checkpoint changes. It builds the message from the session history and the diff.
- Always propose the file list and commit message first and wait for explicit approval before running `git add` / `git commit`.
- A `PreToolUse` hook (`.claude/hooks/confirm-git.sh`, registered in `.claude/settings.json`) forces an approval prompt on every state-changing git command. Never try to bypass it.
- Never push or open PRs unless explicitly asked in a separate request.
- Never stage or commit Terraform state (`*.tfstate*`), `.env` files, secrets, or build output.
