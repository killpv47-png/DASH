---
name: bot-self-maintenance
description: "How to safely modify, test and redeploy THIS bot's own source code (the project you live in)."
---

# Bot self-maintenance

You are running inside the bot you may be asked to modify. Source root = `$GITHUB_WORKSPACE` (Actions) or the project root (local). See AGENTS.md for the module map.

## Safe change loop
1. `search_files` / `read_file` to understand the exact code path first.
2. Make the change with `patch` (never rewrite whole files you did not read).
3. `terminal: python -m pytest -q` — must pass. Add a test for the behaviour you changed in `tests/`.
4. `terminal: python -c "import cfbot.telegram.bot"` as a smoke import.
5. The bot source lives in the HOST repo (name in the runtime environment block). There is no tool for pushing code there on purpose (HOST_PAT is protected). Package the changed files (`git diff > fix.patch` or a ZIP) and send them to the user with `telegram_send_file`; the owner commits them.
6. Tell the user a restart is needed to load the new code and that they can trigger it from Settings → Restart (the lifecycle checkpoints state first, nothing is lost).

## Never
- Never edit `.github/workflows/bot.yml` concurrency/cron without the user agreeing — it can double-run the bot.
- Never commit `data/`, `.env`, or any secret.
- Never change the `GB1` crypto format without a migration — existing checkpoints would become unreadable.
