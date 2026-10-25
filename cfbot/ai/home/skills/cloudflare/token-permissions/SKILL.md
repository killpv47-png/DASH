---
name: token-permissions
description: "Explain / fix Cloudflare API token permissions: which permission each operation needs, presets, Global API Key, 'GID' requests."
---

# Token permissions

- Presets and their template links live in `cfbot/cloudflare/tokens.py` (`PRESETS`, `FEATURE_PERMS`). The Telegram 🔑 Token guide shows them.
- Error code 10000 "Authentication error" = permission missing for that endpoint. Map: Workers → Workers Scripts Edit;
  KV → Workers KV Storage; D1 → D1; R2 → Workers R2 Storage; Queues → Queues; metrics → Account Analytics Read;
  routes → Workers Routes Edit + Zone Read; custom domains → + DNS Edit.
- Check what the token has: `cloudflare_api(action="whoami")`; exact list needs "API Tokens Read" on the token.
- "GID token with all access": no such thing exists in Cloudflare. Offer (a) preset **full** (custom token, all bot
  permissions, revocable, can expire, IP-filterable) or (b) the **Global API Key** (email + key, every permission on every
  account, cannot be scoped — highest risk; rotate it if it ever leaks).
- Verify docs: `cloudflare_docs path="/fundamentals/api/reference/permissions/"`.
