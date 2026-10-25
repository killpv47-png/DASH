---
name: telegram-file-send
description: "Send a file (ZIP, code, logs, backup) to the user, or receive a file they sent, using the built-in Telegram tools."
---

# Telegram files

- Send: `telegram_send_file(path=<workspace path>, caption=...)` — the bot token is attached internally; never read
  BOT_TOKEN yourself (it is a protected secret).
- Receive: when the user uploads a document the bot records it; `telegram_download_file()` saves it into the workspace.
  Then e.g. `cloudflare_api(action="analyze", local_path=...)`.
- Limits: 50 MB per document (Bot API). Split larger archives.
- Never send files that contain secret values (.dev.vars, .env, token dumps).
