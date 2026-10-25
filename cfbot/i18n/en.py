STRINGS = {
    # --- onboarding / language
    "choose_lang": "🌐 <b>Choose your language</b>\nزبان خود را انتخاب کنید",
    "lang_set": "✅ Language set to <b>{lang}</b>.",
    "welcome": (
        "👋 <b>Welcome to Cloudflare Control Bot</b>\n\n"
        "Manage your Cloudflare account from Telegram — above all <b>Workers</b>: create, deploy code with automatic "
        "analysis of what it needs, secrets & variables, KV / D1 / R2 / Queues, crons, routes, domains, rollback, metrics — "
        "and <b>CLOUDFLARE_AI</b>, an agent that can do all of it for you.\n\n"
        "🔑 To begin, connect a <b>Cloudflare API token</b>. Pick a preset below: it opens the official Cloudflare page with "
        "the permissions already selected. Create the token there, copy it and paste it here.\n\n"
        "🔒 Your credential is encrypted with AES-256-GCM before it touches the database and is never shown again."
    ),
    "send_token": "🔑 Paste your Cloudflare <b>API token</b> now (or a <b>Global API Key</b> — I will then ask for the account e-mail).\n<i>The message is deleted right after reading.</i>",
    "token_invalid": "❌ That doesn't look like a Cloudflare API token (40+ characters) or a Global API Key (37 hex characters). Try again or pick a preset.",
    "token_checking": "🔍 Verifying the credential with Cloudflare and scanning your account…",
    "token_bad": "❌ Cloudflare rejected the credential: <code>{error}</code>\n{hint}\nSend another one or pick a preset.",
    "token_saved": "✅ Credential saved (encrypted) — type: <b>{kind}</b>.",
    "kind_user": "user API token",
    "kind_account": "account API token",
    "kind_global_key": "Global API Key (full access)",
    "gk_detected": "🗝 That looks like a <b>Global API Key</b>. Send the <b>e-mail address</b> of your Cloudflare login (required with this key).",
    "gk_ask_email": "🗝 <b>Global API Key</b>\nStep 1/2 — send the <b>e-mail</b> of your Cloudflare account:",
    "gk_ask_key": "Step 2/2 — paste the <b>Global API Key</b> (37 hex characters).\n<i>The message is deleted right after reading.</i>",
    "gk_email_bad": "❌ That is not a valid e-mail address.",
    "gk_key_bad": "❌ A Global API Key is exactly 37 lowercase hex characters.",
    "not_owner": "⛔ This bot is private. Your Telegram id <code>{id}</code> is not authorized.",

    # --- token guide
    "tok_home": (
        "🔑 <b>Cloudflare token guide</b>\n\n"
        "Pick what the bot should be allowed to do. Each preset opens the <b>official Cloudflare token page</b> with the "
        "permissions pre-filled — review, press <i>Continue to summary → Create Token</i>, copy the token and paste it here.\n\n"
        "• <b>Full</b> — everything this bot can do (recommended if you want all features)\n"
        "• <b>Workers deploy</b> — only Workers scripts (minimum to deploy code)\n"
        "• <b>Workers + Storage</b> — Workers + KV, D1, R2, Queues, metrics\n"
        "• <b>Routes & Domains</b> — attach Workers to your own domains\n"
        "• <b>Read only</b> — browse, no changes\n"
        "• <b>Global API Key</b> — legacy key with every permission (not recommended)\n\n"
        "<i>There is no Cloudflare credential called “GID”; the closest real options are the Full preset or the Global API Key.</i>"
    ),
    "tok_btn_full": "👑 Full access (all bot features)",
    "tok_btn_workers": "⚡ Workers deploy",
    "tok_btn_storage": "🗄 Workers + Storage",
    "tok_btn_routes": "🌐 Routes & Domains",
    "tok_btn_readonly": "👁 Read only",
    "tok_btn_global": "🗝 Global API Key (all permissions)",
    "tok_btn_matrix": "📋 Which feature needs which permission",
    "tok_btn_paste": "📥 I have a token — paste it",
    "tok_preset": (
        "{title}\n\n{desc}\n\n<b>Permissions</b> (pre-selected on the Cloudflare page):\n{perms}\n\n"
        "<b>Risk</b>: {risk}\n\n"
        "1️⃣ Open the link (user token = tied to you; account token = owned by the account, survives member changes)\n"
        "2️⃣ Optionally restrict accounts / zones, add IP filter and expiry\n"
        "3️⃣ Create → copy → tap <i>paste</i> and send it here"
    ),
    "tok_full": "All Workers, storage, Pages, routes and DNS permissions this bot uses, plus read access to account settings, analytics and the token's own permissions (so the bot can show exactly what it may do).",
    "tok_workers": "Minimum to list, view, deploy, configure and delete Workers (secrets, vars, crons, rollback). No storage creation.",
    "tok_storage": "Deploy Workers and automatically create/bind KV namespaces, D1 databases, R2 buckets and Queues; view metrics.",
    "tok_routes": "Attach Workers to routes and custom domains on your zones (needs DNS edit for custom domains).",
    "tok_readonly": "Browse Workers, storage, zones and metrics. Nothing can be changed — safest for monitoring.",
    "risk_low": "🟢 low — read only",
    "risk_medium": "🟡 medium — can change the listed resources",
    "risk_high": "🔴 high — can change and delete Workers, storage and DNS. Restrict accounts/zones and set an expiry if possible.",
    "tok_open_user": "🔗 Create user token (official page)",
    "tok_open_account": "🏢 Create account token (official page)",
    "tok_matrix": "📋 <b>Feature → required permission</b>\n\n{list}\n\nOfficial reference: {docs}",
    "tok_global": (
        "🗝 <b>Global API Key</b>\n\n"
        "The legacy key of your Cloudflare user: <b>every permission on every account</b> you belong to. It cannot be "
        "scoped, filtered by IP or given an expiry, and it must be sent together with your login e-mail.\n\n"
        "🔴 Highest risk — prefer the <b>Full access</b> token preset. Use the key only if you understand the risk; rotate it "
        "from the same page if it ever leaks.\n\n"
        "Where: My Profile → API Tokens → <i>Global API Key</i> → View.\nDocs: {docs}"
    ),
    "tok_open_gk": "🔗 Open API Tokens page",
    "tok_gk_use": "🗝 I understand — use a Global API Key",

    # --- scan
    "scan_step": "⏳ Scanning: <b>{step}</b>…",
    "scan_report": (
        "📊 <b>Cloudflare account scan</b>\n\n"
        "👤 {email} · {kind}\n"
        "🏢 Account: <b>{account}</b> ({accounts} visible)\n"
        "⚡ Workers: <b>{workers}</b> · workers.dev: <code>{subdomain}</code>\n"
        "🗂 KV {kv} · 🗄 D1 {d1} · 🪣 R2 {r2} · 📨 Queues {queues} · 🌐 Zones {zones}\n"
        "⏳ Token expires: {expires}\n\n"
        "🔐 <b>Access level: {level_emoji} {level}</b>\n<i>{level_desc}</i>\n"
        "🧾 Capabilities ({exact}): {caps}"
    ),
    "scan_perms": "🧾 Token permissions: <code>{perms}</code>",
    "caps_exact": "exact, from the token's policies",
    "caps_probed": "probed — write access is confirmed on first use",
    "scan_errors": "⚠️ Partial scan: {errors}",
    "access_god": "GOD — full control: Workers, all storage, routes and DNS. Handle with care.",
    "access_architect": "ARCHITECT — deploy Workers and create/bind storage (KV / D1 / R2 / Queues).",
    "access_engineer": "ENGINEER — deploy and configure Workers (code, secrets, vars, crons). No storage creation.",
    "access_observer": "OBSERVER — read-only access.",
    "access_ghost": "GHOST — the credential works but has no Workers or storage permission.",
    "access_level": "Access level",

    # --- main menu
    "menu_title": "🏠 <b>Main Menu</b> — {account} {level_emoji}\nChoose an action:",
    "btn_workers": "⚡ Workers",
    "btn_new_worker": "➕ New Worker",
    "btn_deploy": "🚀 Deploy code",
    "btn_storage": "🗄 Storage",
    "btn_secrets": "🔐 Secrets",
    "btn_ai": "🤖 CLOUDFLARE_AI",
    "btn_analytics": "📈 Analytics",
    "btn_scan": "📊 Rescan",
    "btn_notifs": "🔔 Notifications",
    "btn_tokens": "🔑 Token guide",
    "btn_help": "📖 Docs",
    "btn_settings": "⚙️ Settings",
    "btn_back": "⬅️ Back",
    "btn_cancel": "✖️ Cancel",
    "btn_yes": "✅ Yes",
    "btn_no": "❌ No",
    "btn_menu": "🏠 Menu",
    "btn_refresh": "🔄 Refresh",
    "btn_more": "➡️ More",
    "btn_prev": "⬅️ Prev",
    "btn_open": "📂 Open",
    "cancelled": "✖️ Cancelled.",
    "need_token": "🔑 Connect a Cloudflare token first — use /token.",

    # --- workers
    "workers_title": "⚡ <b>Your Workers</b> ({n}) — page {page}/{pages}\nTap one to manage it:",
    "workers_empty": "📭 No Workers in this account yet. Create one with ➕ New Worker or 🚀 Deploy code.",
    "worker_card": (
        "⚡ <b>{name}</b>\n🔗 {url}\n\n"
        "Handlers: <code>{handlers}</code>\nCompatibility: <code>{compat}</code> · flags: <code>{flags}</code>\n"
        "Usage model: {usage} · Logpush: {logpush}\nCron: <code>{crons}</code>\n"
        "🕒 Modified {modified} · created {created}\n\n<b>Bindings ({nb})</b>\n{bindings}"
    ),
    "btn_w_deploy": "🚀 Deploy new code",
    "btn_w_code": "📄 Code",
    "btn_w_secrets": "🔐 Secrets & vars",
    "btn_w_bindings": "🧩 Bindings",
    "btn_w_deployments": "🕘 Deployments",
    "btn_w_cron": "⏰ Cron",
    "btn_w_routes": "🌐 Routes & domains",
    "btn_w_metrics": "📈 Metrics",
    "btn_w_test": "🧪 Test request",
    "btn_w_settings": "🛠 Settings",
    "btn_w_watch": "🔔 Watch deploys",
    "btn_w_unwatch": "🔕 Unwatch",
    "btn_w_ai": "🤖 Ask AI about it",
    "btn_w_delete": "🗑 Delete Worker",
    "worker_code": "📄 <b>{name}</b> — modules:\n{files}\n\n<b>{main}</b> (preview):\n<pre>{code}</pre>",
    "worker_code_zip": "📦 Full source of <b>{name}</b> — edit and send it back via 🚀 Deploy.",
    "bindings_title": "🧩 <b>Bindings of {name}</b>\n{list}\n\nTap ✖️ to remove a binding (secrets are managed under 🔐).",
    "btn_bind_add": "➕ Bind KV / D1 / R2 / Queue",
    "binding_removed": "✖️ Binding <code>{binding}</code> removed from <b>{name}</b>.",
    "watch_on": "🔔 You will be notified about new deployments of <b>{name}</b>.",
    "watch_off": "🔕 Stopped watching <b>{name}</b>.",
    "watch_event": "🔔 <b>{worker}</b> — new deployment\nSource: {source} · by {author}\nVersions: <code>{versions}</code>\nMessage: {message}\n🕒 {when}",
    "worker_edit_title": "🛠 <b>Settings of {name}</b>",
    "btn_wdev_on": "🌍 workers.dev ON",
    "btn_wdev_off": "🚫 workers.dev OFF",
    "btn_logpush": "📤 Toggle logpush",
    "btn_observability": "👁 Toggle Workers Logs",
    "btn_compat": "📅 Compatibility date",
    "btn_nodecompat": "🟩 Toggle nodejs_compat",
    "ask_compat": "📅 Send the new compatibility date (YYYY-MM-DD):",
    "compat_bad": "❌ Use the format YYYY-MM-DD.",
    "worker_updated": "✅ <b>{name}</b> updated: {what}",
    "worker_delete_confirm": "🗑 <b>Delete {name}?</b>\nCode, bindings, secrets, crons and routes of this Worker are removed. Storage (KV/D1/R2) is NOT deleted.\nType <code>{name}</code> to confirm.",
    "worker_delete_mismatch": "❌ Name mismatch — nothing was deleted.",
    "worker_deleted": "🗑 Worker <b>{name}</b> deleted.",
    "worker_name_bad": "❌ Invalid Worker name: lowercase letters, digits and dashes, 1–63 characters, not starting/ending with a dash.",

    # --- new worker
    "nw_name": "➕ <b>New Worker</b>\n\nStep 1/2 — send the Worker <b>name</b> (lowercase, digits, dashes):",
    "nw_exists": "⚠️ A Worker named <b>{name}</b> already exists. Send another name, or use 🚀 Deploy to update it.",
    "nw_template": "Step 2/2 — start <b>{name}</b> from a template, or send your own code:",
    "btn_nw_own": "📤 Upload / paste my own code",
    "nw_tpl_chosen": "🧩 Template <b>{title}</b> → <b>{name}</b>. Analyzing…",

    # --- deploy
    "dp_pick": "🚀 <b>Deploy code</b>\nChoose the Worker to update, or create a new one:",
    "btn_dp_new": "➕ New Worker",
    "dp_ask_name": "Send the <b>name</b> of the new Worker (lowercase letters, digits, dashes):",
    "dp_send_code": (
        "📤 Send the code for <b>{name}</b>:\n"
        "• a <code>.js</code> / <code>.mjs</code> / <code>.py</code> file\n"
        "• a <code>.zip</code> project (wrangler.toml / wrangler.json is read: vars, KV, D1, R2, queues, crons…)\n"
        "• or paste the code as a message\n\n"
        "I will analyze it and show exactly what it needs before anything is deployed."
    ),
    "dp_too_big": "❌ File too large (max 20 MB via Telegram).",
    "dp_not_code": "❌ That doesn't look like Worker code (expected <code>export default {…}</code>, <code>addEventListener('fetch')</code> or a Python Worker).",
    "dp_bad_bundle": "❌ Cannot use this upload: {error}",
    "dp_analysis": (
        "🔎 <b>Code analysis</b>\n"
        "Entry: <code>{main}</code> ({fmt}) · {modules} module(s) · {size}\n"
        "Handlers: <code>{handlers}</code>\n"
        "Compatibility: <code>{compat}</code> · flags: <code>{flags}</code>\n"
        "Cron in config: <code>{crons}</code> · config file: <code>{config}</code>\n\n"
        "<b>What the code needs</b>\n{needs}"
    ),
    "dp_routes_note": "Routes in config ({routes}) — add them afterwards under 🌐 Routes & domains.",
    "dp_skipped": "⚠️ {n} file(s) ignored (unsafe paths, node_modules, too large).",
    "plan_title": (
        "📋 <b>Deploy plan — {name}</b> ({mode})\n\n{items}\n\n"
        "⏰ Cron: <code>{crons}</code> · 🌍 workers.dev: {wdev}\n\n{state}"
    ),
    "plan_new": "new Worker",
    "plan_update": "update existing — current bindings and secrets are kept",
    "plan_create": "→ create <code>{name}</code>",
    "plan_value_set": "→ value set",
    "plan_keep": "→ keep current",
    "plan_skip": "→ skipped (may fail at runtime)",
    "plan_pending": "→ <b>needs your input</b>",
    "plan_pending_n": "❓ {n} item(s) need your input — tap them.",
    "plan_ready": "✅ Ready. Tap <b>Deploy</b> to create the resources and upload.",
    "plan_blocked": "⛔ Blocked — fix the problems listed in the analysis and send the code again.",
    "plan_item": "🧩 <b>{name}</b> — detected as <b>{kind}</b>\n<i>{note}</i>\n{advice}\n\nWhat should I do? (⇄ changes the type if the guess is wrong)",
    "btn_it_create": "🆕 Create new (automatic)",
    "btn_it_link": "🔗 Use an existing one",
    "btn_it_value": "✏️ Enter value",
    "btn_it_as_secret": "🔐 Treat as secret",
    "btn_it_as_var": "📝 Treat as plain variable",
    "btn_it_target": "⌨️ Type id / name",
    "btn_it_skip": "⏭ Skip",
    "btn_plan_cron": "⏰ Set cron",
    "btn_plan_wdev": "🌍 Toggle workers.dev",
    "btn_plan_deploy": "🚀 Deploy",
    "dp_ask_secret": "🔐 Send the secret value for <code>{name}</code>.\n<i>Your message is deleted immediately; the value is kept only in memory until upload.</i>",
    "dp_ask_var": "📝 Send the value for variable <code>{name}</code>:",
    "dp_ask_target": "⌨️ Send the target for <code>{name}</code> ({kind}): KV namespace id, D1 database id, R2 bucket name, queue name, service (Worker) name or Durable Object class:",
    "dp_pick_existing": "🔗 Existing {kind} ({n}) — pick one:",
    "dp_ask_cron": "⏰ Send cron expressions, one per line (e.g. <code>*/15 * * * *</code>), or <code>-</code> for none:",
    "dp_starting": "🚀 Deploying <b>{name}</b>…",
    "dp_progress": "🚀 {msg}",
    "dp_done": (
        "🎉 <b>{name}</b> deployed!\n🔗 {url}\n\n<b>Created</b>\n{created}\n\n"
        "<b>Bindings</b>: {bindings}\n⏰ Cron: {crons}"
    ),
    "dp_fail": "❌ Deploy failed: <code>{error}</code>",
    "btn_open_card": "⚡ Open Worker",

    # --- secrets
    "sec_pick": "🔐 <b>Secrets & variables</b>\nChoose a Worker:",
    "sec_title": "🔐 <b>Secrets of {name}</b> ({n})\n{list}\n\nValues are never shown (Cloudflare does not return them).",
    "sec_item": "• <code>{name}</code>",
    "sec_none": "<i>no secrets yet</i>",
    "btn_sec_add": "➕ New secret",
    "btn_sec_scan": "🔎 Detect from code",
    "btn_sec_vars": "📝 Variables",
    "sec_ask_name": "🔐 Send the <b>secret name</b> (letters, digits, _):",
    "sec_name_bad": "❌ Invalid name. Use letters, digits and underscores, starting with a letter or _.",
    "sec_ask_value": "🔑 Send the <b>value</b> for <code>{key}</code>.\n<i>Your message will be deleted immediately after reading.</i>",
    "sec_saved": "✅ Secret <code>{key}</code> saved on <b>{name}</b> (a new deployment was created).",
    "sec_deleted": "🗑 Secret <code>{key}</code> deleted.",
    "sec_actions": "🔐 <code>{key}</code> on <b>{name}</b>",
    "btn_sec_update": "✏️ Update value",
    "btn_sec_delete": "🗑 Delete",
    "sec_detect_result": "🔎 The deployed code uses: {all}\nNot bound yet: <b>{missing}</b>\nTap one to set it.",
    "sec_detect_none": "🔎 No JavaScript/Python modules found in the deployed Worker.",
    "vars_title": "📝 <b>Variables of {name}</b>\n{list}",
    "vars_item": "• <code>{key}</code> = <code>{value}</code>",
    "btn_var_add": "➕ New variable",
    "var_ask_name": "📝 Send the <b>variable name</b>:",
    "var_ask_value": "📝 Send the <b>value</b> for <code>{key}</code> (visible in the dashboard — use a secret for credentials):",
    "var_saved": "✅ Variable <code>{key}</code> saved.",

    # --- ops: deployments / cron / routes / test / metrics
    "deps_title": "🕘 <b>Deployments of {name}</b>\n{deps}\n\n<b>Versions</b> (🟢 = live)\n{versions}",
    "dep_item": "• {when} · {source} · {author}\n  <code>{versions}</code>",
    "ver_item": "{active} <code>{id}</code> #{n} · {when} · {source} {msg}",
    "btn_rollback": "↩️ Roll back to {id}",
    "rollback_confirm": "↩️ Make version <code>{id}</code> of <b>{name}</b> live (100% traffic)?",
    "rollback_done": "↩️ <b>{name}</b> now serves version <code>{id}</code>.",
    "cron_title": "⏰ <b>Cron triggers of {name}</b>\n<code>{crons}</code>\n\nSend new expressions (one per line, UTC) to replace them, e.g. <code>0 */6 * * *</code>.",
    "btn_cron_clear": "🧹 Remove all",
    "cron_bad": "❌ Invalid cron expression(s): <code>{bad}</code> — 5 fields: minute hour day month weekday.",
    "cron_saved": "⏰ Cron for <b>{name}</b>: <code>{crons}</code>",
    "routes_title": "🌐 <b>Routes & domains of {name}</b>\nworkers.dev: {wdev}\n\n<b>Routes</b>\n{routes}\n\n<b>Custom domains</b>\n{domains}",
    "btn_route_add": "➕ Add route",
    "btn_domain_add": "➕ Add custom domain",
    "route_ask": "🛣 Send the route pattern, e.g. <code>example.com/api/*</code> or <code>*.example.com/*</code> (the zone must be in this account):",
    "domain_ask": "🌐 Send the hostname, e.g. <code>api.example.com</code> — Cloudflare creates the DNS record and certificate:",
    "zone_not_found": "❌ No zone in this account matches <code>{host}</code> (or the token lacks Zone Read).",
    "route_added": "✅ Route <code>{pattern}</code> added on zone {zone}.",
    "domain_added": "✅ Custom domain <code>{host}</code> attached (certificate issuance can take a few minutes).",
    "route_deleted": "🗑 Route removed.",
    "domain_deleted": "🗑 Custom domain detached.",
    "test_ask": "🧪 Send a path to request on workers.dev, e.g. <code>/</code>, <code>/api/health</code> or <code>POST /items</code>:",
    "btn_test_root": "🧪 GET /",
    "test_result": "🧪 <b>{method}</b> {url}\nStatus <b>{status}</b> · {ms} ms · {ctype} · cf-ray {ray}\n<pre>{body}</pre>",
    "test_fail": "❌ Request to {url} failed: <code>{error}</code>",
    "test_no_subdomain": "⚠️ This account has no workers.dev subdomain yet — register one in the dashboard (Workers & Pages).",
    "metrics_title": "📈 <b>Metrics — {scope}</b> (last {hours}h)\n{list}",
    "metrics_item": "⚡ <b>{name}</b>: {req} req · {err} errors ({rate}%) · {sub} subreq · CPU p50 {p50} ms / p99 {p99} ms",
    "metrics_none": "<i>no invocations in this period</i>",
    "metrics_perm": "💡 Metrics need the <b>Account Analytics Read</b> permission.",
    "all_workers": "all Workers",

    # --- storage
    "st_home": "🗄 <b>Storage</b>\nKV (key-value) · D1 (SQL) · R2 (files) · Queues (jobs)",
    "btn_zones": "🌐 Zones",
    "st_list": "{kind} — {n} item(s):",
    "btn_st_create": "➕ Create",
    "st_ask_name": "Send a name for the new {kind}:",
    "st_created": "✅ {kind} <b>{name}</b> created (<code>{id}</code>).",
    "st_item": "{kind} <b>{ref}</b>\n\n{detail}",
    "btn_kv_get": "🔍 Get key",
    "btn_kv_put": "✏️ Put key",
    "kv_ask_key": "🔑 Send the key name:",
    "kv_ask_value": "✏️ Send the value:",
    "kv_value": "🔑 <code>{key}</code>\n<pre>{value}</pre>",
    "kv_saved": "✅ Key <code>{key}</code> saved.",
    "btn_d1_sql": "🧮 Run SQL",
    "btn_d1_more": "🧮 Another query",
    "d1_ask_sql": "🧮 Send an SQL statement (SQLite syntax). Destructive statements run immediately — be careful.",
    "d1_result": "🧮 <code>{sql}</code>\n<pre>{out}</pre>",
    "btn_bind_worker": "🧩 Bind to a Worker",
    "btn_st_delete": "🗑 Delete",
    "st_delete_confirm": "🗑 Delete {kind} <b>{name}</b> and ALL its data? Type <code>{name}</code> to confirm.",
    "st_deleted": "🗑 <b>{name}</b> deleted.",
    "st_pick_worker": "🧩 Bind to which Worker?",
    "st_pick_kind": "🧩 What do you want to bind?",
    "st_ask_binding": "🧩 Send the binding name the code uses (e.g. <code>DB</code>, <code>CACHE</code>, <code>BUCKET</code>):",
    "st_bound": "✅ <code>{binding}</code> bound to <b>{worker}</b> (new deployment created).",
    "zones_title": "🌐 <b>Zones</b> ({n})\n{list}",

    # --- notifications
    "notif_title": "🔔 <b>Recent notifications</b>\n{list}",
    "notif_none": "<i>no notifications yet</i>",
    "notif_item": "<code>{time}</code> {text}",
    "jobs_title": "🧾 <b>Recent jobs</b>\n{list}",
    "job_item": "{icon} <b>{title}</b> — {status} ({steps} steps)",

    # --- settings
    "settings_title": (
        "⚙️ <b>Settings</b>\n"
        "Language: {lang}\nCloudflare: {email} · account <b>{account}</b> ({level})\nAI: {ai}\nWatched Workers: {watches}\n"
        "Runtime: {runtime}"
    ),
    "btn_change_lang": "🌐 Language",
    "btn_change_token": "🔑 Change Cloudflare token",
    "btn_switch_account": "🏢 Switch account / rescan",
    "btn_forget_token": "🧹 Forget my credential",
    "forget_confirm": "🧹 Remove your stored Cloudflare credential from the bot? (It stays valid at Cloudflare — revoke it in the dashboard if needed.)",
    "forget_done": "🧹 Credential removed. Use /token to connect again.",
    "btn_ai_reset": "🤖 Reconfigure AI",
    "btn_export": "💾 Save state now",
    "btn_restart": "♻️ Restart bot (new run)",
    "export_done": "💾 State checkpoint pushed.",
    "export_fail": "❌ Checkpoint failed: {error}",
    "restart_confirm": "♻️ Hand off to a fresh hosting run now? Nothing will be lost — state is checkpointed first.",
    "restart_go": "♻️ Handing off… I'll message you from the new run in ~30–60s.",
    "restart_not_actions": "ℹ️ Not running on GitHub Actions hosting — restart means restarting the local process.",

    # --- lifecycle
    "lifecycle_hello": "🟢 <b>Bot online</b> — run <code>#{run}</code> (attempt {attempt}).\nState restored: {restored}. Uptime budget: {minutes} min.",
    "lifecycle_bye": "🟠 Run budget reached. Checkpointing and starting a new run… back in ~1 min.",
    "lifecycle_resume_ai": "♻️ Resuming your interrupted CLOUDFLARE_AI task from where it stopped…",
    "lifecycle_no_pat": "⚠️ <code>HOST_PAT</code> is missing — I cannot checkpoint state or restart myself on the hosting runner. Set it in the host repo secrets.",

    # --- AI
    "ai_setup_base": (
        "🤖 <b>CLOUDFLARE_AI setup</b>\n\nStep 1/3 — Send the <b>BASE_URL</b> of an OpenAI-compatible API "
        "(e.g. <code>https://api.openai.com/v1</code>, <code>https://openrouter.ai/api/v1</code>):"
    ),
    "ai_setup_key": "Step 2/3 — Send the <b>API_KEY</b>.\n<i>Your message will be deleted after reading.</i>",
    "ai_fetching_models": "🔎 Fetching model list from <code>{base}</code>…",
    "ai_models_fail": "❌ Could not list models: <code>{error}</code>\nSend a model name manually, or /cancel.",
    "ai_pick_model": "Step 3/3 — Pick a <b>model</b> ({n} found, page {page}/{pages}) or send a name:",
    "ai_ready": "✅ CLOUDFLARE_AI ready.\nBase: <code>{base}</code>\nModel: <code>{model}</code>\n\nAsk me anything about your Workers — I can analyze, deploy and configure them.",
    "ai_home": (
        "🤖 <b>CLOUDFLARE_AI</b> — model <code>{model}</code>\n"
        "Session: <code>{session}</code> · {msgs} msgs · {compressions} compactions\n"
        "Memory: {mem} entries · Skills: {skills}\n\n"
        "Just type your request. Tools: Cloudflare API, official docs, terminal, files, web search{search}, memory, skills, todo."
    ),
    "btn_ai_new": "🆕 New session",
    "btn_ai_sessions": "🗂 Sessions",
    "btn_ai_memory": "🧠 Memory",
    "btn_ai_skills": "🧩 Skills",
    "btn_ai_model": "🔄 Change model",
    "btn_ai_stop": "⏹ Stop",
    "ai_new_session": "🆕 New session <code>{id}</code> started.",
    "ai_thinking": "🤖 Thinking…",
    "ai_tool_call": "🔧 <code>{tool}</code> {args}",
    "ai_tool_result": "↩️ {tool}: {summary}",
    "ai_rate_limited": "⏳ Model rate-limited — waiting {secs}s then resuming the same step (attempt {n}).",
    "ai_api_error": "⚠️ API error: <code>{error}</code> — retrying in {secs}s.",
    "ai_compressing": "🗜 Context is large — compressing older turns (nothing is lost; a summary replaces them).",
    "ai_done": "✅ Done ({iters} steps, {tools} tool calls).",
    "ai_stopped": "⏹ Stopped.",
    "ai_busy": "⏳ CLOUDFLARE_AI is still working on your previous request. Tap Stop to interrupt.",
    "ai_not_configured": "🤖 CLOUDFLARE_AI is not configured yet. Tap 🤖 CLOUDFLARE_AI to set BASE_URL, API_KEY and model.",
    "ai_sessions_title": "🗂 <b>Sessions</b>\n{list}",
    "ai_session_item": "{active} <code>{id}</code> {title} — {msgs} msgs",
    "ai_memory_title": "🧠 <b>Memory</b>\n<b>MEMORY</b>\n{memory}\n\n<b>USER</b>\n{user}",
    "ai_memory_empty": "<i>empty</i>",
    "ai_skills_title": "🧩 <b>Skills</b>\n{list}",
    "ai_skill_item": "• <code>{name}</code> — {desc}",
    "ai_max_iter": "⚠️ Reached the step limit ({n}). Send 'continue' to keep going.",
    "ai_file_received": "📎 Got <b>{name}</b> — tell me what to do with it (e.g. “analyze and deploy as my-api”), or use 🚀 Deploy.",

    # --- help
    "btn_help_arch": "🏗 Architecture",
    "btn_help_workers": "⚡ Workers",
    "btn_help_tokens": "🔑 Tokens",
    "btn_help_ai": "🤖 CLOUDFLARE_AI",
    "btn_help_cmds": "⌨️ Commands",
    "btn_help_security": "🔒 Security",

    # --- generic
    "error_generic": "❌ Error: <code>{error}</code>",
    "cf_wait": "⏳ Cloudflare rate limit — waiting {secs}s before continuing…",
    "unknown": "🤔 I didn't understand that. Use the menu or /help.",
    "yes": "yes",
    "no": "no",
    "none": "none",
}
