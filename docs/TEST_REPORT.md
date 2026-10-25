# Test report — 2026-10-25

## Automated suite: `python -m pytest -q` → **75 passed** (≈40 s, Python 3.13, aiogram 3)

| File | Tests | What is exercised |
|------|-------|-------------------|
| `test_telegram_flows.py` | 26 | Real aiogram Dispatcher with synthetic Telegram updates against **FakeCloudflare**. Every user flow: onboarding (EN/FA, token, Global Key, bad token), token guide links, workers (card/code/bindings/settings/watch/delete), new worker from templates (KV auto-create, cron), deploy (.js with var+secret, update linking existing KV while keeping secrets, ZIP + wrangler.toml creating missing R2, paste, bad upload, API failure), secrets/vars, ops (deployments/rollback/cron/routes/domains/metrics/test request), storage (KV/D1/R2/Queues/zones + binding both ways), permission-error hints, settings/help/cancel/forget, 429 rate-limit wait, AI setup + chat using `cloudflare_api`, AI review button, AI stop/busy |
| `test_ai_tools.py` | 10 | `cloudflare_api` end-to-end (analyze → refused incomplete plan → deploy → redeploy keeps secret → rollback → KV/D1 → metrics → raw → error codes/hints), `cloudflare_docs` (official domain only), terminal/file tools, blocked secret files (`.env`, `.dev.vars`, DB, checkpoint), memory, skills, todo, session search |
| `test_ai_llm_agent.py` | 12 | LLM client retry/resume, agent loop, CLOUDFLARE_AI system prompt tiers (no GitHub remnants), Cloudflare skills catalog, compression, cancel |
| `test_core.py` | 17 | crypto, redaction (Cloudflare tokens / Global Key), access levels from exact policies, token preset URLs (official domain, `permissionGroupKeys`, read-only preset is read-only), analyzer (all binding kinds, handlers, DO, node/npm imports, service-worker, every template), wrangler toml/jsonc → plan, bundle safety, TypeScript rejection, i18n completeness + placeholder check + GitHub-remnant guard |
| `test_lifecycle.py` | 6 | Full restart cycle on the hosting runner (encrypted checkpoint → dispatch → fresh run restores credential/AI config/skills → interrupted AI task resumes), deployment watch notifications, wrong STATE_KEY, no-PAT local handoff, settings validation, partial tool-result repair |
| `test_db.py` | 4 | users (cf_* columns), kv, notifications, jobs, watches (worker/account/last_deployment), sessions + FTS, memory, pending |

## Real-process boot
`main.py` was started as a real process against `tests/fake_tg_server.py` (`TELEGRAM_API_URL`). It called getMe, deleteWebhook and setMyCommands (new Cloudflare command list), long-polled, and on SIGTERM ran the handoff path and exited cleanly ("bye").

## What was NOT tested (honest)
- **No real Cloudflare account or token was available.** Every Cloudflare call was verified against `FakeCloudflare`. It is an emulator written from the official API reference: envelopes, error codes, multipart upload/metadata, `inherit`, content v2 multipart, pagination and GraphQL shape. Things that can only be confirmed live:
  - exact error codes and messages for some edge cases;
  - GraphQL analytics field availability on every plan;
  - `/user/tokens/{id}` readability for every token type;
  - custom-domain certificate timing.
- The **token-template links** were checked against the documented URL format. Whether the dashboard pre-selects every permission depends on Cloudflare's UI and was not clicked through live.
- Real Telegram (api.telegram.org) and a real LLM provider were not used. Both were faked at the HTTP layer.
- The GitHub Actions hosting workflow was not run on GitHub. Its checkpoint and dispatch logic was tested against `FakeHost`.

## Known functional limitations
- TypeScript and bare npm imports need bundling (wrangler or esbuild). The analyzer detects them and blocks the deploy with an explanation.
- Durable Object migrations beyond the first `new_sqlite_classes`, Workers Assets, Workflows, Hyperdrive and Vectorize creation are not automated. Linking by id/name is supported.
- Live `wrangler tail`-style logs are not implemented (WebSocket). Workers Logs toggle + metrics + test request are provided instead.
- 8 secondary languages translate the menus and onboarding; other texts fall back to English (EN and FA are complete).
