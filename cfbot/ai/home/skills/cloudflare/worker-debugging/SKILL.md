---
name: worker-debugging
description: "Diagnose a failing / erroring Cloudflare Worker: metrics, deployments, code, bindings, live request; propose and apply a fix."
---

# Worker debugging

1. `cloudflare_api(action="metrics", worker=..., hours=24)` — requests vs errors, CPU p99 (CPU limit exceeded shows as errors).
2. `cloudflare_api(action="list_deployments", worker=...)` — did a recent deploy start the errors? Note the previous version id.
3. Reproduce: `terminal: curl -sS -i https://<worker>.<subdomain>.workers.dev/<path>` — record status + body (Cloudflare error 1101 = uncaught exception, 1102 = CPU/memory limit, 1042 = worker not found).
4. `cloudflare_api(action="analyze", worker=...)` + `get_worker` — compare the env names the code uses with the bindings attached. A missing binding is the #1 cause (`env.DB is undefined`).
5. Missing secret/var → ask the user for the value → `set_secret` / `set_var`. Missing storage → `create_kv|create_d1|create_r2` + `add_binding`.
6. Code bug → `get_code` (saved to workspace), fix with `patch`, re-`analyze`, then `deploy` with the same plan (existing bindings are inherited).
7. If the user wants service back first: `rollback` to the previous version (needs confirmation).
8. Live logs: the API `tail` endpoint needs a websocket session — recommend enabling observability (`settings_patch fields={"observability":{"enabled":true}}`) and checking Workers Logs in the dashboard.

Never paste full code or logs into chat — summarize and quote ≤15 relevant lines.
