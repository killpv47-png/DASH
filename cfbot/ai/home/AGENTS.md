# Cloudflare Control Bot — Project Context for CLOUDFLARE_AI

You live inside this repository. It is a Telegram bot (Python 3.11+, aiogram 3) that manages the owner's
**Cloudflare** account — above all **Workers** — and the resources Workers use. The bot process itself is
*hosted* as a long-running GitHub Actions job (that is only where it runs; it does not manage GitHub).
Treat this file as the floor plan of your house.

## What runs where

| Path | Purpose |
|------|---------|
| `main.py` | Entry point. Restores checkpoint, opens DB, starts polling + lifecycle + watchers. |
| `cfbot/core/config.py` | **All environment variables** (see Secrets below). |
| `cfbot/core/crypto.py` | AES-256-GCM (scrypt KDF). Encrypts Cloudflare credentials at rest and the state checkpoint. |
| `cfbot/core/db.py` | SQLite (WAL + FTS5) at `data/cfbot.db`. Users, jobs, notifications, watches, AI sessions/messages/memory/pending. |
| `cfbot/core/notify.py` | Every outgoing message. Redacts secrets, stores notifications, throttles edits. |
| `cfbot/core/redact.py` | Secret patterns (Cloudflare tokens, Global API Key, bot token…) masked at every output boundary. |
| `cfbot/cloudflare/client.py` | Async Cloudflare API v4 client: token or Global-Key auth, retry/429, pagination; Workers (upload, content, settings, secrets, schedules, subdomain, deployments, versions), routes, domains, zones, KV, D1, R2, Queues, GraphQL metrics. |
| `cfbot/cloudflare/tokens.py` | Token presets → official dashboard template URLs; feature→permission matrix; error-code hints. |
| `cfbot/cloudflare/access.py` | Credential capabilities → access level (GOD / ARCHITECT / ENGINEER / OBSERVER / GHOST). |
| `cfbot/cloudflare/scanner.py` | Account scan (verify, accounts, Workers, KV/D1/R2/Queues, zones, workers.dev subdomain, capabilities). |
| `cfbot/cloudflare/analyzer.py` | Static analysis of Worker code: format, handlers, `env.X` usage → binding kind, node/npm imports, DO classes, wrangler config. |
| `cfbot/cloudflare/bundle.py` | Turns a `.js/.mjs/.py` file, pasted code or `.zip` project into uploadable modules (+ wrangler.toml/json). |
| `cfbot/cloudflare/deployer.py` | Analysis → plan (create/link/value/keep/ai/skip per binding) → real execution (create resources, upload, crons, workers.dev). |
| `cfbot/cloudflare/templates.py` | Starter Workers for the New Worker wizard. |
| `cfbot/hosting/github_host.py` | Minimal client for the HOST repo only (checkpoint file + self-dispatch). Never use it for user tasks. |
| `cfbot/telegram/` | aiogram routers: onboarding (token guide), menu, workers, newworker, deploy, secrets, ops (deployments/rollback/cron/routes/domains/test/metrics), storage, settings, help, AI chat. |
| `cfbot/i18n/` | 10 languages. `en.py` is the source of truth; `fa.py` is complete; others fall back to EN. |
| `cfbot/ai/` | **You.** `agent.py`, `prompt_builder.py`, `llm.py`, `compressor.py`, `memory.py`, `skills.py`, `tools/*` (cloudflare_api, cloudflare_docs, terminal, files, web, todo, session_search, telegram files). |
| `cfbot/ai/home/` | Your home dir: `SOUL.md`, this `AGENTS.md`, `skills/<category>/<name>/SKILL.md`. |
| `cfbot/lifecycle/` | Checkpoint (encrypted DB → host repo branch `cfbot-state`), handoff to a new run via `HOST_PAT`, deployment watcher. |
| `.github/workflows/bot.yml` | The hosting workflow. `workflow_dispatch` + cron watchdog; concurrency group prevents double runs. |
| `data/` | Runtime only (git-ignored): `cfbot.db`, `workspace/` (your terminal cwd). |

## Secrets & credentials — where they live

- **`BOT_TOKEN`** — Telegram bot token. Env var only. Never print.
- **`STATE_KEY`** — encrypts every stored Cloudflare credential and the checkpoint. Losing it = losing state.
- **`HOST_PAT`** (alias `GH_PAT`) — token of the GitHub repo that hosts the bot; only `cfbot/lifecycle/` uses it.
- **`TAVILY_API_KEY`** (alias `TAVILY`) — optional, enables `web_search`.
- **User Cloudflare credentials** — `users.cf_token_enc` (encrypted JSON: `{mode: token, token}` or
  `{mode: global_key, email, key}`) + `cf_account_id`. Your `cloudflare_api` tool already carries them; never ask, never echo.
- **AI provider credentials** — `kv` key `ai:<tg_id>` (api key encrypted).
- **Worker secrets you set** go to Cloudflare (`PUT …/workers/scripts/{name}/secrets`); the API never returns values.

## Cloudflare facts you rely on (verify with cloudflare_docs when in doubt)

- Upload/replace + deploy: `PUT /accounts/{a}/workers/scripts/{name}` multipart: `metadata` JSON
  (`main_module`, `compatibility_date`, `compatibility_flags`, `bindings[]`, `keep_bindings`) + one part per module.
- Change bindings/compat without code: `PATCH …/settings` (multipart field `settings`); keep a binding with `{"type":"inherit"}`.
- Binding JSON: `kv_namespace{namespace_id}`, `d1{id}`, `r2_bucket{bucket_name}`, `queue{queue_name}`, `ai`,
  `service{service}`, `durable_object_namespace{class_name}`, `plain_text{text}`, `secret_text{text}`.
- Crons: `PUT …/schedules` `[{"cron": "*/5 * * * *"}]`. workers.dev: `POST …/subdomain {"enabled": true}`.
- Rollback: `POST …/deployments` `{"strategy":"percentage","versions":[{"version_id":…,"percentage":100}]}`.
- Worker size limit 64 MiB uncompressed. Bare npm imports must be bundled first.

## How to change things

- UI text → `cfbot/i18n/en.py` (and `fa.py`).
- New Cloudflare capability → method on `CloudflareClient`; Telegram via a handler; for you via `cfbot/ai/tools/cloudflare_tool.py`.
- New AI tool → file in `cfbot/ai/tools/`, register in `TOOLS` in `cfbot/ai/tools/__init__.py`.
- New skill → `skill_manage(create)`.

## Operating rules

1. Analyze before deploy; show the analysis; never guess secret/var values or foreign resource ids.
2. Prefer `cloudflare_api` over curl (retry, rate limits, redaction).
3. Never write a secret value into memory, skills, todo items or chat.
4. Destructive operations need explicit confirmation in the same conversation.
5. "The bot / this project / the code" means this repository. Run `python -m pytest -q` before claiming a code change works.
6. Restart safety: the in-flight step is in `ai_pending`; `resume_pending()` repairs and continues after a handoff.
