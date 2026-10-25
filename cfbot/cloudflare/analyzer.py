"""Static analysis of Worker code → what the project needs before it can run.

Detects (heuristic, regex based — no code is executed):
  * format: ES module (``export default``) vs legacy service-worker (``addEventListener('fetch')``)
    vs Python Worker (``from workers import`` / ``class Default(WorkerEntrypoint)``)
  * handlers: fetch, scheduled (→ needs cron trigger), queue (→ queue consumer), email, tail
  * every ``env.NAME`` usage + how it is used → binding kind:
        env.X.get/put/list/delete/getWithMetadata   → KV namespace
        env.X.prepare/batch/exec/dump               → D1 database
        env.X.put/get/head/list/delete + createMultipartUpload/resumeMultipartUpload → R2 bucket
        env.X.send/sendBatch                        → Queue producer
        env.X.run(...)  (Workers AI)                → AI binding
        env.X.idFromName/idFromString/newUniqueId/get(id) → Durable Object namespace
        env.X.fetch(...) / env.X.connect            → Service binding (other Worker)
        env.X.writeDataPoint                        → Analytics Engine
        env.X.query/upsert/insert (vectors)         → Vectorize
        env.X.connectionString                      → Hyperdrive
        anything else (string use)                  → plain var or secret (name heuristics)
  * Node built-ins (``node:*``, ``require('fs')``…) → needs ``nodejs_compat`` flag
  * bare npm imports → cannot be uploaded raw; must be bundled first (wrangler/esbuild)
  * ``class X extends DurableObject`` → Durable Object classes (need migrations)
  * wrangler.toml / wrangler.json(c) in a ZIP → authoritative config (name, main, compat date,
    vars, kv/d1/r2/queues/services/ai/durable objects, crons, routes)

The result is shown to the user BEFORE deploying (handlers/deploy.py) and used by
``deployer.build_plan``.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore

DEFAULT_COMPAT_DATE = "2025-09-01"

_ENV_NAME = r"[A-Z_a-z][A-Za-z0-9_]*"
# env.X / env["X"] / context.env.X ; also destructuring: const { A, B } = env
_ENV_DOT = re.compile(rf"\benv\s*(?:\?\.|\.)\s*({_ENV_NAME})")
_ENV_IDX = re.compile(rf"\benv\s*\[\s*['\"]({_ENV_NAME})['\"]\s*\]")
_ENV_DESTRUCT = re.compile(r"\{\s*([A-Za-z0-9_,\s:]+?)\s*\}\s*=\s*(?:c\.|ctx\.|context\.)?env\b")
_PY_ENV = re.compile(rf"\b(?:self\.)?env\.({_ENV_NAME})")

KIND_METHODS: list[tuple[str, tuple[str, ...]]] = [
    ("d1", ("prepare", "batch", "exec", "dump", "withSession")),
    ("r2", ("createMultipartUpload", "resumeMultipartUpload", "head")),
    ("queue", ("send", "sendBatch")),
    ("durable_object", ("idFromName", "idFromString", "newUniqueId", "getByName", "jurisdiction")),
    ("analytics_engine", ("writeDataPoint",)),
    ("vectorize", ("upsert", "insert", "getByIds", "deleteByIds", "describe")),
    ("hyperdrive", ("connectionString",)),
    ("kv", ("getWithMetadata",)),
    ("ai", ("run", "autorag", "gateway")),
    ("service", ("fetch", "connect")),
    ("kv_or_r2", ("get", "put", "list", "delete")),
]

SECRET_HINT = re.compile(r"(TOKEN|SECRET|KEY|PASSWORD|PASS|PRIVATE|CREDENTIAL|AUTH|WEBHOOK|DSN|SALT|SIGNING)", re.I)
NODE_BUILTINS = {"fs", "path", "crypto", "buffer", "stream", "util", "events", "url", "os", "http", "https", "net",
                 "zlib", "assert", "querystring", "string_decoder", "async_hooks", "child_process", "tls", "dns", "process"}

_IMPORT_RE = re.compile(r"""(?:^|\n)\s*import\s+(?:[^'";]+?\s+from\s+)?['"]([^'"]+)['"]""")
_REQUIRE_RE = re.compile(r"""\brequire\(\s*['"]([^'"]+)['"]\s*\)""")
_DYN_IMPORT_RE = re.compile(r"""\bimport\(\s*['"]([^'"]+)['"]\s*\)""")
_DO_CLASS_RE = re.compile(r"\bexport\s+class\s+([A-Za-z_][A-Za-z0-9_]*)\s+extends\s+DurableObject\b")
_DO_CLASS_LOOSE = re.compile(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:extends\s+\w+\s*)?\{[^}]*?\bconstructor\s*\(\s*(?:state|ctx)\s*,\s*env\s*\)", re.S)
_WORKFLOW_CLASS_RE = re.compile(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)\s+extends\s+WorkflowEntrypoint\b")


@dataclass
class BindingNeed:
    name: str
    kind: str            # kv | d1 | r2 | queue | ai | durable_object | service | analytics_engine | vectorize | hyperdrive | secret | var | unknown
    reason: str = ""
    source: str = "code"  # code | config
    config: dict = field(default_factory=dict)   # from wrangler config (ids, bucket names, …)


@dataclass
class Analysis:
    main_module: str = "worker.js"
    format: str = "module"           # module | service_worker | python
    handlers: list[str] = field(default_factory=list)
    bindings: list[BindingNeed] = field(default_factory=list)
    compatibility_date: str = DEFAULT_COMPAT_DATE
    compatibility_flags: list[str] = field(default_factory=list)
    crons: list[str] = field(default_factory=list)
    routes: list[str] = field(default_factory=list)
    durable_object_classes: list[str] = field(default_factory=list)
    npm_imports: list[str] = field(default_factory=list)
    node_imports: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    name_hint: str | None = None
    config_file: str | None = None
    size_bytes: int = 0
    modules: list[str] = field(default_factory=list)

    def need(self, name: str) -> BindingNeed | None:
        return next((b for b in self.bindings if b.name == name), None)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def storage_needed(self) -> list[BindingNeed]:
        return [b for b in self.bindings if b.kind in ("kv", "d1", "r2", "queue", "kv_or_r2")]


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"(?m)(^|[^:\\'\"])//.*$", r"\1", src)


def _method_calls(src: str, name: str) -> set[str]:
    pat = re.compile(rf"\benv\s*(?:\?\.|\.)\s*{re.escape(name)}\s*(?:\?\.|\.)\s*([A-Za-z_][A-Za-z0-9_]*)")
    calls = set(pat.findall(src))
    # destructured usage: const { DB } = env; DB.prepare(...)
    pat2 = re.compile(rf"(?<![\w.]){re.escape(name)}\s*(?:\?\.|\.)\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    calls |= set(pat2.findall(src))
    return calls


def _guess_kind(src: str, name: str) -> tuple[str, str]:
    calls = _method_calls(src, name)
    for kind, methods in KIND_METHODS:
        hit = sorted(calls & set(methods))
        if hit:
            if kind == "kv_or_r2":
                # R2 objects are read with .text()/.json()/.arrayBuffer()/.body and put returns metadata;
                # KV get takes a type ("json"/"text") and KV put supports expirationTtl.
                if re.search(rf"{re.escape(name)}\s*\.\s*get\([^)]*['\"](?:json|text|arrayBuffer|stream)['\"]", src) or \
                        re.search(r"expirationTtl|expiration\s*:", src):
                    return "kv", f"uses .{', .'.join(hit)} with KV options"
                if re.search(rf"{re.escape(name)}\s*\.\s*(?:get|head)\([^)]*\)\s*;?[\s\S]{{0,200}}?\.(?:body|httpMetadata|writeHttpMetadata|arrayBuffer)\b", src) or \
                        re.search(r"httpMetadata|customMetadata|R2Object", src):
                    return "r2", f"uses .{', .'.join(hit)} with R2 object API"
                return "kv", f"uses .{', .'.join(hit)} (KV or R2 — defaulting to KV, change if wrong)"
            if kind == "ai" and "run" in hit and not re.search(r"@cf/|@hf/|model", src):
                continue
            if kind == "service" and name.upper() in ("ASSETS",):
                return "assets", "static assets binding"
            return kind, f"uses .{', .'.join(hit)}"
    if SECRET_HINT.search(name):
        return "secret", "name looks sensitive"
    return "var", "used as a value"


def _imports(src: str) -> list[str]:
    return sorted(set(_IMPORT_RE.findall(src)) | set(_REQUIRE_RE.findall(src)) | set(_DYN_IMPORT_RE.findall(src)))


def analyze_sources(modules: dict[str, str], main: str, *, config: dict | None = None) -> Analysis:
    """Analyze one or more module sources. ``config`` = parsed wrangler config (optional)."""
    a = Analysis(main_module=main, modules=sorted(modules))
    a.size_bytes = sum(len(s.encode()) for s in modules.values())
    all_src = "\n".join(_strip_comments(s) for n, s in modules.items() if n.endswith((".js", ".mjs", ".cjs", ".ts", ".py")))
    main_src = modules.get(main, "")

    # -------- format & handlers
    if main.endswith(".py"):
        a.format = "python"
        a.compatibility_flags.append("python_workers")
        for h, pat in (("fetch", r"def\s+fetch\s*\("), ("scheduled", r"def\s+scheduled\s*\("), ("queue", r"def\s+queue\s*\(")):
            if re.search(pat, main_src):
                a.handlers.append(h)
    elif re.search(r"\bexport\s+default\b", all_src) or re.search(r"\bexport\s*\{[^}]*\bas\s+default\b", all_src):
        a.format = "module"
        for h in ("fetch", "scheduled", "queue", "email", "tail", "trace"):
            if re.search(rf"\b(?:async\s+)?{h}\s*\(|\b{h}\s*:\s*(?:async\s*)?(?:function|\()", all_src):
                a.handlers.append(h)
        if re.search(r"\bnew\s+Hono\b|\bapp\.(?:get|post|route)\(", all_src) and "fetch" not in a.handlers:
            a.handlers.append("fetch")  # export default app (Hono / itty)
    elif re.search(r"addEventListener\(\s*['\"](fetch|scheduled)['\"]", all_src):
        a.format = "service_worker"
        a.handlers = sorted(set(re.findall(r"addEventListener\(\s*['\"](fetch|scheduled)['\"]", all_src)))
        a.warnings.append("Service-worker syntax (addEventListener) is legacy — it is uploaded as body_part; "
                          "bindings are globals instead of env.X. Consider migrating to ES modules.")
    else:
        a.blockers.append("No handler found: expected `export default { fetch(...) }` (ES module), "
                          "`addEventListener('fetch', …)` or a Python `on_fetch`/WorkerEntrypoint.")

    # -------- env usage
    names: dict[str, None] = {}
    for rx in (_ENV_DOT, _ENV_IDX):
        for n in rx.findall(all_src):
            names[n] = None
    for grp in _ENV_DESTRUCT.findall(all_src):
        for part in grp.split(","):
            n = part.split(":")[0].strip()
            if re.fullmatch(_ENV_NAME, n):
                names[n] = None
    if a.format == "python":
        for n in _PY_ENV.findall(all_src):
            names[n] = None
    if a.format == "service_worker":  # globals: guess from UPPER_CASE identifiers used with methods
        for n in set(re.findall(r"\b([A-Z][A-Z0-9_]{2,})\s*\.\s*(?:get|put|prepare|send|fetch|list|delete)\s*\(", all_src)):
            names[n] = None
    for skip in ("then", "constructor", "prototype", "toString"):
        names.pop(skip, None)

    for n in names:
        kind, reason = _guess_kind(all_src, n)
        a.bindings.append(BindingNeed(n, kind, reason))

    # -------- imports
    for imp in _imports(all_src):
        if imp.startswith(("./", "../", "/")):
            continue
        if imp.startswith("node:"):
            a.node_imports.append(imp)
        elif imp.split("/")[0] in NODE_BUILTINS:
            a.node_imports.append(imp)
        elif imp.startswith("cloudflare:") or imp in ("workers", "js", "pyodide") or imp.startswith("__STATIC_CONTENT"):
            continue
        elif a.format == "python":
            continue
        else:
            a.npm_imports.append(imp)
    if a.node_imports:
        a.compatibility_flags.append("nodejs_compat")
    rel_missing = [imp for imp in _imports(all_src) if imp.startswith("./") and _resolve(imp, modules) is None]
    if a.npm_imports:
        a.blockers.append(
            "Bare npm imports (" + ", ".join(sorted(set(a.npm_imports))[:8]) + ") cannot be resolved by the upload API. "
            "Bundle the project first (`npx wrangler deploy --dry-run --outdir dist` or esbuild) and upload the bundled .js, "
            "or send a ZIP that already contains the bundled output.")
    if rel_missing:
        a.blockers.append("Missing local modules: " + ", ".join(rel_missing[:8]) + " — upload a ZIP containing them.")

    # -------- Durable Objects / Workflows
    a.durable_object_classes = sorted(set(_DO_CLASS_RE.findall(all_src)))
    if _WORKFLOW_CLASS_RE.search(all_src):
        a.warnings.append("Workflows detected — create the Workflow binding with wrangler; the upload API alone does not register it.")
    for b in a.bindings:
        if b.kind == "durable_object" and not a.durable_object_classes:
            a.warnings.append(f"{b.name} looks like a Durable Object namespace but no `export class … extends DurableObject` was found "
                              "(it may live in another Worker — set script_name).")

    if "scheduled" in a.handlers:
        a.warnings.append("Has a scheduled() handler — add at least one cron trigger or it will never run.")
    if "queue" in a.handlers:
        a.warnings.append("Has a queue() handler — attach this Worker as a consumer of a Queue (Queues → consumers).")
    if a.size_bytes > 60 * 1024 * 1024:
        a.blockers.append("Bundle exceeds the 64 MiB Worker size limit.")

    if config:
        _apply_config(a, config)
    a.compatibility_flags = sorted(set(a.compatibility_flags))
    return a


def _resolve(imp: str, modules: dict[str, str]) -> str | None:
    base = imp[2:]
    for cand in (base, base + ".js", base + ".mjs", base + "/index.js"):
        if cand in modules:
            return cand
    return None


# ----------------------------------------------------------------------- wrangler config
def parse_wrangler(name: str, text: str) -> dict:
    if name.endswith(".toml"):
        if tomllib is None:  # pragma: no cover
            raise ValueError("TOML parser not available")
        return tomllib.loads(text)
    # json / jsonc: strip comments + trailing commas
    t = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    t = re.sub(r'(?m)^(\s*)//.*$', r"\1", t)
    t = re.sub(r'(?<!:)//[^\n"]*$', "", t, flags=re.M)
    t = re.sub(r",(\s*[}\]])", r"\1", t)
    return json.loads(t)


def _apply_config(a: Analysis, cfg: dict) -> None:
    a.name_hint = cfg.get("name") or a.name_hint
    if cfg.get("compatibility_date"):
        a.compatibility_date = str(cfg["compatibility_date"])
    a.compatibility_flags = sorted(set(a.compatibility_flags) | set(cfg.get("compatibility_flags") or []))
    trig = cfg.get("triggers") or {}
    a.crons = list(trig.get("crons") or [])
    routes = cfg.get("routes") or ([cfg["route"]] if cfg.get("route") else [])
    a.routes = [r if isinstance(r, str) else r.get("pattern", "") for r in routes]

    def upsert(name: str, kind: str, conf: dict, reason: str):
        b = a.need(name)
        if b:
            b.kind, b.source, b.config, b.reason = kind, "config", conf, reason
        else:
            a.bindings.append(BindingNeed(name, kind, reason, "config", conf))

    for k, v in (cfg.get("vars") or {}).items():
        upsert(k, "var", {"value": v if isinstance(v, str) else json.dumps(v)}, "wrangler [vars]")
    for kv in cfg.get("kv_namespaces") or []:
        upsert(kv["binding"], "kv", {"id": kv.get("id")}, "wrangler kv_namespaces")
    for d in cfg.get("d1_databases") or []:
        upsert(d["binding"], "d1", {"id": d.get("database_id"), "name": d.get("database_name")}, "wrangler d1_databases")
    for r in cfg.get("r2_buckets") or []:
        upsert(r["binding"], "r2", {"bucket_name": r.get("bucket_name")}, "wrangler r2_buckets")
    for q in (cfg.get("queues") or {}).get("producers") or []:
        upsert(q["binding"], "queue", {"queue_name": q.get("queue")}, "wrangler queues.producers")
    for s in cfg.get("services") or []:
        upsert(s["binding"], "service", {"service": s.get("service")}, "wrangler services")
    if cfg.get("ai"):
        upsert(cfg["ai"].get("binding", "AI"), "ai", {}, "wrangler ai")
    for d in (cfg.get("durable_objects") or {}).get("bindings") or []:
        upsert(d["name"], "durable_object", {"class_name": d.get("class_name"), "script_name": d.get("script_name")},
               "wrangler durable_objects")
    for v in cfg.get("vectorize") or []:
        upsert(v["binding"], "vectorize", {"index_name": v.get("index_name")}, "wrangler vectorize")
    for h in cfg.get("hyperdrive") or []:
        upsert(h["binding"], "hyperdrive", {"id": h.get("id")}, "wrangler hyperdrive")
    for e in cfg.get("analytics_engine_datasets") or []:
        upsert(e["binding"], "analytics_engine", {"dataset": e.get("dataset")}, "wrangler analytics_engine_datasets")
    if (cfg.get("assets") or {}).get("binding"):
        a.warnings.append("Static assets ([assets]) need the assets upload session — deploy those with wrangler; "
                          "the Worker script itself is deployed here.")


# ----------------------------------------------------------------------- summary helpers
KIND_LABEL = {
    "kv": "KV namespace", "d1": "D1 database", "r2": "R2 bucket", "queue": "Queue (producer)", "ai": "Workers AI",
    "durable_object": "Durable Object", "service": "Service binding", "analytics_engine": "Analytics Engine",
    "vectorize": "Vectorize index", "hyperdrive": "Hyperdrive", "secret": "Secret", "var": "Variable",
    "assets": "Static assets", "kv_or_r2": "KV or R2", "unknown": "?",
}
AUTO_CREATABLE = {"kv", "d1", "r2", "queue"}
NO_RESOURCE = {"ai"}


def storage_advice(kind: str) -> str:
    return {
        "kv": "KV — global key-value, eventually consistent (~60s), best for config, cache, sessions, flags.",
        "d1": "D1 — serverless SQLite: relational data, joins, transactions, users/orders/tables.",
        "r2": "R2 — object storage: files, images, uploads, large blobs; zero egress fees.",
        "queue": "Queues — async background jobs and batching between Workers.",
    }.get(kind, "")
