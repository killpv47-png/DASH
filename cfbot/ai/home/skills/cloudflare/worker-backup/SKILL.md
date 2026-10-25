---
name: worker-backup
description: "Download the deployed code + configuration of one or all Workers and deliver it to the user as a ZIP via Telegram."
---

# Worker backup / download

1. `cloudflare_api(action="list_workers")`.
2. For each Worker: `get_code` (modules are saved to `workspace/workers/<name>/`) and `get_worker` (bindings, compat date/flags) + `get_crons`.
3. Write `workspace/workers/<name>/wrangler.json` reconstructing the config: `name`, `main`, `compatibility_date`,
   `compatibility_flags`, `vars` (plain_text), `kv_namespaces`, `d1_databases`, `r2_buckets`, `queues.producers`,
   `services`, `triggers.crons`. Secrets: list names only (values are never returned by the API).
4. Zip everything (`python -m zipfile -c backup.zip workers/`) and send with `telegram_send_file`.
5. Report count + size. Telegram limit is 50 MB per file.
