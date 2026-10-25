# Cloudflare Control Bot + CLOUDFLARE_AI

A Telegram bot for managing your **Cloudflare** account, built mainly around **Workers**:
- Create or deploy a Worker from a file, a ZIP or pasted code.
- The bot analyses what the code needs (vars, secrets, KV, D1, R2, Queues, crons, compatibility flags, etc.).
- It shows the plan first, creates and binds the missing resources through the real Cloudflare API, then uploads and enables `workers.dev`.
- Includes secrets and variables, storage management, crons, routes, custom domains, deployments and rollback, metrics, and a test request.

It ships with **CLOUDFLARE_AI**, a Hermes-style agent with Cloudflare tools, the official docs, memory and skills.
The bot process runs as a long-lived job on **GitHub Actions**. It hands itself off to a fresh run before the 6-hour
limit and carries all state (encrypted) to the next run. GitHub is used *only* for this hosting.

> فارسی: پنل هوشمند مدیریت Cloudflare (به‌خصوص Workers) داخل تلگرام. کد را بفرستید (فایل `.js` یا ZIP یا متن)؛ ربات
> نیازهای آن (متغیر، سکرت، KV، D1، R2، Queue، کرون، …) را تحلیل می‌کند، نتیجه را **قبل از هر کاری** نشان می‌دهد، مقادیر ناقص را
> از شما می‌پرسد (هیچ‌چیز حدس زده نمی‌شود)، منابع لازم را با API واقعی Cloudflare می‌سازد و متصل می‌کند و Worker را منتشر می‌کند.
> راهنمای ساخت توکن با لینک‌های رسمی Cloudflare (دسترسی کامل و محدود + ریسک هر سطح) و ایجنت CLOUDFLARE_AI هم دارد.

---

## ✅ Features

| Area | What you get |
|------|--------------|
| **Onboarding** | `/start` → language (10) → **token guide** → paste the token (or Global API Key + e-mail) → verify → full account scan |
| **Token guide** | 5 presets (Full · Workers · Workers + Storage · Routes & DNS · Read-only). Each one opens the **official Cloudflare token page with the permissions pre-filled** (user-token link and account-token link) and states the permissions and their risk. Also includes a feature → permission matrix and a Global API Key explanation (see *"GID token"* below). |
| **Account scan** | e-mail, token status and expiry, accounts (picker if more than one), `workers.dev` subdomain, Workers, KV, D1, R2, Queues, zones. Exact permissions come from the token's policies when readable; otherwise they are probed per product. This yields an access level of 👑 GOD / 🏛 ARCHITECT / 🛠 ENGINEER / 👁 OBSERVER / 👻 GHOST. |
| **Workers** | list (paged) and card: URL, handlers, compatibility date and flags, usage model, crons, bindings, logpush. View code and download it as a ZIP. Bindings: remove or add. Settings: workers.dev on/off, logpush, Workers Logs (observability), `nodejs_compat`, compatibility date. Watch deployments. Delete (confirm by typing the name). |
| **Deploy (smart)** | Accepts `.js` / `.mjs` / `.cjs` / `.py` / `.zip` (with `wrangler.toml` / `wrangler.json(c)`) or pasted code. The **analyzer** finds the format (module, service-worker or Python), the handlers, every `env.X` and its kind, Durable Object classes, `node:` and npm imports, wrangler vars and bindings, crons and routes. The **plan** has one row per need, each set to create, link existing, enter value, keep or skip. Values are always asked for, never guessed, and **Deploy only appears when nothing is pending**. **Execute** creates KV / D1 / R2 / Queues, uploads with all bindings (existing secrets are kept via `inherit`), sets crons and enables workers.dev. |
| **New Worker** | name → template (Hello, KV cache, D1 notes API, R2 files, Cron, API proxy with secret) or your own code → same analysis, plan and deploy |
| **Secrets & vars** | list, create, update and delete secrets (values are deleted from the chat and never echoed). "Detect from code" downloads the deployed code and lists `env.X` names that are used but not bound. Plain-text vars can be added and removed. |
| **Operations** | deployments and versions → **rollback** to any version; cron triggers (validated); routes on your zones and custom domains (zone auto-detected); **test request** to `https://<worker>.<sub>.workers.dev/<path>`; metrics (requests, errors, sub-requests, CPU p50/p99 over 1h / 24h / 7d through GraphQL Analytics) |
| **Storage** | KV (namespaces, keys, get, put), D1 (databases, tables, **SQL console**), R2 buckets, Queues, zones. Create and delete any of them (delete needs the name typed). Bind any resource to any Worker, from either side. |
| **Notifications** | Every step of every job is sent **and stored**. Watched Workers push a message on each new deployment (deploy, rollback or settings change). |
| **Control surfaces** | slash commands, a persistent reply keyboard and inline buttons. All three drive the same handlers. |
| **Security** | Credentials are AES-256-GCM at rest (key derived with scrypt from `STATE_KEY`). The whole DB is encrypted again before it leaves the runner. Token and secret messages are deleted from the chat. Deploy secret values live only in memory until upload. Output is redacted at every boundary (`cfut_…`, Global Key, `X-Auth-Key`). Owner lock. |

### 🔑 About the "GID token with all permissions"
Cloudflare has **no "GID" token**. The real options are:
1. **API token, "Full" preset** (recommended). Every permission this bot uses, scoped to the accounts and zones you
   pick. You can add an IP filter and an expiry, and revoke it at any time. The bot opens
   `dash.cloudflare.com/profile/api-tokens?permissionGroupKeys=…` with all of them pre-selected.
2. **Global API Key**: the legacy key with *every* permission on *every* account and no scoping. It is sent with your
   login e-mail. It is supported (🔴 highest risk) for users who explicitly want it; the bot detects a 37-hex
   key and asks for the e-mail.

### 🤖 CLOUDFLARE_AI (Hermes architecture)
* Setup: **BASE_URL → API_KEY → `/models` fetched → pick one** (any OpenAI-compatible provider).
* **3-tier frozen system prompt**:
  - SOUL.md identity plus Hermes guidance blocks and a **Cloudflare guidance** block. Among its rules: analyse before deploy, never guess values, ask for missing values, keep secrets out of chat, warn before destructive actions, read the official docs, and the GID explanation.
  - AGENTS.md project map.
  - Skills index, memory, session line and runtime environment (account id, e-mail and access level are included).
* **Tools**:
  - `cloudflare_api` has 43 actions: whoami, workers, code, analyze, deploy (same deployer as the UI and refuses while the plan is incomplete), secrets, vars, bindings, crons, deployments, versions, rollback, workers.dev, settings, routes, domains, zones, metrics, KV, D1, R2, Queues, and `raw` for any v4 endpoint.
  - `cloudflare_docs` reads **developers.cloudflare.com** pages as Markdown.
  - `terminal`, file tools, `web_search` / `web_extract` (Tavily, optional), `memory`, skills, `session_search`, `todo_list`.
* **Skills** (`cfbot/ai/home/skills/cloudflare/`): worker-deploy, worker-debugging, worker-overview, worker-backup,
  secrets-management, storage-selection, token-permissions (plus project/bot-self-maintenance and telegram-file-send).
* Context compression, rate-limit resume (429 / 5xx and network errors), and restart-proof resume of in-flight tasks (`ai_pending`).
* A **"🧠 Review with AI"** button on every Worker card.

---

## 🚀 Deploy (hosting on GitHub Actions)

1. Create a **private** GitHub repo and push this project. It is used only to run the bot.
2. **Settings → Secrets and variables → Actions → Secrets**:

   | Secret | Required | Purpose |
   |--------|----------|---------|
   | `BOT_TOKEN` | ✅ | from @BotFather |
   | `STATE_KEY` | ✅ | ≥16-char random passphrase; encrypts all credentials and the checkpoint. **Back it up.** |
   | `HOST_PAT` | optional | PAT for *this* repo (contents + actions write). Pushes `state/state.enc` to branch `cfbot-state` and dispatches the next run. Falls back to `GITHUB_TOKEN` (alias `GH_PAT`). |
   | `TAVILY_API_KEY` | optional | web search for CLOUDFLARE_AI |

   **Variables** (optional): `OWNER_IDS`, `MAX_RUN_MINUTES` (default 330).
   The **Cloudflare token is not a repo secret**. Each user connects it inside Telegram (`/token`).
3. **Actions → Cloudflare Control Bot → Run workflow**. After that it keeps itself alive.
4. Open the bot in Telegram, send `/start` and follow the token guide.

### Run locally
```bash
pip install -r requirements.txt
cp .env.example .env   # fill BOT_TOKEN + STATE_KEY and export them
python main.py
```

### Tests (75, all green)
```bash
python -m pytest -q
```
* `tests/tg_harness.py` contains **FakeCloudflare**, an in-memory Cloudflare API v4. It reproduces the real response envelopes, error codes, multipart script uploads (metadata + modules), `inherit` bindings, settings PATCH, multipart content download, KV / D1 / R2 / Queues, routes, domains, deployments, versions, GraphQL and 429s. It also has **FakeHost** (host repo) and a real aiogram Dispatcher driven with synthetic Updates.
* `test_telegram_flows.py` (26 tests) covers:
  - Onboarding in EN and FA; exact-policy access levels; official token links; Global Key; bad token.
  - The full worker lifecycle; templates that auto-create KV and crons.
  - `.js` deploy with a var and a secret (the secret is never echoed or stored); linking an existing KV on update while keeping secrets; ZIP with `wrangler.toml` (creates a missing R2 bucket); paste and bad upload; deploy failure.
  - Secrets and vars; deployments, rollback, cron, routes, domains, metrics and the test request.
  - Storage with binding in both directions; permission-error hint; settings, help and cancel; rate limit.
  - AI setup and chat with `cloudflare_api`; AI review button; AI stop.
* `test_ai_tools.py`: `cloudflare_api` end-to-end (analyze → incomplete plan refused → deploy → redeploy keeps the secret → rollback → storage → raw → error codes), and `cloudflare_docs` restricted to the official domain.
* `test_core.py`: crypto, redaction, access levels, token preset URLs, analyzer (every binding kind and the templates), wrangler toml/jsonc, bundle safety, i18n completeness, plus a guard against GitHub remnants in the UI text.
* `test_lifecycle.py`: the full restart cycle (checkpoint → dispatch → restore → AI resume), the deployment watch loop, and a wrong `STATE_KEY`.
* `tests/fake_tg_server.py` boots `main.py` as a real process against a fake Bot API (verified: boots, polls, and SIGTERM gives a clean exit).

---

## 🧭 Commands
| Group | Commands |
|-------|----------|
| Setup | `/start` `/menu` `/lang` `/token` `/scan` |
| Workers | `/workers` `/worker <name>` `/newworker` `/deploy [name]` `/secrets [name]` |
| Storage & metrics | `/storage` `/metrics [name]` |
| AI | `/ai <text>` `/ai_new` `/ai_stop` |
| Other | `/notifications` `/settings` `/restart` `/help` `/cancel` |

Plus the reply keyboard and inline buttons. When CLOUDFLARE_AI is configured, plain text goes to the agent.

## 🏗 Architecture
```
main.py                     restore checkpoint → open DB → build bot → lifecycle → resume AI → poll
cfbot/core/                 config, crypto (AES-GCM), db (SQLite WAL+FTS5), notify, redact, logging
cfbot/cloudflare/           client.py   API v4 client (token or Global Key, retry/429, multipart upload, content v2,
                                        settings/inherit, secrets, crons, workers.dev, deployments/versions,
                                        routes, domains, KV/D1/R2/Queues, GraphQL metrics)
                            tokens.py   official token-template URLs, presets, risk, permission matrix, error hints
                            access.py   capabilities → access level      scanner.py  account scan
                            analyzer.py code/wrangler analysis           bundle.py   file / ZIP → modules
                            deployer.py plan → create resources → upload → crons → workers.dev
                            templates.py ready-to-deploy Workers
cfbot/telegram/             aiogram 3 routers: onboarding (token guide), menu, workers, newworker, deploy,
                            secrets, storage, ops, settings, help, ai_chat; keyboards; middleware
cfbot/ai/                   CLOUDFLARE_AI: agent, llm, prompt_builder, compressor, memory, skills,
                            tools/ (cloudflare_api, cloudflare_docs, terminal, files, web, todo, session_search)
cfbot/ai/home/              SOUL.md, AGENTS.md, skills/**/SKILL.md
cfbot/hosting/              host-repo client (checkpoint branch + workflow dispatch) — hosting only
cfbot/lifecycle/            checkpoint, handoff/dispatch, deployment watch poller
cfbot/i18n/                 en + fa (complete), ru ar tr es de fr zh hi (menus; EN fallback)
docs/                       CONVERSION_CHECKLIST.md, TEST_REPORT.md
```

### Data model (SQLite, `data/cfbot.db`)
* `users`: lang, encrypted credential, Cloudflare e-mail, account id and name, capabilities, access level.
* `kv`: AI config, owners, name-id map, todos, active session.
* `notifications`, and `jobs` with their step log.
* `watches`: worker, account, last deployment.
* `ai_sessions`, `ai_messages` (+ FTS5), `ai_memory`, `ai_pending`.

## ⚠️ Known limitations
* Live Cloudflare calls were verified against an API emulator built from the official API reference, **not against a real account** (no token was available in development). See `docs/TEST_REPORT.md`.
* TypeScript and bare npm imports need a bundling step (wrangler or esbuild). The bot detects them, blocks the deploy and explains why.
* Durable Object migrations beyond the first `new_sqlite_classes`, Workers Assets and Workflows are not managed. Use wrangler for those.
* Live `tail` logs are not implemented (they need a WebSocket). Use Workers Logs (observability toggle) and metrics.

**Stack**: Python 3.12 · aiogram 3 · aiosqlite · httpx · cryptography · **Last updated**: 2026-10-25
