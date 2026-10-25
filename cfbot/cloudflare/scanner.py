"""Account scan: identity, accounts, Workers, storage, zones, workers.dev subdomain, capabilities."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from .access import AccessLevel, Capabilities, caps_from_policies, classify_access
from .client import CloudflareClient, CloudflareError


@dataclass
class ScanResult:
    email: str = ""
    kind: str = ""                   # user | account | global_key
    token_status: str = ""
    expires_on: str | None = None
    accounts: list[dict] = field(default_factory=list)
    account_id: str = ""
    account_name: str = ""
    subdomain: str | None = None
    workers: list[dict] = field(default_factory=list)
    kv: list[dict] = field(default_factory=list)
    d1: list[dict] = field(default_factory=list)
    r2: list[dict] = field(default_factory=list)
    queues: list[dict] = field(default_factory=list)
    zones: list[dict] = field(default_factory=list)
    caps: Capabilities | None = None
    level: AccessLevel | None = None
    errors: list[str] = field(default_factory=list)


async def scan_account(cf: CloudflareClient, *, account_id: str | None = None, progress=None) -> ScanResult:
    res = ScanResult()

    async def say(msg: str):
        if progress:
            await progress(msg)

    await say("credentials")
    v = await cf.verify()
    res.kind = v.get("kind", "")
    res.token_status = v.get("status", "")
    res.expires_on = v.get("expires_on")
    u = await cf.user()
    res.email = (u or {}).get("email", "") or v.get("email") or ""

    await say("accounts")
    try:
        res.accounts = await cf.list_accounts()
    except CloudflareError as e:
        res.errors.append(f"accounts: {e.message}")
    chosen = account_id or cf.account_id or (res.accounts[0]["id"] if res.accounts else "")
    if res.accounts and chosen not in {a["id"] for a in res.accounts}:
        chosen = res.accounts[0]["id"]
    cf.account_id = chosen
    res.account_id = chosen
    res.account_name = next((a.get("name", "") for a in res.accounts if a["id"] == chosen), "")
    if not chosen:
        res.errors.append("no account visible to this credential (add 'Account Settings Read')")
        res.caps = Capabilities()
        res.level = classify_access(res.caps, global_key=res.kind == "global_key")
        return res

    await say("resources")
    caps = None
    if res.kind != "global_key" and v.get("id"):
        details = await cf.token_details(v["id"])
        if details and details.get("policies"):
            caps = caps_from_policies(details["policies"])

    tasks = {
        "workers": cf.list_workers(), "kv": cf.list_kv(), "d1": cf.list_d1(), "r2": cf.list_r2(),
        "queues": cf.list_queues(), "zones": cf.list_zones(), "subdomain": cf.account_subdomain(),
    }
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    ok: dict[str, bool] = {}
    for (name, _), val in zip(tasks.items(), results):
        if isinstance(val, CloudflareError):
            ok[name] = False
            if val.status not in (401, 403) and not ({10000, 9109} & val.codes):
                res.errors.append(f"{name}: {val.message[:120]}")
            continue
        if isinstance(val, Exception):
            ok[name] = False
            res.errors.append(f"{name}: {val}")
            continue
        ok[name] = True
        if name == "subdomain":
            res.subdomain = val
        else:
            setattr(res, name, val or [])

    await say("analytics")
    analytics_ok = False
    try:
        await cf.worker_metrics(None, hours=1)
        analytics_ok = True
    except Exception:
        pass

    if caps is None:  # infer from probes
        caps = Capabilities(exact=False)
        caps.workers_read = ok.get("workers", False)
        caps.workers_write = caps.workers_read  # verified at action time
        caps.kv, caps.d1, caps.r2, caps.queues = ok.get("kv", False), ok.get("d1", False), ok.get("r2", False), ok.get("queues", False)
        caps.zones = ok.get("zones", False) and bool(res.zones)
        caps.routes_write = caps.zones
        caps.dns_write = caps.zones
        caps.analytics = analytics_ok
    res.caps = caps
    res.level = classify_access(caps, global_key=res.kind == "global_key")
    return res
