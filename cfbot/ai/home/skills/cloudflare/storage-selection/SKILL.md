---
name: storage-selection
description: "Choose and provision the right Cloudflare storage (D1, KV, R2, Queues, Durable Objects) for a Worker and bind it."
---

# Storage selection

| Need | Use | Why |
|---|---|---|
| tables, relations, SQL, transactions | **D1** | serverless SQLite; `env.DB.prepare(sql).bind(...).all()` |
| config, feature flags, cache, sessions, read-heavy | **KV** | global, eventually consistent (~60 s), 25 MiB values |
| files, images, uploads, backups | **R2** | object storage, S3-compatible, no egress fees |
| background jobs, batching, decoupling | **Queues** | producer `env.Q.send()`, consumer `queue()` handler |
| strongly consistent per-entity state, websockets, counters | **Durable Objects** | needs a class + migration (deploy with wrangler or our deploy with `new_sqlite_classes`) |

Provision: `create_d1` / `create_kv` / `create_r2` / `create_queue` → `add_binding worker=… binding={...}` (or let `deploy`
create them). D1 schema: `d1_query database_id=… sql="CREATE TABLE …"`. Always check limits with
`cloudflare_docs path="/d1/platform/limits/"` (or kv / r2 / queues) before promising capacity.
