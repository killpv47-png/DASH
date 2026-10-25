"""End-to-end Telegram flows through the real aiogram Dispatcher (fake Telegram + fake Cloudflare API)."""

from __future__ import annotations

import asyncio
import json
from urllib.parse import parse_qs, unquote, urlparse

import httpx
import pytest
from aiogram.methods import DeleteMessage

from cfbot.ai import llm as llm_mod
from tests.fake_llm import FakeLLM, text_resp, tool_resp
from tests.tg_harness import GLOBAL_KEY, TOKEN_CF, USER_ID, FakeCloudflare, Harness, make_zip

TOKEN = TOKEN_CF


async def onboard(h: Harness, lang="en"):
    await h.cmd("/start")
    assert "Choose your language" in h.session.last_text()
    await h.tap(f"lang:set:{lang}")
    await h.text(TOKEN)
    txt = h.session.all_text()
    assert "Cloudflare account scan" in txt or "اسکن" in txt, txt[-800:]
    h.session.clear()


@pytest.fixture
def cf():
    return FakeCloudflare()


@pytest.fixture
async def h(tmp_path, cf):
    async with Harness(tmp_path, cf) as harness:
        yield harness


def plain(s: str) -> str:
    return s.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "")


# ------------------------------------------------------------------ onboarding & tokens
async def test_onboarding_scan_and_menu(h, cf):
    await h.cmd("/start")
    assert "Choose your language" in h.session.last_text()
    await h.tap("lang:set:en")
    assert "Welcome" in h.session.all_text()
    await h.text("not-a-token")
    assert "doesn't look like" in h.session.last_text()
    await h.text(TOKEN)
    txt = h.session.all_text()
    assert "Credential saved" in txt
    assert "Cloudflare account scan" in txt and "My Account" in txt
    assert "Workers: 1" in plain(txt) and "hello-api" in txt
    assert "myacct.workers.dev" in txt
    assert "Main Menu" in txt
    u = await h.db.get_user(USER_ID)
    assert u["cf_account_id"] == "acc123" and u["cf_email"] == "me@example.com"
    assert u["access_level"] in ("GOD", "ARCHITECT", "ENGINEER")
    assert u["cf_token_enc"] and TOKEN.encode() not in u["cf_token_enc"]
    # token message was deleted from chat, never echoed
    assert any(isinstance(c, DeleteMessage) for c in h.session.calls)
    assert TOKEN not in h.session.all_text()
    assert await h.db.kv_get("owners") == [USER_ID]


async def test_exact_policies_give_exact_level(tmp_path):
    pol = [{"effect": "allow", "permission_groups": [{"id": "x", "name": "Workers Scripts Write"},
                                                    {"id": "y", "name": "Workers KV Storage Write"}],
            "resources": {"com.cloudflare.api.account.acc123": "*"}}]
    fake = FakeCloudflare(token_policies=pol)
    async with Harness(tmp_path, fake) as h:
        await onboard(h)
        u = await h.db.get_user(USER_ID)
        caps = json.loads(u["cf_caps"])
        assert caps["workers_write"] and caps["kv"] and not caps["d1"] and caps["exact"]


async def test_persian_onboarding_and_reply_keyboard(h, cf):
    await onboard(h, "fa")
    await h.cmd("/menu")
    assert "منوی اصلی" in h.session.all_text()
    await h.text("⚡ ورکرها")  # reply-keyboard button in Persian
    assert "ورکرهای شما" in h.session.last_text()
    assert "hello-api" in str(h.session.buttons())


async def test_token_guide_official_links(h, cf):
    await h.cmd("/start")
    await h.tap("lang:set:en")
    assert h.session.find_button("tok:p:full")
    await h.tap("tok:p:full")
    txt = h.session.last_text()
    assert "Permissions" in txt and "Workers Scripts" in txt and "Risk" in txt
    urls = [b.url for row in h.session.last_markup().inline_keyboard for b in row if b.url]
    assert len(urls) == 2
    user_url = next(u for u in urls if "/profile/api-tokens" in u)
    acct_url = next(u for u in urls if "to=/:account/api-tokens" in u)
    q = parse_qs(urlparse(user_url).query)
    keys = json.loads(q["permissionGroupKeys"][0])
    assert {"key": "workers_scripts", "type": "edit"} in keys
    assert user_url.startswith("https://dash.cloudflare.com/")
    assert "permissionGroupKeys" in unquote(acct_url)
    # limited presets carry fewer permissions
    await h.tap("tok:p:readonly")
    ro = [b.url for row in h.session.last_markup().inline_keyboard for b in row if b.url][0]
    ro_keys = json.loads(parse_qs(urlparse(ro).query)["permissionGroupKeys"][0])
    assert all(k["type"] == "read" for k in ro_keys)
    # permission matrix + global key explanation (no such thing as "GID")
    await h.tap("tok:matrix")
    assert "developers.cloudflare.com" in h.session.last_text()
    await h.tap("tok:gk")
    assert "Global API Key" in h.session.last_text()


async def test_global_api_key_flow(h, cf):
    await h.cmd("/start")
    await h.tap("lang:set:en")
    await h.text(GLOBAL_KEY)   # pasted directly → detected, asks e-mail
    assert "Global API Key" in h.session.last_text()
    await h.text("not-an-email")
    assert "mail" in h.session.last_text().lower()
    await h.text("me@example.com")
    txt = h.session.all_text()
    assert "Credential saved" in txt and "Cloudflare account scan" in txt
    assert GLOBAL_KEY not in txt
    cred = await h.app.credential_for(USER_ID)
    assert cred["mode"] == "global_key" and cred["email"] == "me@example.com"
    u = await h.db.get_user(USER_ID)
    assert GLOBAL_KEY.encode() not in u["cf_token_enc"]


async def test_bad_token_rejected(h, cf):
    await h.cmd("/start")
    await h.tap("lang:set:en")
    await h.text("cfut_" + "b" * 40)  # well-formed but not valid at Cloudflare
    assert "rejected" in h.session.last_text()
    u = await h.db.get_user(USER_ID)
    assert not u["cf_token_enc"]


# ------------------------------------------------------------------ workers
async def test_worker_list_card_code_bindings_settings_delete(h, cf):
    await onboard(h)
    await h.cmd("/workers")
    assert "Your Workers" in h.session.last_text()
    data = await h.tap_button("hello-api")
    assert data.startswith("wk:card:")
    txt = h.session.last_text()
    assert "hello-api" in txt and "https://hello-api.myacct.workers.dev" in txt and "GREETING" in txt
    # code view + zip download
    await h.tap_button("wk:code:")
    assert "env.GREETING" in h.session.all_text()
    from aiogram.methods import SendDocument
    assert any(isinstance(c, SendDocument) for c in h.session.calls)
    # bindings → remove var
    await h.tap(data)
    await h.tap_button("wk:bind:")
    assert "GREETING" in h.session.last_text()
    await h.tap_button("wk:unbind:")
    assert not cf.workers["hello-api"]["bindings"]
    # settings: workers.dev off, nodejs_compat, compatibility date, observability
    await h.tap(data)
    await h.tap_button("wk:edit:")
    await h.tap_button("wk:wdev:0:")
    assert cf.subdomain_enabled["hello-api"] is False
    await h.tap_button("wk:node:")
    assert "nodejs_compat" in cf.workers["hello-api"]["compatibility_flags"]
    await h.tap_button("wk:obs:")
    assert cf.workers["hello-api"]["observability"]["enabled"] is True
    await h.tap_button("wk:compat:")
    await h.text("2025-13")
    assert "YYYY-MM-DD" in h.session.last_text() or "date" in h.session.last_text().lower()
    await h.text("2025-06-01")
    assert cf.workers["hello-api"]["compatibility_date"] == "2025-06-01"
    # watch
    await h.tap(data)
    await h.tap_button("wk:watch:")
    assert any(w["worker"] == "hello-api" for w in await h.db.list_watches(USER_ID))
    # delete with typed confirmation
    await h.tap_button("wk:del:")
    await h.text("wrong")
    assert "hello-api" in cf.workers
    await h.tap(data)
    await h.tap_button("wk:del:")
    await h.text("hello-api")
    assert "hello-api" not in cf.workers
    assert "deleted" in h.session.all_text().lower()
    assert not await h.db.list_watches(USER_ID)


async def test_unknown_worker_error_hint(h, cf):
    await onboard(h)
    await h.cmd("/worker nope")
    assert "script_not_found" in h.session.last_text() or "not found" in h.session.last_text().lower()


# ------------------------------------------------------------------ new worker from template
async def test_new_worker_template_kv_auto_creates_namespace(h, cf):
    await onboard(h)
    await h.cmd("/newworker")
    await h.text("Bad Name!")
    assert "name" in h.session.last_text().lower()
    await h.text("hello-api")
    assert "exists" in h.session.last_text().lower()
    await h.text("cache-svc")
    await h.tap_button("nw:tpl:kv")
    txt = h.session.all_text()
    assert "Code analysis" in txt and "CACHE" in txt
    assert "Deploy plan" in h.session.last_text()
    # KV is auto-planned as "create" → deploy is available
    await h.tap_button("dp:go")
    txt = h.session.all_text()
    assert "deployed" in txt and "https://cache-svc.myacct.workers.dev" in txt
    assert len(cf.kv) == 1
    ns = next(iter(cf.kv.values()))
    assert "cache-svc" in ns["title"].lower()
    up = cf.uploads[-1]
    assert up["name"] == "cache-svc"
    kvb = [b for b in up["metadata"]["bindings"] if b["type"] == "kv_namespace"]
    assert kvb and kvb[0]["name"] == "CACHE" and kvb[0]["namespace_id"] == ns["id"]
    assert up["metadata"]["main_module"] == "worker.js"
    assert cf.subdomain_enabled["cache-svc"] is True


async def test_new_worker_cron_template_sets_schedule(h, cf):
    await onboard(h)
    await h.cmd("/newworker")
    await h.text("ticker")
    await h.tap_button("nw:tpl:cron")
    # template reads env.PING_URL → bot asks instead of guessing; user skips it
    assert not h.session.find_button("dp:go")
    await h.tap_button("PING_URL")
    await h.tap_button(":skip")
    await h.tap_button("dp:go")
    assert cf.crons["ticker"] == ["*/30 * * * *"]
    assert not any(b["name"] == "PING_URL" for b in cf.workers["ticker"]["bindings"])


# ------------------------------------------------------------------ deploy uploaded code
PROXY_JS = b"""
export default {
  async fetch(request, env, ctx) {
    const r = await fetch(env.UPSTREAM_URL, { headers: { Authorization: `Bearer ${env.API_TOKEN}` } });
    await env.DB.prepare("SELECT 1").all();
    return r;
  }
}
"""


async def test_deploy_js_file_asks_missing_values_and_secret_never_echoed(h, cf):
    await onboard(h)
    await h.cmd("/deploy")
    await h.tap_button("dp:new")
    await h.text("proxy-svc")
    assert "send" in h.session.last_text().lower()
    await h.doc("worker.js", PROXY_JS)
    txt = h.session.all_text()
    assert "Code analysis" in txt
    for n in ("UPSTREAM_URL", "API_TOKEN", "DB"):
        assert n in txt
    # values are pending → no Deploy button yet (never guesses)
    assert not h.session.find_button("dp:go")
    plan = __import__("cfbot.telegram.handlers.deploy", fromlist=["x"]).plan_for_tests(USER_ID)
    idx = {it.name: i for i, it in enumerate(plan.items)}
    assert plan.items[idx["API_TOKEN"]].kind == "secret"
    assert plan.items[idx["UPSTREAM_URL"]].kind == "var"
    # var value
    await h.tap(f"dp:it:{idx['UPSTREAM_URL']}")
    await h.tap(f"dp:act:{idx['UPSTREAM_URL']}:value")
    await h.text("https://api.example.com")
    # secret value — message deleted
    n_del = sum(isinstance(c, DeleteMessage) for c in h.session.calls)
    await h.tap(f"dp:it:{idx['API_TOKEN']}")
    await h.tap(f"dp:act:{idx['API_TOKEN']}:value")
    await h.text("s3cr3t-value-xyz")
    assert sum(isinstance(c, DeleteMessage) for c in h.session.calls) == n_del + 1
    # D1 defaults to create
    assert plan.items[idx["DB"]].action == "create"
    await h.tap_button("dp:go")
    txt = h.session.all_text()
    assert "deployed" in txt
    assert "s3cr3t-value-xyz" not in txt
    assert cf.secrets["proxy-svc"]["API_TOKEN"] == "s3cr3t-value-xyz"
    assert len(cf.d1) == 1
    b = {x["name"]: x for x in cf.workers["proxy-svc"]["bindings"]}
    assert b["UPSTREAM_URL"]["text"] == "https://api.example.com"
    assert b["DB"]["type"] == "d1" and b["DB"]["id"] in cf.d1
    # secret value never persisted to DB/kv
    dump = json.dumps([dict(r) for r in await (await h.db._conn.execute("SELECT * FROM kv")).fetchall()], default=str) \
        if hasattr(h.db, "_conn") else ""
    assert "s3cr3t-value-xyz" not in dump
    jobs = await h.db.recent_jobs(USER_ID)
    assert jobs and jobs[0]["status"] == "done"


async def test_deploy_link_existing_kv_and_update_keeps_secrets(h, cf):
    await onboard(h)
    cf.kv["kvexist"] = {"id": "kvexist", "title": "shared-cache"}
    cf.kv_data["kvexist"] = {}
    cf.secrets["hello-api"]["OLD_SECRET"] = "keepme"
    code = b"export default { async fetch(r, env) { await env.CACHE.get('a'); return new Response(env.OLD_SECRET + env.GREETING) } }"
    await h.cmd("/deploy hello-api")
    await h.doc("index.mjs", code)
    plan = __import__("cfbot.telegram.handlers.deploy", fromlist=["x"]).plan_for_tests(USER_ID)
    idx = {it.name: i for i, it in enumerate(plan.items)}
    # existing secret + existing var are kept
    assert plan.items[idx["OLD_SECRET"]].action == "keep"
    assert plan.items[idx["GREETING"]].action == "keep"
    await h.tap(f"dp:it:{idx['CACHE']}")
    await h.tap(f"dp:act:{idx['CACHE']}:pick")
    assert "shared-cache" in str(h.session.buttons())
    await h.tap_button("shared-cache")
    await h.tap_button("dp:go")
    assert "deployed" in h.session.all_text()
    assert cf.secrets["hello-api"]["OLD_SECRET"] == "keepme"
    b = {x["name"]: x for x in cf.workers["hello-api"]["bindings"]}
    assert b["CACHE"]["namespace_id"] == "kvexist"
    assert b["GREETING"]["text"] == "hi"
    assert len(cf.kv) == 1  # nothing new created


async def test_deploy_zip_with_wrangler_toml(h, cf):
    await onboard(h)
    toml = b'''name = "from-toml"
main = "src/index.js"
compatibility_date = "2025-03-01"
compatibility_flags = ["nodejs_compat"]

[vars]
MODE = "prod"

[[r2_buckets]]
binding = "FILES"
bucket_name = "my-files"

[triggers]
crons = ["0 * * * *"]
'''
    z = make_zip({"proj/wrangler.toml": toml,
                  "proj/src/index.js": b"import {h} from './util.js'; export default { fetch(r, env) { return h(env.MODE, env.FILES) }, scheduled() {} }",
                  "proj/src/util.js": b"export function h(a){ return new Response(a) }",
                  "proj/README.md": b"docs"})
    await h.cmd("/deploy")
    await h.tap_button("dp:new")
    await h.text("from-toml")
    await h.doc("proj.zip", z)
    txt = h.session.all_text()
    assert "wrangler.toml" in txt and "nodejs_compat" in txt and "FILES" in txt
    await h.tap_button("dp:go")
    assert "deployed" in h.session.all_text()
    up = cf.uploads[-1]
    md = up["metadata"]
    assert md["compatibility_date"] == "2025-03-01" and "nodejs_compat" in md["compatibility_flags"]
    assert set(up["modules"]) >= {"index.js", "util.js"} or set(up["modules"]) >= {"src/index.js", "src/util.js"}
    b = {x["name"]: x for x in md["bindings"]}
    assert b["MODE"]["text"] == "prod" and b["FILES"]["bucket_name"] == "my-files"
    assert "my-files" in cf.r2   # created because it did not exist
    assert cf.crons["from-toml"] == ["0 * * * *"]


async def test_deploy_paste_code_and_bad_upload(h, cf):
    await onboard(h)
    await h.cmd("/deploy hello-api")
    await h.text("just some words")
    assert "code" in h.session.last_text().lower()
    await h.doc("bad.zip", b"this is not a zip")
    assert "❌" in h.session.last_text() or "zip" in h.session.last_text().lower()
    await h.text("export default { fetch() { return new Response('pasted') } }")
    await h.tap_button("dp:go")
    assert b"pasted" in cf.workers["hello-api"]["code"]["worker.js"]


async def test_deploy_failure_is_reported(h, cf):
    await onboard(h)
    await h.cmd("/deploy hello-api")
    await h.text("export default { fetch() { return new Response('x') } }")
    cf.fail_next = (400, 10021, "Uncaught SyntaxError: Unexpected token")
    await h.tap_button("dp:go")
    assert "Unexpected token" in h.session.all_text()
    jobs = await h.db.recent_jobs(USER_ID)
    assert jobs[0]["status"] == "failed"


# ------------------------------------------------------------------ secrets & vars
async def test_secrets_crud_scan_variables(h, cf):
    await onboard(h)
    cf.secrets["hello-api"]["MY_SECRET"] = "x"
    await h.cmd("/secrets hello-api")
    assert "MY_SECRET" in h.session.last_text()
    await h.tap_button("sec:add:")
    await h.text("bad-name")
    assert "name" in h.session.last_text().lower()
    await h.text("NEW_SECRET")
    await h.text("value123456")
    assert cf.secrets["hello-api"]["NEW_SECRET"] == "value123456"
    assert "value123456" not in h.session.all_text()
    # scan the deployed code for used-but-unbound names
    cf.workers["hello-api"]["code"]["worker.js"] = b"export default { fetch(r, env) { return new Response(env.GREETING + env.OTHER_KEY) } }"
    await h.cmd("/secrets hello-api")
    await h.tap_button("sec:scan:")
    assert "OTHER_KEY" in h.session.last_text()
    assert h.session.find_button("OTHER_KEY")
    # delete
    await h.cmd("/secrets hello-api")
    await h.tap_button("sec:one:")
    await h.tap_button("sec:del:")
    assert len(cf.secrets["hello-api"]) == 1
    # variables
    await h.cmd("/secrets hello-api")
    await h.tap_button("sec:vars:")
    assert "GREETING" in h.session.last_text()
    await h.tap_button("sec:varadd:")
    await h.text("MY_VAR")
    await h.text("v1")
    b = {x["name"]: x for x in cf.workers["hello-api"]["bindings"]}
    assert b["MY_VAR"]["text"] == "v1" and b["GREETING"]["text"] == "hi"
    assert cf.secrets["hello-api"]  # secrets survive var edits (inherit)


# ------------------------------------------------------------------ ops
async def test_ops_deployments_rollback_cron_routes_domains_metrics(h, cf):
    await onboard(h)
    # create a second version so rollback has a target
    cf.add_worker("hello-api", "export default { fetch() { return new Response('v2') } }",
                  cf.workers["hello-api"]["bindings"])
    old_vid = cf.versions["hello-api"][1]["id"]
    await h.cmd("/worker hello-api")
    await h.tap_button("ops:deps:")
    assert "100%" in h.session.last_text()
    await h.tap_button("ops:rb:")
    await h.tap_button("ops:rbgo:")
    assert cf.deployments["hello-api"][0]["versions"][0]["version_id"] == old_vid
    assert "now serves" in h.session.all_text()
    # cron
    await h.cmd("/worker hello-api")
    await h.tap_button("ops:cron:")
    await h.text("not a cron")
    assert "cron" in h.session.last_text().lower()
    await h.text("*/5 * * * *\n0 3 * * MON")
    assert cf.crons["hello-api"] == ["*/5 * * * *", "0 3 * * MON"]
    await h.cmd("/worker hello-api")
    await h.tap_button("ops:cron:")
    await h.tap_button("ops:cronclr:")
    assert cf.crons["hello-api"] == []
    # routes + custom domain
    await h.cmd("/worker hello-api")
    await h.tap_button("ops:routes:")
    assert "hello-api.myacct.workers.dev" in h.session.last_text()
    await h.tap_button("ops:radd:")
    await h.text("nozone.org/*")
    assert "zone" in h.session.last_text().lower()
    await h.cmd("/worker hello-api")
    await h.tap_button("ops:routes:")
    await h.tap_button("ops:radd:")
    await h.text("api.example.com/*")
    assert cf.routes["z1"][0]["pattern"] == "api.example.com/*" and cf.routes["z1"][0]["script"] == "hello-api"
    await h.tap_button("ops:routes:")
    await h.tap_button("ops:dadd:")
    await h.text("app.example.com")
    assert cf.domains and cf.domains[0]["hostname"] == "app.example.com" and cf.domains[0]["service"] == "hello-api"
    await h.tap_button("ops:routes:")
    assert "app.example.com" in h.session.last_text() and "api.example.com/*" in h.session.last_text()
    await h.tap_button("ops:rdel:")
    assert not cf.routes["z1"]
    await h.tap_button("ops:ddel:")
    assert not cf.domains
    # metrics
    await h.cmd("/metrics")
    assert "Metrics" in h.session.last_text() and "hello-api" in h.session.last_text() and "120" in h.session.last_text()
    await h.tap_button("ops:metrics:168")
    assert "168h" in h.session.last_text()


async def test_ops_test_request(h, cf, monkeypatch):
    await onboard(h)
    import cfbot.telegram.handlers.ops as ops
    seen = []
    real = httpx.AsyncClient

    class Client(real):
        def __init__(self, *a, **kw):
            kw.setdefault("transport", httpx.MockTransport(lambda r: (seen.append(str(r.url)),
                                                             httpx.Response(200, text="hello!", headers={"cf-ray": "abc"}))[1]))
            super().__init__(*a, **kw)
    monkeypatch.setattr(ops.httpx, "AsyncClient", Client)
    await h.cmd("/worker hello-api")
    await h.tap_button("ops:test:")
    await h.text("/health")
    assert seen == ["https://hello-api.myacct.workers.dev/health"]
    txt = h.session.all_text()
    assert "200" in txt and "hello!" in txt


# ------------------------------------------------------------------ storage
async def test_storage_kv_d1_r2_queues_and_bind(h, cf):
    await onboard(h)
    await h.cmd("/storage")
    await h.tap("st:ls:kv")
    assert "0" in h.session.last_text()
    await h.tap_button("st:new:kv")
    await h.text("SESSIONS")
    assert any(n["title"] == "SESSIONS" for n in cf.kv.values())
    ns_id = next(n["id"] for n in cf.kv.values())
    await h.tap_button("st:o:kv:")
    await h.tap_button("st:kvput:")
    await h.text("user:1")
    await h.text('{"a":1}')
    assert cf.kv_data[ns_id]["user:1"] == '{"a":1}'
    await h.tap_button("st:o:kv:")
    assert "user:1" in h.session.last_text()
    await h.tap_button("st:kvget:")
    await h.text("user:1")
    assert "&quot;a&quot;" in h.session.last_text() or '"a"' in h.session.last_text()
    # bind KV to the worker
    await h.tap_button("st:o:kv:")
    await h.tap_button("st:bind:")
    await h.tap_button("hello-api")
    await h.text("SESS")
    b = {x["name"]: x for x in cf.workers["hello-api"]["bindings"]}
    assert b["SESS"]["namespace_id"] == ns_id and "GREETING" in b
    # D1 + SQL console
    await h.cmd("/storage")
    await h.tap("st:ls:d1")
    await h.tap_button("st:new:d1")
    await h.text("appdb")
    await h.tap_button("st:o:d1:")
    assert "notes" in h.session.last_text()
    await h.tap_button("st:sql:")
    await h.text("SELECT 1 AS x")
    assert "rows_read=1" in h.session.last_text()
    assert cf.d1_queries[-1][1] == "SELECT 1 AS x"
    # R2 + Queue create/delete
    await h.cmd("/storage")
    await h.tap("st:ls:r2")
    await h.tap_button("st:new:r2")
    await h.text("Media-Files")
    assert "media-files" in cf.r2
    await h.tap_button("st:o:r2:")
    await h.tap_button("st:del:")
    await h.text("media-files")
    assert "media-files" not in cf.r2
    await h.cmd("/storage")
    await h.tap("st:ls:q")
    await h.tap_button("st:new:q")
    await h.text("jobs")
    assert any(q["queue_name"] == "jobs" for q in cf.queues.values())
    # zones
    await h.cmd("/storage")
    await h.tap("st:zones")
    assert "example.com" in h.session.last_text()


async def test_bind_from_worker_side(h, cf):
    await onboard(h)
    cf.d1["d1-x"] = {"uuid": "d1-x", "name": "maindb", "num_tables": 1}
    await h.cmd("/worker hello-api")
    await h.tap_button("wk:bind:")
    await h.tap_button("st:bindto:")
    await h.tap("st:bt:" + h.session.find_button("st:bt:").split(":")[2] + ":d1")
    await h.tap_button("maindb")
    await h.text("DB")
    b = {x["name"]: x for x in cf.workers["hello-api"]["bindings"]}
    assert b["DB"] == {"type": "d1", "name": "DB", "id": "d1-x"}


async def test_permission_error_shows_hint(h, cf):
    await onboard(h)
    cf.deny = {"/d1/database"}
    await h.cmd("/storage")
    await h.tap("st:ls:d1")
    txt = h.session.last_text()
    assert "Authentication error" in txt and "💡" in txt


# ------------------------------------------------------------------ settings / help / notifications
async def test_settings_help_notifications_cancel(h, cf):
    await onboard(h)
    await h.cmd("/settings")
    assert "acc123" in h.session.last_text() or "My Account" in h.session.last_text()
    await h.cmd("/help")
    for sec in ("arch", "workers", "tokens", "ai", "cmds", "sec"):
        await h.tap(f"help:{sec}")
        assert len(h.session.last_text()) > 100, sec
    await h.cmd("/notifications")
    assert "scan" in h.session.last_text().lower() or "Notifications" in h.session.last_text()
    await h.cmd("/newworker")
    await h.cmd("/cancel")
    assert "Cancelled" in h.session.last_text()
    assert await h.dp.fsm.get_context(h.bot, USER_ID, USER_ID).get_state() is None
    await h.text("hello there")      # AI not configured → still answers
    assert h.session.last_text()
    await h.cmd("/restart")
    assert "Hand off" in h.session.last_text()
    await h.tap("set:restart:yes")   # no lifecycle attached in tests → must not crash
    # forget credential
    await h.tap("set:forget")
    await h.tap("set:forget:yes")
    u = await h.db.get_user(USER_ID)
    assert not u["cf_token_enc"]


async def test_rate_limit_wait_notification(h, cf):
    await onboard(h)
    cf.rate_limit_once = True
    import cfbot.cloudflare.client as c
    real_sleep = asyncio.sleep

    async def fast_sleep(s):
        await real_sleep(0)
    c.asyncio.sleep = fast_sleep
    try:
        await h.cmd("/workers")
    finally:
        c.asyncio.sleep = real_sleep
    txt = h.session.all_text()
    assert "rate" in txt.lower()
    assert "hello-api" in str(h.session.buttons())


# ------------------------------------------------------------------ AI
def _patch_llm(monkeypatch, fake):
    orig_init = llm_mod.LLMClient.__init__

    def patched(self, base_url, api_key, **kw):
        orig_init(self, base_url, api_key, **kw)
        self._client = httpx.AsyncClient(transport=httpx.MockTransport(fake.handler), headers=self._client.headers)
    monkeypatch.setattr(llm_mod.LLMClient, "__init__", patched)


async def test_ai_setup_and_chat_with_cloudflare_tool(h, cf, monkeypatch):
    await onboard(h)
    fake = FakeLLM([
        tool_resp("cloudflare_api", {"action": "list_workers"}),
        text_resp("You have **1** Worker: `hello-api`."),
    ])
    _patch_llm(monkeypatch, fake)
    await h.text("🤖 CLOUDFLARE_AI")
    assert "not configured" in h.session.last_text().lower() or "Setup" in str(h.session.buttons()) \
        or "ai:setup" in str(h.session.buttons())
    await h.tap("ai:setup")
    assert "BASE_URL" in h.session.last_text() or "base" in h.session.last_text().lower()
    await h.text("api.example.com/v1")
    await h.text("sk-testkey1234567890")
    assert "m1" in str(h.session.buttons()) and "m2" in str(h.session.buttons())
    await h.tap_button("ai:model:1")
    cfg = await h.app.ai_config(USER_ID)
    assert cfg["model"] == "m2" and cfg["api_key"] == "sk-testkey1234567890"
    assert "sk-testkey1234567890" not in json.dumps(await h.db.kv_get(f"ai:{USER_ID}"))

    h.session.clear()
    await h.text("how many workers do I have?")
    await h.wait_ai()
    txt = h.session.all_text()
    assert "cloudflare_api" in txt
    assert "<b>1</b>" in txt and "<code>hello-api</code>" in txt
    sysmsg = fake.requests[0]["messages"][0]
    assert sysmsg["role"] == "system"
    assert "CLOUDFLARE_AI" in sysmsg["content"] and "AGENTS.md" in sysmsg["content"]
    assert "acc123" in sysmsg["content"]
    assert "github_api" not in json.dumps(fake.requests[0].get("tools", []))
    tool_names = {t["function"]["name"] for t in fake.requests[0].get("tools", [])}
    assert {"cloudflare_api", "cloudflare_docs"} <= tool_names
    assert fake.requests[1]["messages"][-1]["role"] == "tool"
    assert "hello-api" in fake.requests[1]["messages"][-1]["content"]
    await h.tap("ai:home")
    assert "m2" in h.session.last_text()
    await h.tap("ai:sessions")
    assert "how many workers" in h.session.last_text()
    await h.tap("ai:memory")
    await h.tap("ai:skills")
    assert "worker" in h.session.last_text().lower()


async def test_ai_review_worker_button(h, cf, monkeypatch):
    await onboard(h)
    fake = FakeLLM([text_resp("Looks fine.")])
    _patch_llm(monkeypatch, fake)
    await h.app.save_ai_config(USER_ID, "https://x/v1", "sk-key-1234567890", "m1")
    await h.cmd("/worker hello-api")
    await h.tap_button("ai:w:")
    await h.wait_ai()
    user_msgs = [m for m in fake.requests[0]["messages"] if m["role"] == "user"]
    assert "hello-api" in user_msgs[-1]["content"]


async def test_ai_stop_and_busy(h, cf, monkeypatch):
    await onboard(h)
    gate = asyncio.Event()

    class SlowTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            if request.url.path.endswith("/models"):
                return httpx.Response(200, json={"data": [{"id": "m1"}]})
            await gate.wait()
            return httpx.Response(200, json=text_resp("done"))

    orig_init = llm_mod.LLMClient.__init__

    def patched(self, base_url, api_key, **kw):
        orig_init(self, base_url, api_key, **kw)
        self._client = httpx.AsyncClient(transport=SlowTransport(), headers=self._client.headers)
    monkeypatch.setattr(llm_mod.LLMClient, "__init__", patched)
    await h.app.save_ai_config(USER_ID, "https://x/v1", "sk-key-1234567890", "m1")
    await h.text("do something long")
    await asyncio.sleep(0.05)
    await h.text("another request")
    assert "still working" in h.session.all_text().lower()
    await h.cmd("/ai_stop")
    await asyncio.sleep(0.05)
    assert "stopped" in h.session.all_text().lower()
    assert await h.db.get_pending(USER_ID) is None
    gate.set()
