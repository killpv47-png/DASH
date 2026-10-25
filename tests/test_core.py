import pytest

from cfbot.core import crypto
from cfbot.core.redact import redact, register_secret
from cfbot.cloudflare.access import Capabilities, caps_from_policies, classify_access
from cfbot.cloudflare.analyzer import analyze_sources, parse_wrangler
from cfbot.cloudflare.bundle import BundleError, from_code, from_upload, from_zip
from cfbot.cloudflare.deployer import build_plan, resource_name
from cfbot.cloudflare.templates import TEMPLATES
from cfbot.cloudflare.tokens import PRESETS, hint_for
from cfbot.i18n import LANGS, missing_keys, t


# ------------------------------------------------------------------ crypto
def test_crypto_roundtrip_and_salt():
    a = crypto.encrypt(b"hello", "k" * 16)
    b = crypto.encrypt(b"hello", "k" * 16)
    assert a != b  # random salt+nonce
    assert crypto.decrypt(a, "k" * 16) == b"hello"
    with pytest.raises(crypto.DecryptError):
        crypto.decrypt(a, "wrong-key-wrong-key")
    with pytest.raises(crypto.DecryptError):
        crypto.decrypt(b"garbage", "k" * 16)


# ------------------------------------------------------------------ redact
def test_redact_patterns_and_known():
    s = ("cf token cfut_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcd and sk-abcdefghijklmnopqrstuvwxyz and "
         "123456:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA and X-Auth-Key: 0123456789abcdef0123456789abcdef01234")
    out = redact(s)
    assert "cfut_ABC" not in out and "sk-abc" not in out and "AAAAAAAA" not in out
    assert "0123456789abcdef0123456789abcdef01234" not in out
    register_secret("my-very-secret-value")
    assert "my-very-secret-value" not in redact("x my-very-secret-value y")
    assert redact("api_key=abcdefghijklmnop123") == "api_key=[REDACTED]"


# ------------------------------------------------------------------ access levels
def _pol(*names):
    return [{"effect": "allow", "permission_groups": [{"id": n, "name": n} for n in names], "resources": {}}]


@pytest.mark.parametrize("names,level", [
    (("Workers Scripts Write", "Workers KV Storage Write", "D1 Write", "Workers R2 Storage Write",
      "Workers Routes Write", "DNS Write", "Zone Read"), "GOD"),
    (("Workers Scripts Write", "Workers KV Storage Write"), "ARCHITECT"),
    (("Workers Scripts Write",), "ENGINEER"),
    (("Workers Scripts Read", "Zone Read"), "OBSERVER"),
    (("Account Settings Read",), "GHOST"),
])
def test_access_levels_from_exact_policies(names, level):
    caps = caps_from_policies(_pol(*names))
    assert caps.exact and classify_access(caps).name == level


def test_access_global_key_and_deny():
    assert classify_access(None, global_key=True).name == "GOD"
    assert classify_access(None).name == "GHOST"
    pol = _pol("Workers Scripts Write") + [{"effect": "deny", "permission_groups": [{"name": "D1 Write"}]}]
    caps = caps_from_policies(pol)
    assert caps.workers_write and not caps.d1
    assert classify_access(Capabilities(workers_read=True)).name == "OBSERVER"


# ------------------------------------------------------------------ tokens (official template links)
def test_token_presets_urls():
    import json
    from urllib.parse import parse_qs, urlparse
    for key, p in PRESETS.items():
        u = urlparse(p.user_url())
        assert u.scheme == "https" and u.netloc == "dash.cloudflare.com" and u.path == "/profile/api-tokens"
        q = parse_qs(u.query)
        perms = json.loads(q["permissionGroupKeys"][0])
        assert perms and all(set(x) == {"key", "type"} and x["type"] in ("read", "edit") for x in perms)
        assert q["name"][0].startswith("Cloudflare Control Bot")
        assert "accountId" in q and "zoneId" in q
        a = urlparse(p.account_url())
        assert "to=/:account/api-tokens" in p.account_url() and "permissionGroupKeys" in a.query
        assert p.human_perms()
    full = {x["key"] for x in json.loads(parse_qs(urlparse(PRESETS["full"].user_url()).query)["permissionGroupKeys"][0])}
    assert {"workers_scripts", "workers_kv_storage", "workers_r2", "d1", "queues", "workers_routes", "dns"} <= full
    ro = json.loads(parse_qs(urlparse(PRESETS["readonly"].user_url()).query)["permissionGroupKeys"][0])
    assert all(x["type"] == "read" for x in ro)
    assert PRESETS["full"].risk == "high" and PRESETS["readonly"].risk == "low"
    assert "permission" in hint_for({10000}).lower() and hint_for({1}) == ""


# ------------------------------------------------------------------ analyzer
def test_analyzer_detects_bindings_kinds_and_handlers():
    src = """
import { DurableObject } from "cloudflare:workers";
import { Buffer } from "node:buffer";
import lodash from "lodash";
export class Counter extends DurableObject {}
export default {
  async fetch(req, env, ctx) {
    const v = await env.CACHE.get("k", { type: "json" });
    await env.DB.prepare("select 1").bind(1).all();
    await env.FILES.put("a", "b", { httpMetadata: {} });
    await env.JOBS.send({ x: 1 });
    const out = await env.AI.run("@cf/meta/llama", {});
    const stub = env.COUNTER.get(env.COUNTER.idFromName("a"));
    const r = await env.AUTH_SVC.fetch(req);
    return new Response(env.API_SECRET + env.SITE_NAME + env.MAX_ITEMS);
  },
  async scheduled(ev, env) {},
  async queue(batch, env) {},
}
"""
    a = analyze_sources({"index.js": src}, "index.js")
    k = {b.name: b.kind for b in a.bindings}
    assert k["CACHE"] == "kv" and k["DB"] == "d1" and k["FILES"] == "r2" and k["JOBS"] == "queue"
    assert k["AI"] == "ai" and k["COUNTER"] == "durable_object" and k["AUTH_SVC"] == "service"
    assert k["API_SECRET"] == "secret" and k["SITE_NAME"] == "var"
    assert set(a.handlers) >= {"fetch", "scheduled", "queue"}
    assert a.format == "module" and a.durable_object_classes == ["Counter"]
    assert "lodash" in a.npm_imports and "node:buffer" in a.node_imports
    assert "nodejs_compat" in a.compatibility_flags or any("nodejs_compat" in w for w in a.warnings)
    assert a.blockers  # bare npm import cannot be uploaded unbundled


def test_analyzer_service_worker_and_templates():
    a = analyze_sources({"w.js": "addEventListener('fetch', e => e.respondWith(new Response(MY_VAR)))"}, "w.js")
    assert a.format == "service_worker"
    expected = {"hello": {"GREETING": "var"}, "kv": {"CACHE": "kv"}, "d1": {"DB": "d1"}, "r2": {"BUCKET": "r2"},
                "proxy": {"UPSTREAM_URL": "var", "API_TOKEN": "secret"}}
    for key, want in expected.items():
        an = from_code(TEMPLATES[key]["code"], "worker.js").analysis
        got = {b.name: b.kind for b in an.bindings}
        assert got == want, (key, got)
        assert not an.blockers
    assert "scheduled" in from_code(TEMPLATES["cron"]["code"], "worker.js").analysis.handlers


def test_wrangler_toml_and_jsonc():
    toml = """name = "svc"
main = "src/index.ts"
compatibility_date = "2025-02-02"
[vars]
A = "1"
[[kv_namespaces]]
binding = "KV"
id = "abc"
[[d1_databases]]
binding = "DB"
database_name = "x"
database_id = "uuid-1"
[triggers]
crons = ["0 0 * * *"]
"""
    cfg = parse_wrangler("wrangler.toml", toml)
    assert cfg["name"] == "svc" and cfg["vars"]["A"] == "1" and cfg["kv_namespaces"][0]["id"] == "abc"
    jsonc = '{\n // comment\n "name": "j", "compatibility_date": "2025-01-01", "vars": {"B": "2"},}'
    assert parse_wrangler("wrangler.jsonc", jsonc)["vars"]["B"] == "2"
    a = analyze_sources({"index.js": "export default { fetch(r, env) { return env.KV.get(env.A) && env.DB.prepare('') } }"},
                        "index.js", config=cfg)
    plan = build_plan("svc", a)
    acts = {i.name: (i.action, i.target, i.value) for i in plan.items}
    assert acts["KV"] == ("link", "abc", None) and acts["DB"] == ("link", "uuid-1", None) and acts["A"][0] == "value"
    assert plan.crons == ["0 0 * * *"] and plan.compatibility_date == "2025-02-02"
    assert resource_name("svc", "MY_CACHE") == "svc-my-cache"


# --------------------------------------------------------------------- bundle
def _zip(files: dict[str, bytes]) -> bytes:
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for k, v in files.items():
            z.writestr(k, v)
    return buf.getvalue()


def test_bundle_zip_root_strip_ignores_and_safety():
    b = from_zip(_zip({
        "proj/src/index.js": b"import x from './lib.js'; export default { fetch() { return new Response(x) } }",
        "proj/src/lib.js": b"export default 'x'",
        "proj/node_modules/a/index.js": b"junk",
        "proj/.git/config": b"junk",
        "__MACOSX/._x": b"junk",
        "proj/../evil.js": b"x",
        "proj/README.md": b"docs",
    }))
    assert b.main.endswith("index.js")
    assert all("node_modules" not in m and ".git" not in m and "evil" not in m for m in b.modules)
    assert any("lib.js" in m for m in b.modules)
    assert b.analysis.format == "module"
    with pytest.raises(BundleError):
        from_zip(b"not a zip")
    with pytest.raises(BundleError):
        from_zip(_zip({"README.md": b"no code here"}))


def test_bundle_typescript_rejected_with_explanation():
    with pytest.raises(BundleError) as e:
        from_upload("index.ts", b"export default { fetch(): Response { return new Response('') } }")
    assert "TypeScript" in str(e.value) or ".ts" in str(e.value)


def test_bundle_from_upload_kinds():
    assert from_upload("w.mjs", b"export default { fetch() { return new Response('') } }").main == "w.mjs"
    assert from_upload("w.py", b"from workers import WorkerEntrypoint\nclass Default(WorkerEntrypoint):\n  async def fetch(self, r): pass").analysis.format == "python"


# -------------------------------------------------------------------- i18n
def test_i18n_complete_and_fallback():
    assert len(LANGS) == 10
    assert missing_keys("fa") == []
    assert t("ru", "btn_workers") != t("en", "btn_workers") or t("ru", "btn_ai") == t("en", "btn_ai")
    assert t("ru", "plan_title", name="n", mode="m", items="i", crons="c", wdev="w", state="s").startswith("📋")  # EN fallback
    assert t("xx", "btn_workers") == t("en", "btn_workers")
    from cfbot.i18n import en
    import re
    # only hosting messages may mention GitHub (the bot runs on a GitHub Actions runner)
    flat = " ".join(v for k, v in en.STRINGS.items() if k not in ("restart_not_actions", "lifecycle_no_pat"))
    assert not re.search(r"\b(repo|repositor|GitHub token|pull request)", flat, re.I), "GitHub remnants in UI text"
    assert t("en", "does_not_exist") == "does_not_exist"


def test_i18n_placeholders_match_english():
    import re
    ph = lambda s: set(re.findall(r"{(\w+)}", s))  # noqa: E731
    from cfbot.i18n import en
    for lang, table in LANGS.items():
        for k, v in table.items():
            if k in en.STRINGS:
                assert ph(v) <= ph(en.STRINGS[k]), f"{lang}:{k} has unknown placeholders"
