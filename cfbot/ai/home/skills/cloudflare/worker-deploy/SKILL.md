---
name: worker-deploy
description: "Deploy code to a Worker the right way: analyze → show plan → collect values → create/link resources → upload → verify."
---

# Worker deploy

1. Get the code: user file (telegram_download_file → workspace), pasted code, or a ZIP project. TypeScript / bare npm
   imports → bundle first in the terminal (`npm i && npx wrangler deploy --dry-run --outdir dist`) and deploy `dist/`.
2. `cloudflare_api(action="analyze", local_path=… | code=…, worker=<name>)` and SHOW the user: handlers, each binding
   with its inferred kind and planned action, flags, crons, warnings, blockers.
3. Resolve the plan with the user:
   - storage (KV/D1/R2/Queue): create new (`<worker>-<binding>`) or link an existing one (`list_kv`/`list_d1`/…);
     choose the type with the storage rules (D1 relational, KV key-value, R2 files, Queues async);
   - vars/secrets: ASK for values. Never invent;
   - service / Durable Object bindings: confirm the target Worker / class.
4. Overwriting an existing Worker = destructive → confirm. Existing bindings/secrets are inherited automatically.
5. `cloudflare_api(action="deploy", worker=…, local_path|code=…, plan={NAME: {action, target, value}}, crons=[…])`.
6. Verify: `list_deployments`, then curl the workers.dev URL from the report and show the real status.
