"""Turn an ``Analysis`` into a deploy plan, then execute it for real against the API.

Plan = one entry per binding with an *action*:
  create   create a new KV / D1 / R2 / Queue named ``<worker>-<binding>`` and bind it
  link     bind an existing resource (id / bucket / queue name / service) chosen by the user or from wrangler config
  value    plain_text var or secret_text value supplied by the user
  keep     keep the binding the Worker already has (update of an existing Worker → ``inherit``)
  ai       Workers AI binding (no resource)
  skip     do not bind (user decision; the Worker may fail at runtime — warned)

Nothing sensitive is guessed: vars/secrets without a value and service/DO bindings
without a target stay ``pending`` and block the deploy until the user provides them
(or explicitly skips).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Awaitable, Callable

from .analyzer import AUTO_CREATABLE, Analysis
from .client import CloudflareClient, CloudflareError

Progress = Callable[[str], Awaitable[None]]


@dataclass
class PlanItem:
    name: str
    kind: str
    action: str = "pending"       # pending | create | link | value | keep | ai | skip
    target: str = ""              # resource id / bucket / queue / service / class name
    value: str | None = None      # var/secret value (secret values are never persisted in the plan store)
    note: str = ""

    @property
    def ready(self) -> bool:
        return self.action != "pending"


@dataclass
class Plan:
    worker: str
    main: str
    compatibility_date: str
    compatibility_flags: list[str]
    items: list[PlanItem] = field(default_factory=list)
    crons: list[str] = field(default_factory=list)
    enable_workers_dev: bool = True
    existing: bool = False
    do_classes: list[str] = field(default_factory=list)

    def item(self, name: str) -> PlanItem | None:
        return next((i for i in self.items if i.name == name), None)

    @property
    def pending(self) -> list[PlanItem]:
        return [i for i in self.items if not i.ready]

    def to_store(self) -> dict:
        """Serializable form WITHOUT secret values (those live only in memory until deploy)."""
        d = asdict(self)
        for it in d["items"]:
            if it["kind"] == "secret":
                it["value"] = None
        return d

    @classmethod
    def from_store(cls, d: dict) -> "Plan":
        items = [PlanItem(**i) for i in d.pop("items", [])]
        p = cls(**d)
        p.items = items
        return p


def resource_name(worker: str, binding: str) -> str:
    n = re.sub(r"[^a-z0-9-]+", "-", f"{worker}-{binding}".lower()).strip("-")
    return n[:63] or "resource"


def build_plan(worker: str, a: Analysis, *, existing_bindings: list[dict] | None = None,
               existing_secrets: set[str] | None = None) -> Plan:
    existing_bindings = existing_bindings or []
    by_name = {b.get("name"): b for b in existing_bindings}
    existing_secrets = existing_secrets or set()
    p = Plan(worker=worker, main=a.main_module, compatibility_date=a.compatibility_date,
             compatibility_flags=list(a.compatibility_flags), crons=list(a.crons),
             existing=bool(existing_bindings) or bool(existing_secrets), do_classes=list(a.durable_object_classes))
    for b in a.bindings:
        kind = "kv" if b.kind == "kv_or_r2" else b.kind
        it = PlanItem(b.name, kind, note=b.reason)
        cur = by_name.get(b.name)
        if cur or b.name in existing_secrets:
            it.action, it.note = "keep", "already bound on the deployed Worker"
        elif kind == "ai":
            it.action = "ai"
        elif b.source == "config":
            c = b.config
            if kind == "var" and c.get("value") is not None:
                it.action, it.value = "value", str(c["value"])
            elif kind == "kv" and c.get("id"):
                it.action, it.target = "link", c["id"]
            elif kind == "d1" and c.get("id"):
                it.action, it.target = "link", c["id"]
            elif kind == "r2" and c.get("bucket_name"):
                it.action, it.target = "link", c["bucket_name"]
            elif kind == "queue" and c.get("queue_name"):
                it.action, it.target = "link", c["queue_name"]
            elif kind == "service" and c.get("service"):
                it.action, it.target = "link", c["service"]
            elif kind == "durable_object" and c.get("class_name"):
                it.action, it.target = "link", c["class_name"]
                it.note = (it.note + f"; script_name={c['script_name']}") if c.get("script_name") else it.note
            elif kind in AUTO_CREATABLE:
                it.action = "create"
            elif kind == "analytics_engine":
                it.action, it.target = "link", c.get("dataset") or resource_name(worker, b.name)
            elif kind in ("vectorize", "hyperdrive") and (c.get("index_name") or c.get("id")):
                it.action, it.target = "link", c.get("index_name") or c.get("id")
        elif kind in AUTO_CREATABLE:
            it.action = "create"  # default suggestion; user may switch to link/skip
        elif kind == "durable_object" and len(a.durable_object_classes) == 1:
            it.action, it.target = "link", a.durable_object_classes[0]
        elif kind == "analytics_engine":
            it.action, it.target = "link", resource_name(worker, b.name).replace("-", "_")
        p.items.append(it)
    # bindings present on the deployed Worker but not referenced in the new code → keep (inherit)
    for name, cur in by_name.items():
        if not p.item(name):
            p.items.append(PlanItem(name, _kind_of(cur), "keep", note="existing binding not referenced in code"))
    for s in existing_secrets:
        if not p.item(s):
            p.items.append(PlanItem(s, "secret", "keep", note="existing secret"))
    return p


def _kind_of(b: dict) -> str:
    return {"kv_namespace": "kv", "d1": "d1", "r2_bucket": "r2", "queue": "queue", "plain_text": "var",
            "secret_text": "secret", "ai": "ai", "service": "service", "durable_object_namespace": "durable_object",
            "analytics_engine": "analytics_engine", "vectorize": "vectorize", "hyperdrive": "hyperdrive"}.get(b.get("type", ""), b.get("type", "?"))


async def _create_resource(cf: CloudflareClient, kind: str, name: str) -> str:
    if kind == "kv":
        try:
            return (await cf.create_kv(name))["id"]
        except CloudflareError as e:
            if 10014 in e.codes or "already exists" in e.message.lower():
                for ns in await cf.list_kv():
                    if ns.get("title") == name:
                        return ns["id"]
            raise
    if kind == "d1":
        try:
            return (await cf.create_d1(name))["uuid"]
        except CloudflareError as e:
            if "already exists" in e.message.lower():
                for d in await cf.list_d1():
                    if d.get("name") == name:
                        return d["uuid"]
            raise
    if kind == "r2":
        try:
            await cf.create_r2(name)
        except CloudflareError as e:
            if 10004 not in e.codes and "already" not in e.message.lower():
                raise
        return name
    if kind == "queue":
        try:
            await cf.create_queue(name)
        except CloudflareError as e:
            if 11009 not in e.codes and "already" not in e.message.lower():
                raise
        return name
    raise CloudflareError(0, f"cannot auto-create {kind}")


def binding_for(it: PlanItem, plan: Plan) -> dict | None:
    k, n = it.kind, it.name
    if it.action in ("skip", "pending"):
        return None
    if it.action == "keep":
        return {"type": "inherit", "name": n}
    if it.action == "ai" or k == "ai":
        return {"type": "ai", "name": n}
    if k == "var":
        return {"type": "plain_text", "name": n, "text": it.value or ""}
    if k == "secret":
        return {"type": "secret_text", "name": n, "text": it.value or ""}
    if k == "kv":
        return {"type": "kv_namespace", "name": n, "namespace_id": it.target}
    if k == "d1":
        return {"type": "d1", "name": n, "id": it.target}
    if k == "r2":
        return {"type": "r2_bucket", "name": n, "bucket_name": it.target}
    if k == "queue":
        return {"type": "queue", "name": n, "queue_name": it.target}
    if k == "service":
        return {"type": "service", "name": n, "service": it.target, "environment": "production"}
    if k == "durable_object":
        b = {"type": "durable_object_namespace", "name": n, "class_name": it.target}
        m = re.search(r"script_name=([\w-]+)", it.note or "")
        if m:
            b["script_name"] = m.group(1)
        return b
    if k == "analytics_engine":
        return {"type": "analytics_engine", "name": n, "dataset": it.target}
    if k == "vectorize":
        return {"type": "vectorize", "name": n, "index_name": it.target}
    if k == "hyperdrive":
        return {"type": "hyperdrive", "name": n, "id": it.target}
    return None


async def execute(cf: CloudflareClient, plan: Plan, modules: dict[str, bytes], *, progress: Progress | None = None,
                  service_worker: bool = False) -> dict:
    """Create resources, upload code with bindings, set crons, enable workers.dev. Returns a report."""
    async def say(m: str):
        if progress:
            await progress(m)

    if plan.pending:
        raise CloudflareError(0, "plan has unresolved items: " + ", ".join(i.name for i in plan.pending))
    report: dict = {"created": [], "bindings": [], "url": None, "crons": [], "warnings": []}

    for it in plan.items:
        if it.action == "create":
            name = it.target or resource_name(plan.worker, it.name)
            await say(f"Creating {it.kind.upper()} '{name}' for {it.name}…")
            it.target = await _create_resource(cf, it.kind, name)
            it.action = "link"
            report["created"].append({"binding": it.name, "kind": it.kind, "id": it.target, "name": name})

    # R2 buckets / queues are linked by NAME (wrangler config or typed by the user): make sure they exist,
    # otherwise the upload fails with "bucket not found" — create them with exactly that name.
    by_kind: dict[str, set[str]] = {}
    for it in plan.items:
        if it.action == "link" and it.kind in ("r2", "queue") and it.target:
            if it.kind not in by_kind:
                try:
                    by_kind[it.kind] = ({b["name"] for b in await cf.list_r2()} if it.kind == "r2"
                                        else {q["queue_name"] for q in await cf.list_queues()})
                except CloudflareError as e:
                    report["warnings"].append(f"could not verify {it.kind} '{it.target}': {e.message}")
                    by_kind[it.kind] = {it.target}
            if it.target not in by_kind[it.kind]:
                await say(f"{it.kind.upper()} '{it.target}' does not exist yet — creating it for {it.name}…")
                await _create_resource(cf, it.kind, it.target)
                by_kind[it.kind].add(it.target)
                report["created"].append({"binding": it.name, "kind": it.kind, "id": it.target, "name": it.target})

    bindings = [b for b in (binding_for(i, plan) for i in plan.items) if b]
    metadata: dict = {"compatibility_date": plan.compatibility_date, "bindings": bindings}
    if plan.compatibility_flags:
        metadata["compatibility_flags"] = plan.compatibility_flags
    if service_worker:
        metadata["body_part"] = plan.main
    else:
        metadata["main_module"] = plan.main
    if plan.do_classes and not plan.existing:
        metadata["migrations"] = {"new_tag": "v1", "new_sqlite_classes": plan.do_classes}
    if any(b["type"] == "inherit" for b in bindings):
        metadata["keep_bindings"] = ["secret_text", "secret_key"]
    if service_worker:
        # body_part upload: the API validates main_module presence differently
        md = dict(metadata)
        files_meta = md
        await say(f"Uploading {len(modules)} file(s) as service-worker script…")
        res = await _upload_sw(cf, plan.worker, modules, files_meta)
    else:
        await say(f"Uploading {len(modules)} module(s) with {len(bindings)} binding(s)…")
        res = await cf.upload_worker(plan.worker, modules, metadata)
    report["bindings"] = [{"name": b["name"], "type": b["type"]} for b in bindings]
    report["upload"] = {k: res.get(k) for k in ("id", "etag", "handlers", "compatibility_date", "usage_model") if isinstance(res, dict)}

    if plan.crons:
        await say("Setting cron triggers…")
        report["crons"] = [s.get("cron") for s in await cf.set_schedules(plan.worker, plan.crons)]
    if plan.enable_workers_dev:
        try:
            await cf.set_worker_subdomain(plan.worker, True)
            sub = await cf.account_subdomain()
            if sub:
                report["url"] = f"https://{plan.worker}.{sub}.workers.dev"
            else:
                report["warnings"].append("Account has no workers.dev subdomain yet — register one in the dashboard (Workers & Pages → Overview).")
        except CloudflareError as e:
            report["warnings"].append(f"workers.dev not enabled: {e.message}")
    return report


async def _upload_sw(cf: CloudflareClient, name: str, modules: dict[str, bytes], metadata: dict) -> dict:
    import json as _json

    from .client import content_type_for
    files = [("metadata", (None, _json.dumps(metadata), "application/json"))]
    for fname, data in modules.items():
        ct = "application/javascript" if fname == metadata.get("body_part") else content_type_for(fname)
        files.append((fname, (fname, data, ct)))
    return await cf._call("PUT", f"/accounts/{cf.acct()}/workers/scripts/{name}", files=files)
