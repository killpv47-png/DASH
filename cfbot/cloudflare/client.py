"""Async Cloudflare API v4 client.

Design rules (same as the old GitHub client, adapted):
  * every call goes through ``_request`` → handles 429 (Retry-After), transient 5xx,
    network errors with capped backoff; never crashes the bot, raises a typed
    ``CloudflareError`` the UI can show.
  * Cloudflare wraps responses in ``{success, errors, messages, result, result_info}``;
    ``_call`` unwraps ``result`` and turns ``errors`` into a readable message.
  * two auth modes (official):
      - API token  → ``Authorization: Bearer <token>``           (recommended)
      - Global API Key → ``X-Auth-Email`` + ``X-Auth-Key``         (legacy, all permissions)
  * ``on_wait`` lets the UI say "waiting Ns" instead of appearing frozen.

Endpoints are taken from https://developers.cloudflare.com/api/ (Workers scripts,
secrets, settings, schedules, deployments, versions, subdomain, routes, domains,
KV, D1, R2, Queues, zones, tokens/verify, GraphQL analytics).
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from email.parser import BytesParser
from email.policy import default as _email_policy
from typing import Any, Awaitable, Callable

import httpx

log = logging.getLogger(__name__)

API = "https://api.cloudflare.com/client/v4"
WaitCB = Callable[[float, str], Awaitable[None]]

GLOBAL_KEY_RE = re.compile(r"^[a-f0-9]{37}$")
SCRIPT_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")

JS_CT = "application/javascript+module"
CT_BY_EXT = {
    ".js": JS_CT, ".mjs": JS_CT, ".cjs": "application/javascript", ".py": "text/x-python",
    ".wasm": "application/wasm", ".map": "application/source-map", ".txt": "text/plain",
    ".html": "text/plain", ".json": "text/plain", ".sql": "text/plain", ".bin": "application/octet-stream",
}


class CloudflareError(Exception):
    def __init__(self, status: int, message: str, errors: list | None = None):
        super().__init__(f"Cloudflare {status}: {message}")
        self.status = status
        self.message = message
        self.errors = errors or []

    @property
    def codes(self) -> set[int]:
        return {e.get("code") for e in self.errors if isinstance(e, dict)}


class RateLimited(CloudflareError):
    def __init__(self, reset_in: float):
        super().__init__(429, f"rate limited, retry in {int(reset_in)}s")
        self.reset_in = reset_in


def _err_text(data: Any, fallback: str) -> tuple[str, list]:
    if isinstance(data, dict):
        errs = data.get("errors") or []
        parts = []
        for e in errs:
            if isinstance(e, dict):
                parts.append(f"[{e.get('code')}] {e.get('message')}")
            else:
                parts.append(str(e))
        if parts:
            return "; ".join(parts), errs
        if data.get("message"):
            return str(data["message"]), []
    return fallback[:300], []


def content_type_for(name: str) -> str:
    for ext, ct in CT_BY_EXT.items():
        if name.lower().endswith(ext):
            return ct
    return "application/octet-stream"


class CloudflareClient:
    def __init__(self, token: str = "", *, email: str = "", global_key: str = "", account_id: str = "",
                 on_wait: WaitCB | None = None, timeout: float = 60.0, max_wait: float = 600.0):
        if not token and not (email and global_key):
            raise ValueError("need an API token or email + Global API Key")
        self.auth_mode = "token" if token else "global_key"
        headers = {"User-Agent": "cfbot-telegram/2.0"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        else:
            headers["X-Auth-Email"] = email
            headers["X-Auth-Key"] = global_key
        self.account_id = account_id
        self.on_wait = on_wait
        self.max_wait = max_wait
        self._client = httpx.AsyncClient(base_url=API, timeout=timeout, headers=headers, follow_redirects=True)
        self.token_kind: str | None = None  # "user" | "account" | "global_key"

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "CloudflareClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    # ------------------------------------------------------------------ core
    def acct(self, account_id: str | None = None) -> str:
        a = account_id or self.account_id
        if not a:
            raise CloudflareError(0, "no Cloudflare account selected (scan first or pass account_id)")
        return a

    async def _request(self, method: str, path: str, *, retries: int = 6, **kw) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                resp = await self._client.request(method, path, **kw)
            except (httpx.TransportError, httpx.TimeoutException) as e:
                last_exc = e
                await asyncio.sleep(min(1.5 ** attempt, 20))
                continue
            if resp.status_code == 429:
                ra = resp.headers.get("retry-after")
                wait = float(ra) if ra and ra.replace(".", "", 1).isdigit() else min(30.0 * (attempt + 1), 300.0)
                if wait > self.max_wait:
                    raise RateLimited(wait)
                if self.on_wait:
                    try:
                        await self.on_wait(wait, "cloudflare_rate_limit")
                    except Exception:  # pragma: no cover
                        pass
                log.warning("Cloudflare rate limited; sleeping %.0fs", wait)
                await asyncio.sleep(wait)
                continue
            if resp.status_code in (500, 502, 503, 504) and attempt < retries - 1:
                await asyncio.sleep(min(1.5 ** attempt, 20))
                continue
            return resp
        raise CloudflareError(0, f"network error: {last_exc}") if last_exc else CloudflareError(0, "retries exhausted")

    async def _call(self, method: str, path: str, *, full: bool = False, **kw) -> Any:
        resp = await self._request(method, path, **kw)
        try:
            data = resp.json() if resp.content else {}
        except ValueError:
            data = None
        if resp.status_code >= 400 or (isinstance(data, dict) and data.get("success") is False):
            msg, errs = _err_text(data, resp.text or f"HTTP {resp.status_code}")
            raise CloudflareError(resp.status_code, msg, errs)
        if data is None:
            return resp.text
        if full:
            return data
        return data.get("result") if isinstance(data, dict) and "result" in data else data

    async def get(self, path: str, **params) -> Any:
        return await self._call("GET", path, params={k: v for k, v in params.items() if v is not None} or None)

    async def post(self, path: str, json: Any = None, **kw) -> Any:
        return await self._call("POST", path, json=json, **kw)

    async def put(self, path: str, json: Any = None, **kw) -> Any:
        return await self._call("PUT", path, json=json, **kw)

    async def patch(self, path: str, json: Any = None, **kw) -> Any:
        return await self._call("PATCH", path, json=json, **kw)

    async def delete(self, path: str, **kw) -> Any:
        return await self._call("DELETE", path, **kw)

    async def paginate(self, path: str, *, per_page: int = 50, max_pages: int = 20, key: str | None = None, **params) -> list:
        out: list = []
        page = 1
        while page <= max_pages:
            data = await self._call("GET", path, full=True, params={"page": page, "per_page": per_page, **params})
            res = data.get("result") or []
            items = res.get(key, []) if key and isinstance(res, dict) else res
            out.extend(items or [])
            info = data.get("result_info") or {}
            total_pages = info.get("total_pages")
            if not items or (total_pages and page >= total_pages) or (not total_pages and len(items) < per_page):
                break
            page += 1
        return out

    # ------------------------------------------------------------ identity
    async def verify(self) -> dict:
        """Validate credentials. Returns {"kind", "status", "id", ...}.

        * user API token  → GET /user/tokens/verify
        * account API token → /user/tokens/verify fails (code 1000 "Invalid API Token"); we then need the
          account id: GET /accounts lists accounts the token can see, then /accounts/{id}/tokens/verify.
        * Global API Key  → GET /user
        """
        if self.auth_mode == "global_key":
            u = await self.get("/user")
            self.token_kind = "global_key"
            return {"kind": "global_key", "status": "active", "id": None, "email": u.get("email")}
        try:
            r = await self.get("/user/tokens/verify")
            self.token_kind = "user"
            return {"kind": "user", **(r or {})}
        except CloudflareError as first:
            try:
                accounts = await self.get("/accounts", per_page=50)
            except CloudflareError:
                raise first
            for a in accounts or []:
                try:
                    r = await self.get(f"/accounts/{a['id']}/tokens/verify")
                    self.token_kind = "account"
                    if not self.account_id:
                        self.account_id = a["id"]
                    return {"kind": "account", "account_id": a["id"], **(r or {})}
                except CloudflareError:
                    continue
            raise first

    async def token_details(self, token_id: str) -> dict | None:
        """Policies of the current token (needs 'API Tokens Read'; returns None when not permitted)."""
        try:
            if self.token_kind == "account":
                return await self.get(f"/accounts/{self.acct()}/tokens/{token_id}")
            return await self.get(f"/user/tokens/{token_id}")
        except CloudflareError:
            return None

    async def user(self) -> dict | None:
        try:
            return await self.get("/user")
        except CloudflareError:
            return None  # account tokens / tokens without User Details Read

    async def list_accounts(self) -> list[dict]:
        return await self.paginate("/accounts", per_page=50, max_pages=5)

    async def get_account(self, account_id: str | None = None) -> dict:
        return await self.get(f"/accounts/{self.acct(account_id)}")

    # ------------------------------------------------------------ workers
    async def list_workers(self, account_id: str | None = None) -> list[dict]:
        return await self.get(f"/accounts/{self.acct(account_id)}/workers/scripts") or []

    async def get_worker_settings(self, name: str) -> dict:
        """Bindings (names/types; secret values never returned), compatibility date/flags, logpush, observability…"""
        return await self.get(f"/accounts/{self.acct()}/workers/scripts/{name}/settings") or {}

    async def get_script_settings(self, name: str) -> dict:
        return await self.get(f"/accounts/{self.acct()}/workers/scripts/{name}/script-settings") or {}

    async def patch_script_settings(self, name: str, fields: dict) -> dict:
        """Script-level settings (logpush, observability, tags, tail_consumers) — JSON PATCH."""
        return await self.patch(f"/accounts/{self.acct()}/workers/scripts/{name}/script-settings", fields)

    async def patch_worker_settings(self, name: str, settings: dict) -> dict:
        """Script+version settings (bindings, compatibility_date/flags, limits, placement…).

        Official format: multipart form field ``settings`` with JSON. Bindings must be the FULL list;
        use ``{"type": "inherit", "name": X}`` to keep an existing binding (e.g. secrets) unchanged.
        """
        files = {"settings": (None, _json.dumps(settings), "application/json")}
        return await self._call("PATCH", f"/accounts/{self.acct()}/workers/scripts/{name}/settings", files=files)

    async def get_worker_content(self, name: str) -> dict[str, bytes]:
        """Download the deployed modules. Response is multipart/form-data → {filename: bytes}."""
        resp = await self._request("GET", f"/accounts/{self.acct()}/workers/scripts/{name}/content/v2")
        if resp.status_code >= 400:
            try:
                msg, errs = _err_text(resp.json(), resp.text)
            except ValueError:
                msg, errs = resp.text[:300], []
            raise CloudflareError(resp.status_code, msg, errs)
        ctype = resp.headers.get("content-type", "")
        if "multipart" not in ctype:
            name_hdr = resp.headers.get("cf-entrypoint") or "worker.js"
            return {name_hdr: resp.content}
        msg = BytesParser(policy=_email_policy).parsebytes(b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + resp.content)
        out: dict[str, bytes] = {}
        for part in msg.iter_parts():
            fname = part.get_param("filename", header="content-disposition") or part.get_param("name", header="content-disposition") or "module"
            out[fname] = part.get_payload(decode=True) or b""
        return out

    async def upload_worker(self, name: str, modules: dict[str, bytes], metadata: dict) -> dict:
        """Create or replace a Worker and deploy it immediately (Script Upload API, multipart).

        ``metadata`` = {main_module, compatibility_date, compatibility_flags, bindings[], keep_bindings[], …}
        Each module is a form part whose *name* equals the filename referenced by ``main_module``.
        """
        if metadata.get("main_module") not in modules:
            raise CloudflareError(0, f"main_module {metadata.get('main_module')!r} is not among the uploaded files")
        files: list[tuple[str, tuple]] = [("metadata", (None, _json.dumps(metadata), "application/json"))]
        for fname, data in modules.items():
            files.append((fname, (fname, data, content_type_for(fname))))
        return await self._call("PUT", f"/accounts/{self.acct()}/workers/scripts/{name}", files=files)

    async def delete_worker(self, name: str, force: bool = False) -> None:
        await self.delete(f"/accounts/{self.acct()}/workers/scripts/{name}", params={"force": "true"} if force else None)

    # secrets
    async def list_secrets(self, name: str) -> list[dict]:
        return await self.get(f"/accounts/{self.acct()}/workers/scripts/{name}/secrets") or []

    async def put_secret(self, name: str, key: str, value: str) -> dict:
        return await self.put(f"/accounts/{self.acct()}/workers/scripts/{name}/secrets",
                              {"name": key, "text": value, "type": "secret_text"})

    async def delete_secret(self, name: str, key: str) -> None:
        await self.delete(f"/accounts/{self.acct()}/workers/scripts/{name}/secrets/{key}")

    # plain-text vars (done through settings so nothing else changes)
    async def set_bindings(self, name: str, mutate: Callable[[list[dict]], list[dict]]) -> dict:
        """Read current bindings, apply ``mutate`` and PATCH back. Secret bindings are re-sent as ``inherit``
        (their value is never returned by the API, inherit keeps it)."""
        cur = await self.get_worker_settings(name)
        bindings = []
        for b in cur.get("bindings") or []:
            if b.get("type") == "secret_text":
                bindings.append({"type": "inherit", "name": b["name"]})
            else:
                bindings.append(b)
        return await self.patch_worker_settings(name, {"bindings": mutate(bindings)})

    async def set_var(self, name: str, key: str, value: str) -> dict:
        def m(bs):
            bs = [b for b in bs if b.get("name") != key]
            bs.append({"type": "plain_text", "name": key, "text": value})
            return bs
        return await self.set_bindings(name, m)

    async def delete_binding(self, name: str, key: str) -> dict:
        return await self.set_bindings(name, lambda bs: [b for b in bs if b.get("name") != key])

    async def add_binding(self, name: str, binding: dict) -> dict:
        def m(bs):
            bs = [b for b in bs if b.get("name") != binding["name"]]
            bs.append(binding)
            return bs
        return await self.set_bindings(name, m)

    # cron triggers
    async def get_schedules(self, name: str) -> list[dict]:
        r = await self.get(f"/accounts/{self.acct()}/workers/scripts/{name}/schedules") or {}
        return r.get("schedules", []) if isinstance(r, dict) else r

    async def set_schedules(self, name: str, crons: list[str]) -> list[dict]:
        r = await self.put(f"/accounts/{self.acct()}/workers/scripts/{name}/schedules", [{"cron": c} for c in crons])
        return r.get("schedules", []) if isinstance(r, dict) else (r or [])

    # workers.dev
    async def account_subdomain(self) -> str | None:
        try:
            r = await self.get(f"/accounts/{self.acct()}/workers/subdomain")
            return r.get("subdomain") if isinstance(r, dict) else None
        except CloudflareError:
            return None

    async def get_worker_subdomain(self, name: str) -> dict:
        return await self.get(f"/accounts/{self.acct()}/workers/scripts/{name}/subdomain") or {}

    async def set_worker_subdomain(self, name: str, enabled: bool, previews: bool | None = None) -> dict:
        body: dict[str, Any] = {"enabled": enabled}
        if previews is not None:
            body["previews_enabled"] = previews
        return await self.post(f"/accounts/{self.acct()}/workers/scripts/{name}/subdomain", body)

    # deployments / versions / rollback
    async def list_deployments(self, name: str) -> list[dict]:
        r = await self.get(f"/accounts/{self.acct()}/workers/scripts/{name}/deployments") or {}
        return r.get("deployments", []) if isinstance(r, dict) else r

    async def list_versions(self, name: str, per_page: int = 10) -> list[dict]:
        r = await self.get(f"/accounts/{self.acct()}/workers/scripts/{name}/versions", per_page=per_page) or {}
        return r.get("items", []) if isinstance(r, dict) else r

    async def deploy_version(self, name: str, version_id: str, message: str = "") -> dict:
        body: dict[str, Any] = {"strategy": "percentage", "versions": [{"percentage": 100, "version_id": version_id}]}
        if message:
            body["annotations"] = {"workers/message": message[:100]}
        return await self.post(f"/accounts/{self.acct()}/workers/scripts/{name}/deployments", body)

    # routes / custom domains / zones
    async def list_zones(self, name: str | None = None) -> list[dict]:
        params = {"name": name} if name else {}
        if self.account_id:
            params["account.id"] = self.account_id
        return await self.paginate("/zones", per_page=50, max_pages=5, **params)

    async def list_routes(self, zone_id: str) -> list[dict]:
        return await self.get(f"/zones/{zone_id}/workers/routes") or []

    async def create_route(self, zone_id: str, pattern: str, script: str) -> dict:
        return await self.post(f"/zones/{zone_id}/workers/routes", {"pattern": pattern, "script": script})

    async def delete_route(self, zone_id: str, route_id: str) -> None:
        await self.delete(f"/zones/{zone_id}/workers/routes/{route_id}")

    async def list_domains(self, service: str | None = None) -> list[dict]:
        return await self.get(f"/accounts/{self.acct()}/workers/domains", service=service) or []

    async def attach_domain(self, hostname: str, service: str, zone_id: str, environment: str = "production") -> dict:
        return await self.put(f"/accounts/{self.acct()}/workers/domains",
                              {"hostname": hostname, "service": service, "zone_id": zone_id, "environment": environment})

    async def detach_domain(self, domain_id: str) -> None:
        await self.delete(f"/accounts/{self.acct()}/workers/domains/{domain_id}")

    async def worker_routes(self, name: str) -> list[dict]:
        """Routes pointing at ``name`` across all zones the token can read."""
        out = []
        try:
            zones = await self.list_zones()
        except CloudflareError:
            return out
        sem = asyncio.Semaphore(5)

        async def one(z):
            async with sem:
                try:
                    for r in await self.list_routes(z["id"]):
                        if r.get("script") == name:
                            out.append({**r, "zone_id": z["id"], "zone_name": z["name"]})
                except CloudflareError:
                    pass
        await asyncio.gather(*(one(z) for z in zones[:50]))
        return out

    # ------------------------------------------------------------ KV
    async def list_kv(self) -> list[dict]:
        return await self.paginate(f"/accounts/{self.acct()}/storage/kv/namespaces", per_page=100, max_pages=5)

    async def create_kv(self, title: str) -> dict:
        return await self.post(f"/accounts/{self.acct()}/storage/kv/namespaces", {"title": title})

    async def delete_kv(self, ns_id: str) -> None:
        await self.delete(f"/accounts/{self.acct()}/storage/kv/namespaces/{ns_id}")

    async def kv_keys(self, ns_id: str, prefix: str | None = None, limit: int = 100) -> list[dict]:
        return await self.get(f"/accounts/{self.acct()}/storage/kv/namespaces/{ns_id}/keys", prefix=prefix, limit=limit) or []

    async def kv_get(self, ns_id: str, key: str) -> str | None:
        resp = await self._request("GET", f"/accounts/{self.acct()}/storage/kv/namespaces/{ns_id}/values/{key}")
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            msg, errs = _err_text(resp.json() if resp.content else {}, resp.text)
            raise CloudflareError(resp.status_code, msg, errs)
        return resp.text

    async def kv_put(self, ns_id: str, key: str, value: str) -> None:
        files = {"value": (None, value), "metadata": (None, "{}")}
        await self._call("PUT", f"/accounts/{self.acct()}/storage/kv/namespaces/{ns_id}/values/{key}", files=files)

    async def kv_delete(self, ns_id: str, key: str) -> None:
        await self.delete(f"/accounts/{self.acct()}/storage/kv/namespaces/{ns_id}/values/{key}")

    # ------------------------------------------------------------ D1
    async def list_d1(self) -> list[dict]:
        return await self.paginate(f"/accounts/{self.acct()}/d1/database", per_page=50, max_pages=5)

    async def create_d1(self, name: str, location: str | None = None) -> dict:
        body: dict[str, Any] = {"name": name}
        if location:
            body["primary_location_hint"] = location
        return await self.post(f"/accounts/{self.acct()}/d1/database", body)

    async def delete_d1(self, db_id: str) -> None:
        await self.delete(f"/accounts/{self.acct()}/d1/database/{db_id}")

    async def d1_query(self, db_id: str, sql: str, params: list | None = None) -> list[dict]:
        body: dict[str, Any] = {"sql": sql}
        if params:
            body["params"] = params
        return await self.post(f"/accounts/{self.acct()}/d1/database/{db_id}/query", body) or []

    # ------------------------------------------------------------ R2
    async def list_r2(self) -> list[dict]:
        r = await self.get(f"/accounts/{self.acct()}/r2/buckets") or {}
        return r.get("buckets", []) if isinstance(r, dict) else r

    async def create_r2(self, name: str, location: str | None = None) -> dict:
        body: dict[str, Any] = {"name": name}
        if location:
            body["locationHint"] = location
        return await self.post(f"/accounts/{self.acct()}/r2/buckets", body)

    async def delete_r2(self, name: str) -> None:
        await self.delete(f"/accounts/{self.acct()}/r2/buckets/{name}")

    # ------------------------------------------------------------ Queues
    async def list_queues(self) -> list[dict]:
        return await self.get(f"/accounts/{self.acct()}/queues") or []

    async def create_queue(self, name: str) -> dict:
        return await self.post(f"/accounts/{self.acct()}/queues", {"queue_name": name})

    async def delete_queue(self, queue_id: str) -> None:
        await self.delete(f"/accounts/{self.acct()}/queues/{queue_id}")

    # ------------------------------------------------------------ analytics
    async def worker_metrics(self, name: str | None = None, hours: int = 24) -> dict:
        """Requests / errors / subrequests / CPU p50/p99 over the last ``hours`` (GraphQL Analytics API,
        dataset ``workersInvocationsAdaptive``; needs Account Analytics Read)."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=hours)
        filt = "datetime_geq: $start, datetime_leq: $end" + (", scriptName: $script" if name else "")
        query = (
            "query($account: String!, $start: Time, $end: Time" + (", $script: String" if name else "") + ") {"
            " viewer { accounts(filter: {accountTag: $account}) {"
            f" workersInvocationsAdaptive(limit: 1000, filter: {{{filt}}}) {{"
            " sum { requests errors subrequests } quantiles { cpuTimeP50 cpuTimeP99 } dimensions { scriptName status } } } } }"
        )
        variables = {"account": self.acct(), "start": start.isoformat().replace("+00:00", "Z"),
                     "end": end.isoformat().replace("+00:00", "Z")}
        if name:
            variables["script"] = name
        data = await self._call("POST", "/graphql", full=True, json={"query": query, "variables": variables})
        if data.get("errors"):
            raise CloudflareError(400, "; ".join(str(e.get("message")) for e in data["errors"])[:300])
        rows = (((data.get("data") or {}).get("viewer") or {}).get("accounts") or [{}])[0].get("workersInvocationsAdaptive") or []
        per: dict[str, dict] = {}
        for r in rows:
            sn = r["dimensions"]["scriptName"]
            p = per.setdefault(sn, {"requests": 0, "errors": 0, "subrequests": 0, "cpu_p50": 0.0, "cpu_p99": 0.0})
            for k in ("requests", "errors", "subrequests"):
                p[k] += r["sum"].get(k) or 0
            p["cpu_p50"] = max(p["cpu_p50"], r["quantiles"].get("cpuTimeP50") or 0)
            p["cpu_p99"] = max(p["cpu_p99"], r["quantiles"].get("cpuTimeP99") or 0)
        return {"hours": hours, "scripts": per}

    # ------------------------------------------------------------ misc
    async def probe(self, path: str) -> bool:
        try:
            await self.get(path)
            return True
        except CloudflareError:
            return False

    async def raw(self, method: str, path: str, body: Any = None, params: dict | None = None) -> Any:
        return await self._call(method.upper(), path, full=True, json=body if method.upper() != "GET" else None, params=params)


def now_ts() -> float:
    return time.time()
