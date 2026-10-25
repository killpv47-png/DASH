# GitHub → Cloudflare conversion checklist

Source project: `killpv47-png/68` (GitHub Control Bot + GITHUB_AI). Every feature of the original was reviewed.
Decision legend:
- **CONVERT**: replaced by the real Cloudflare equivalent.
- **KEEP**: platform-neutral, kept as is (adapted).
- **HOST**: GitHub kept *only* for hosting the bot process.
- **NEW**: did not exist before.
- **DROP**: no Cloudflare meaning; removed (not faked).

| # | Original feature (GitHub) | Decision | Cloudflare implementation (file) | Status |
|---|---------------------------|----------|-----------------------------------|--------|
| 1 | `/start` → language → paste GitHub PAT | CONVERT | Token guide → API token **or** Global API Key + e-mail → `/user/tokens/verify` / `/accounts/{id}/tokens/verify` (`handlers/onboarding.py`) | ✅ tested |
| 2 | PAT regex check, delete token message | CONVERT | `cfut_/cfat_`/legacy-40 token regex, 37-hex Global Key detection; message deleted (`onboarding.py`) | ✅ tested |
| 3 | Account scan (repos, orgs, running jobs, rate budget) | CONVERT | `cloudflare/scanner.py`: accounts, workers.dev subdomain, Workers, KV, D1, R2, Queues, zones, token status and expiry | ✅ tested |
| 4 | Scopes header → access level (GOD…GHOST) | CONVERT | `cloudflare/access.py`: exact token policies → capabilities, or per-product probing → GOD / ARCHITECT / ENGINEER / OBSERVER / GHOST | ✅ tested |
| 5 | Fine-grained token probing | CONVERT | Probing per product when `/user/tokens/{id}` is not readable | ✅ tested |
| 6 | Multiple owners/orgs picker | CONVERT | Account picker (`acct:set:`) when the token sees more than one account | ✅ |
| 7 | Repo list (paged) | CONVERT | Worker list (paged) `handlers/workers.py` | ✅ tested |
| 8 | Repo card | CONVERT | Worker card: URL, handlers, compat date and flags, usage model, crons, bindings, logpush | ✅ tested |
| 9 | File tree / view file | CONVERT | View Worker code (`/content/v2` multipart) and download it as a ZIP | ✅ tested |
| 10 | Edit repo (private, issues, wiki, description, default branch) | CONVERT | Worker settings: workers.dev on/off, logpush, observability, `nodejs_compat`, compatibility date | ✅ tested |
| 11 | Delete repo (type-name confirm) | CONVERT | Delete Worker (type-name confirm, `force=true`) | ✅ tested |
| 12 | Watch repo runs → notifications | CONVERT | Watch Worker deployments (`lifecycle/handoff.py:poll_watches`) | ✅ tested |
| 13 | New-repo wizard | CONVERT | New-Worker wizard: name → 6 real templates or own code → analysis → plan → deploy (`handlers/newworker.py`, `cloudflare/templates.py`) | ✅ tested |
| 14 | .gitignore / license templates | DROP | No Cloudflare meaning. Replaced by Worker templates (#13). | — |
| 15 | Upload ZIP → one commit | CONVERT | Upload `.js/.mjs/.cjs/.py/.zip` or paste code → `bundle.py` → multipart script upload (`deployer.py`) | ✅ tested |
| 16 | ZIP single-root strip / `__MACOSX` / traversal filter | KEEP | `bundle.py`: common-root strip, ignored dirs, safe paths, size limits | ✅ tested |
| 17 | "Delete existing files?" (wipe vs layer) | CONVERT | Update keeps existing bindings and secrets (`inherit`). A new upload replaces the code. | ✅ tested |
| 18 | Detect `${{ secrets.X }}` → offer missing secrets | CONVERT | **Analyzer** detects every `env.X` and its kind (var, secret, KV, D1, R2, Queue, DO, service, AI…) plus wrangler config → plan asks for each missing value (`analyzer.py`, `deployer.py`) | ✅ tested |
| 19 | — | NEW | Auto-create KV, D1, R2 and Queues and bind them; link existing ones (picker or id); set crons; enable workers.dev; Deploy only when nothing is pending | ✅ tested |
| 20 | Secrets CRUD (sealed box) | CONVERT | Worker secrets CRUD (`/secrets`), values deleted from chat | ✅ tested |
| 21 | Scan workflows for missing secrets | CONVERT | "Detect from code": download the deployed code and list unbound `env.X` | ✅ tested |
| 22 | Actions variables | CONVERT | Plain-text vars (`plain_text` bindings) add/remove; secrets preserved | ✅ tested |
| 23 | Actions: workflows / runs / jobs | CONVERT | Deployments and versions (`ops.py`) | ✅ tested |
| 24 | Cancel / re-run run | CONVERT | **Rollback** to any version (`POST /deployments` 100%) | ✅ tested |
| 25 | Job log tail | CONVERT | Test request to workers.dev, metrics (GraphQL `workersInvocationsAdaptive`) and the Workers Logs toggle. Live `tail` is not implemented (needs WebSocket). | ⚠️ partial |
| 26 | `workflow_dispatch` | CONVERT | Cron triggers (set/clear) plus a manual test request | ✅ tested |
| 27 | "Running now" view | CONVERT | Metrics over all Workers (1h / 24h / 7d) | ✅ tested |
| 28 | — | NEW | Storage manager: KV keys get/put, D1 SQL console, R2, Queues, zones; bind from either side | ✅ tested |
| 29 | — | NEW | Routes on zones and custom domains (zone auto-detected) | ✅ tested |
| 30 | Issues / PRs / releases / code search / org members (AI tool only) | DROP | No Cloudflare equivalent. Removed with `github_tool.py`. | — |
| 31 | GITHUB_AI agent (prompt, tools, skills, memory) | CONVERT | CLOUDFLARE_AI: new SOUL/AGENTS, Cloudflare guidance block, `cloudflare_api` (43 actions, same deployer), `cloudflare_docs` (official docs), 7 Cloudflare skills, Worker review button | ✅ tested |
| 32 | Notifications + job step history | KEEP | Unchanged, now fed by Cloudflare operations | ✅ tested |
| 33 | Reply keyboard / slash commands / inline buttons, 10 languages | KEEP | New menu (Workers, New, Deploy, Storage, Secrets, AI, Metrics, Scan, Notifications, Token, Settings, Help); EN and FA complete, 8 others with menus | ✅ tested |
| 34 | Self-restart on GitHub Actions (checkpoint + dispatch) | HOST | `hosting/github_host.py` (checkpoint branch `cfbot-state` + dispatch only), env `HOST_PAT` | ✅ tested |
| 35 | Encryption, redaction, owner lock | KEEP | Redaction extended with Cloudflare tokens, Global Key and `X-Auth-Key` | ✅ tested |
| 36 | — | NEW | **Token guide**: 5 presets with official pre-filled links (user and account token), minimum permissions, risk, feature → permission matrix, Global API Key path, and the "GID" explanation | ✅ tested |

## "GID token with all permissions"
Researched in the official docs: Cloudflare has no "GID" credential. The two real "all permissions" options are implemented:
- the **Full** API-token preset (recommended, scoped and revocable);
- the **Global API Key** (legacy, unscoped; 🔴).

Both are explained in the bot (`tok:gk`, `tok:p:full`), in the AI guidance and in the `token-permissions` skill.

## Official references used
- API v4 envelope and auth: developers.cloudflare.com/fundamentals/api/
- Token templates (`permissionGroupKeys` URL): developers.cloudflare.com/fundamentals/api/how-to/account-owned-token-template/
- Permission names: developers.cloudflare.com/fundamentals/api/reference/permissions/
- Workers script upload (multipart metadata, `main_module`, bindings, `keep_bindings`), settings, content v2, secrets, schedules, subdomain, deployments and versions, domains, routes: developers.cloudflare.com/api/resources/workers/
- KV, D1, R2, Queues REST: the corresponding `/api/resources/*` pages
- GraphQL Workers analytics: developers.cloudflare.com/analytics/graphql-api/
- Limits (script size, compatibility dates and flags): developers.cloudflare.com/workers/platform/limits/, /workers/configuration/compatibility-flags/
