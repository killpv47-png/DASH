"""cloudflare_api — one tool, many actions, authenticated as the Telegram user's Cloudflare credential.

Wraps ``CloudflareClient`` (retry / rate-limit handling built in) so the agent never
touches the raw token.  ``analyze`` and ``deploy`` share the exact same code path as the
Telegram deploy flow (analyzer → plan → deployer.execute).
"""

from __future__ import annotations

import json
from pathlib import Path

from ...cloudflare.analyzer import analyze_sources
from ...cloudflare.bundle import BundleError, from_code, from_zip
from ...cloudflare.client import SCRIPT_NAME_RE, CloudflareError
from ...cloudflare.deployer import Plan, PlanItem, build_plan, execute
from ...cloudflare.tokens import hint_for
from .context import ToolContext

ACTIONS = [
    "whoami", "list_accounts", "list_workers", "get_worker", "get_code", "analyze", "deploy", "delete_worker",
    "list_secrets", "set_secret", "delete_secret", "set_var", "remove_binding", "add_binding",
    "get_crons", "set_crons", "list_deployments", "list_versions", "rollback", "set_workers_dev", "settings_patch",
    "list_routes", "add_route", "delete_route", "list_domains", "attach_domain", "detach_domain", "list_zones",
    "metrics", "list_kv", "create_kv", "kv_keys", "kv_get", "kv_put", "kv_delete", "list_d1", "create_d1", "d1_query",
    "list_r2", "create_r2", "list_queues", "create_queue", "raw",
]
DESTRUCTIVE = {"delete_worker", "delete_secret", "remove_binding", "rollback", "detach_domain", "delete_route", "kv_delete"}

SCHEMA = {
    "name": "cloudflare_api",
    "description": (
        "Call the Cloudflare API as the current user (credential and account id already attached; never ask for the "
        "token). Actions: " + ", ".join(ACTIONS) + ". "
        "`worker` = script name. analyze: static analysis of code (code=… or local_path to a .js/.zip in the workspace, or "
        "worker=… to analyze the deployed code) → handlers, env bindings needed (KV/D1/R2/Queue/AI/DO/service/var/secret), "
        "flags, blockers, and a deploy plan. deploy: upload code (code / local_path) to `worker`; `plan` maps binding name → "
        "{action: create|link|value|keep|ai|skip, target, value}; unspecified storage bindings default to create, and "
        "vars/secrets WITHOUT a value block the deploy (ask the user — never invent values). crons=[...], workers_dev=true. "
        "d1_query runs SQL (sql, params). metrics: requests/errors/CPU over `hours`. raw: method+path(+body) for anything else "
        "(path relative to /client/v4, `{account}` is replaced by the account id). Destructive actions ("
        + ", ".join(sorted(DESTRUCTIVE)) + ", deploy over an existing Worker) need explicit user confirmation earlier in the conversation."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ACTIONS},
            "worker": {"type": "string"},
            "account_id": {"type": "string"},
            "code": {"type": "string", "description": "Worker source (ES module)"},
            "filename": {"type": "string", "description": "file name for code, e.g. worker.js / worker.py"},
            "local_path": {"type": "string", "description": "workspace path to a .js/.mjs/.py file or .zip project"},
            "plan": {"type": "object", "description": "binding name → {action, target, value}"},
            "crons": {"type": "array", "items": {"type": "string"}},
            "workers_dev": {"type": "boolean"},
            "compatibility_date": {"type": "string"},
            "compatibility_flags": {"type": "array", "items": {"type": "string"}},
            "name": {"type": "string"},
            "value": {"type": "string"},
            "binding": {"type": "object", "description": "full binding object for add_binding"},
            "version_id": {"type": "string"},
            "message": {"type": "string"},
            "enabled": {"type": "boolean"},
            "fields": {"type": "object", "description": "settings_patch: script-settings fields (logpush, observability, tags)"},
            "zone_id": {"type": "string"},
            "route_id": {"type": "string"},
            "pattern": {"type": "string"},
            "hostname": {"type": "string"},
            "domain_id": {"type": "string"},
            "namespace_id": {"type": "string"},
            "key": {"type": "string"},
            "prefix": {"type": "string"},
            "database_id": {"type": "string"},
            "sql": {"type": "string"},
            "params": {"type": "array", "items": {}},
            "hours": {"type": "integer"},
            "method": {"type": "string"},
            "path": {"type": "string"},
            "body": {"type": "object"},
            "force": {"type": "boolean"},
        },
        "required": ["action"],
    },
}


def _ok(**kw) -> str:
    return json.dumps({"success": True, **kw}, ensure_ascii=False, default=str)


def _bundle(ctx: ToolContext, args: dict):
    if args.get("local_path"):
        p: Path = ctx.resolve(args["local_path"])
        data = p.read_bytes()
        if p.suffix.lower() == ".zip":
            return from_zip(data, p.name)
        return from_code(data, p.name)
    if args.get("code"):
        return from_code(args["code"], args.get("filename") or "worker.js")
    return None


def _plan_view(p: Plan) -> list[dict]:
    return [{"name": i.name, "kind": i.kind, "action": i.action, "target": i.target,
             "value": ("<set>" if i.value else None) if i.kind == "secret" else i.value, "note": i.note} for i in p.items]


async def _existing(cf, name: str) -> tuple[list[dict], set[str]]:
    try:
        ws = {w["id"] for w in await cf.list_workers()}
    except CloudflareError:
        return [], set()
    if name not in ws:
        return [], set()
    bindings = [b for b in (await cf.get_worker_settings(name)).get("bindings") or [] if b.get("type") != "secret_text"]
    secrets = {s["name"] for s in await cf.list_secrets(name)}
    return bindings, secrets


async def handle(ctx: ToolContext, args: dict) -> str:
    cf = ctx.cf
    if cf is None:
        return json.dumps({"error": "no Cloudflare credential configured for this user — ask them to use /token"})
    a = args.get("action")
    w = args.get("worker", "")
    if args.get("account_id"):
        cf.account_id = args["account_id"]
    try:
        if a == "whoami":
            v = await cf.verify()
            u = await cf.user()
            return _ok(kind=v.get("kind"), status=v.get("status"), expires_on=v.get("expires_on"),
                       email=(u or {}).get("email"), account_id=cf.account_id)
        if a == "list_accounts":
            return _ok(accounts=[{"id": x["id"], "name": x.get("name")} for x in await cf.list_accounts()])
        if a == "list_workers":
            return _ok(workers=[{k: x.get(k) for k in ("id", "handlers", "modified_on", "compatibility_date", "usage_model")}
                                for x in await cf.list_workers()])
        if a == "get_worker":
            s = await cf.get_worker_settings(w)
            return _ok(settings={k: s.get(k) for k in ("bindings", "compatibility_date", "compatibility_flags", "logpush",
                                                         "observability", "placement", "tail_consumers", "usage_model", "limits")},
                       subdomain=await cf.account_subdomain())
        if a == "get_code":
            mods = await cf.get_worker_content(w)
            out = {}
            ws = ctx.workspace / "workers" / w
            ws.mkdir(parents=True, exist_ok=True)
            for k, v in mods.items():
                (ws / k).parent.mkdir(parents=True, exist_ok=True)
                (ws / k).write_bytes(v)
                out[k] = v.decode("utf-8", errors="replace")[:15000]
            return _ok(saved_to=str(ws), modules=out)
        if a == "analyze":
            if not args.get("code") and not args.get("local_path") and w:
                mods = await cf.get_worker_content(w)
                texts = {k: v.decode("utf-8", errors="replace") for k, v in mods.items()}
                an = analyze_sources(texts, next(iter(texts)))
            else:
                b = _bundle(ctx, args)
                if b is None:
                    return json.dumps({"error": "give code, local_path or worker"})
                an = b.analysis
            eb, es = await _existing(cf, w) if w else ([], set())
            plan = build_plan(w or an.name_hint or "worker", an, existing_bindings=eb, existing_secrets=es)
            d = an.to_dict()
            return _ok(analysis={k: d[k] for k in ("main_module", "format", "handlers", "bindings", "compatibility_date",
                                                    "compatibility_flags", "crons", "routes", "durable_object_classes",
                                                    "npm_imports", "node_imports", "warnings", "blockers", "config_file", "modules")},
                       plan=_plan_view(plan), pending=[i.name for i in plan.pending])
        if a == "deploy":
            if not w or not SCRIPT_NAME_RE.match(w):
                return json.dumps({"error": "worker name required: lowercase letters, digits, dashes (max 63)"})
            b = _bundle(ctx, args)
            if b is None:
                return json.dumps({"error": "give code or local_path"})
            if b.analysis.blockers:
                return json.dumps({"error": "blockers", "blockers": b.analysis.blockers})
            eb, es = await _existing(cf, w)
            plan = build_plan(w, b.analysis, existing_bindings=eb, existing_secrets=es)
            for name, spec in (args.get("plan") or {}).items():
                it = plan.item(name)
                if not it:
                    it = PlanItem(name, spec.get("kind", "var"))
                    plan.items.append(it)
                if spec.get("kind"):
                    it.kind = spec["kind"]
                it.action = spec.get("action") or ("value" if "value" in spec else it.action)
                it.target = spec.get("target", it.target)
                if "value" in spec:
                    it.value = str(spec["value"])
            if args.get("crons") is not None:
                plan.crons = list(args["crons"])
            if args.get("workers_dev") is not None:
                plan.enable_workers_dev = bool(args["workers_dev"])
            if args.get("compatibility_date"):
                plan.compatibility_date = args["compatibility_date"]
            if args.get("compatibility_flags") is not None:
                plan.compatibility_flags = list(args["compatibility_flags"])
            if plan.pending:
                return json.dumps({"error": "plan incomplete — ask the user for these values/targets",
                                   "pending": _plan_view(Plan(w, plan.main, "", [], items=plan.pending))})

            async def prog(m):
                if ctx.notify:
                    await ctx.notify(f"🚀 {m}")
            rep = await execute(cf, plan, b.modules, progress=prog, service_worker=b.analysis.format == "service_worker")
            return _ok(report=rep)
        if a == "delete_worker":
            await cf.delete_worker(w, force=bool(args.get("force", True)))
            return _ok(deleted=w)
        if a == "list_secrets":
            return _ok(secrets=[s["name"] for s in await cf.list_secrets(w)])
        if a == "set_secret":
            await cf.put_secret(w, args["name"], args.get("value", ""))
            return _ok(name=args["name"])
        if a == "delete_secret":
            await cf.delete_secret(w, args["name"])
            return _ok()
        if a == "set_var":
            await cf.set_var(w, args["name"], args.get("value", ""))
            return _ok(name=args["name"])
        if a == "remove_binding":
            await cf.delete_binding(w, args["name"])
            return _ok()
        if a == "add_binding":
            await cf.add_binding(w, args["binding"])
            return _ok()
        if a == "get_crons":
            return _ok(crons=[s.get("cron") for s in await cf.get_schedules(w)])
        if a == "set_crons":
            return _ok(crons=[s.get("cron") for s in await cf.set_schedules(w, list(args.get("crons") or []))])
        if a == "list_deployments":
            return _ok(deployments=(await cf.list_deployments(w))[:10])
        if a == "list_versions":
            return _ok(versions=[{"id": v["id"], "number": (v.get("metadata") or {}).get("number"),
                                  "created_on": (v.get("metadata") or {}).get("created_on"),
                                  "source": (v.get("metadata") or {}).get("source"),
                                  "message": (v.get("annotations") or {}).get("workers/message")}
                                 for v in await cf.list_versions(w, per_page=int(args.get("hours") or 10))])
        if a == "rollback":
            return _ok(deployment=await cf.deploy_version(w, args["version_id"], args.get("message") or "rollback via CLOUDFLARE_AI"))
        if a == "set_workers_dev":
            return _ok(result=await cf.set_worker_subdomain(w, bool(args.get("enabled", True))))
        if a == "settings_patch":
            fields = dict(args.get("fields") or {})
            res = {}
            if args.get("compatibility_date") or args.get("compatibility_flags") is not None:
                vs = {}
                if args.get("compatibility_date"):
                    vs["compatibility_date"] = args["compatibility_date"]
                if args.get("compatibility_flags") is not None:
                    vs["compatibility_flags"] = args["compatibility_flags"]
                res["version_settings"] = bool(await cf.patch_worker_settings(w, vs) is not None)
            if fields:
                res["script_settings"] = await cf.patch_script_settings(w, fields)
            return _ok(**res)
        if a == "list_zones":
            return _ok(zones=[{"id": z["id"], "name": z["name"], "status": z.get("status")} for z in await cf.list_zones()])
        if a == "list_routes":
            if args.get("zone_id"):
                return _ok(routes=await cf.list_routes(args["zone_id"]))
            return _ok(routes=await cf.worker_routes(w))
        if a == "add_route":
            return _ok(route=await cf.create_route(args["zone_id"], args["pattern"], w))
        if a == "delete_route":
            await cf.delete_route(args["zone_id"], args["route_id"])
            return _ok()
        if a == "list_domains":
            return _ok(domains=await cf.list_domains(service=w or None))
        if a == "attach_domain":
            return _ok(domain=await cf.attach_domain(args["hostname"], w, args["zone_id"]))
        if a == "detach_domain":
            await cf.detach_domain(args["domain_id"])
            return _ok()
        if a == "metrics":
            return _ok(**await cf.worker_metrics(w or None, hours=int(args.get("hours") or 24)))
        if a == "list_kv":
            return _ok(namespaces=[{"id": n["id"], "title": n["title"]} for n in await cf.list_kv()])
        if a == "create_kv":
            return _ok(namespace=await cf.create_kv(args["name"]))
        if a == "kv_keys":
            return _ok(keys=[k["name"] for k in await cf.kv_keys(args["namespace_id"], args.get("prefix"))])
        if a == "kv_get":
            return _ok(value=await cf.kv_get(args["namespace_id"], args["key"]))
        if a == "kv_put":
            await cf.kv_put(args["namespace_id"], args["key"], args.get("value", ""))
            return _ok()
        if a == "kv_delete":
            await cf.kv_delete(args["namespace_id"], args["key"])
            return _ok()
        if a == "list_d1":
            return _ok(databases=[{"uuid": d["uuid"], "name": d["name"]} for d in await cf.list_d1()])
        if a == "create_d1":
            return _ok(database=await cf.create_d1(args["name"]))
        if a == "d1_query":
            return _ok(result=await cf.d1_query(args["database_id"], args["sql"], args.get("params")))
        if a == "list_r2":
            return _ok(buckets=[b["name"] for b in await cf.list_r2()])
        if a == "create_r2":
            return _ok(bucket=await cf.create_r2(args["name"]))
        if a == "list_queues":
            return _ok(queues=[{"id": q.get("queue_id"), "name": q.get("queue_name")} for q in await cf.list_queues()])
        if a == "create_queue":
            return _ok(queue=await cf.create_queue(args["name"]))
        if a == "raw":
            method = (args.get("method") or "GET").upper()
            path = args.get("path", "")
            if not path.startswith("/"):
                return json.dumps({"error": "path must start with / (relative to https://api.cloudflare.com/client/v4)"})
            path = path.replace("{account}", cf.acct())
            data = await cf.raw(method, path, args.get("body"))
            return json.dumps(data, ensure_ascii=False, default=str)[:20000]
        return json.dumps({"error": f"unknown action {a}", "actions": ACTIONS})
    except CloudflareError as e:
        return json.dumps({"error": e.message, "status": e.status, "codes": sorted(c for c in e.codes if c),
                           "hint": hint_for(e.codes)})
    except BundleError as e:
        return json.dumps({"error": str(e)})
    except KeyError as e:
        return json.dumps({"error": f"missing argument {e}"})
