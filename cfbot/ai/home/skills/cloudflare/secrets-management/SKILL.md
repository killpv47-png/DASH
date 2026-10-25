---
name: secrets-management
description: "Worker secrets and plain-text variables: list, set, delete, and detect which env names the code needs."
---

# Secrets & variables

- List secrets: `cloudflare_api(action="list_secrets", worker=…)` (names only; values never returned).
- Set: `set_secret worker=… name=… value=…` — **only with a value the user gave you in this conversation**.
- Plain vars: `set_var` (stored as `plain_text` binding; visible in the dashboard — never put credentials there).
- Remove: `delete_secret` / `remove_binding` (confirm first).
- Detect needs: `analyze worker=…` → items with kind `secret`/`var` and action `pending` are missing.
- Names: letters, digits, underscore. Names that look sensitive (TOKEN, KEY, SECRET, PASSWORD…) should be secrets.
- Bot-level secrets (BOT_TOKEN, STATE_KEY, HOST_PAT, TAVILY_API_KEY) are env vars of the hosting workflow, not Worker secrets.
