---
name: worker-overview
description: "Analyze a Worker: purpose, handlers, bindings, missing env, crons, routes, deployments, metrics, and red flags."
---

# Worker overview / review

1. `get_worker` (bindings, compat), `get_crons`, `list_routes worker=…`, `list_domains worker=…`, `list_deployments`.
2. `analyze worker=…` — code-level needs vs what is bound (`pending` items = missing).
3. `metrics worker=… hours=24`.
4. Report: what it does (from code), entry points, bindings table, missing/unused bindings, crons (scheduled handler without
   crons = never runs), exposure (workers.dev / routes / domains), error rate, old compatibility_date (> 1 year), red flags
   (secrets hard-coded in code, `nodejs_compat` missing for node:* imports).
5. Offer concrete fixes; apply only after the user agrees.
