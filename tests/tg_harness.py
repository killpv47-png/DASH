"""Integration harness: drive the real aiogram Dispatcher with synthetic Updates.

* ``FakeSession`` replaces the Bot's HTTP session — every outgoing API call is
  recorded (so tests assert on what the user would see) and answered with a
  plausible object (Message for send/edit, True for the rest).
* ``FakeCloudflare`` is an httpx MockTransport implementing the Cloudflare API v4
  endpoints the bot touches (envelopes, multipart uploads, errors) with in-memory state.
* ``FakeHost`` emulates the host GitHub repo (checkpoint + dispatch) for lifecycle tests.
* ``Harness`` wires the two together and offers ``text()`` / ``cmd()`` /
  ``tap()`` / ``doc()`` helpers that push Updates through ``dp.feed_update``.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import time
import zipfile

import httpx
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import (AnswerCallbackQuery, DeleteMessage, DeleteWebhook, EditMessageText, GetFile, SendMessage,
                             SetMyCommands, TelegramMethod)
from aiogram.types import (CallbackQuery, Chat, Document, File, Message, Update, User)

from cfbot.core.config import Settings
from cfbot.core.db import Database
from cfbot.cloudflare import client as cfclient
from cfbot.hosting import github_host
from cfbot.telegram.bot import build

USER_ID = 777
CHAT_ID = 777
TOKEN_CF = "cfut_" + "a" * 40
GLOBAL_KEY = "0123456789abcdef0123456789abcdef01234"


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls: list[TelegramMethod] = []
        self._mid = 1000
        self.files: dict[str, bytes] = {}

    async def close(self):
        pass

    async def stream_content(self, url, headers=None, timeout=30, chunk_size=65536, raise_for_status=True):
        data = self.files.get(url.rsplit("/", 1)[-1], b"")
        yield data

    async def make_request(self, bot: Bot, method: TelegramMethod, timeout=None):
        self.calls.append(method)
        now = int(time.time())
        if isinstance(method, SendMessage):
            self._mid += 1
            return Message(message_id=self._mid, date=now, chat=Chat(id=method.chat_id, type="private"),
                           from_user=User(id=1, is_bot=True, first_name="bot"), text=method.text,
                           reply_markup=method.reply_markup if hasattr(method.reply_markup, "inline_keyboard") else None).as_(bot)
        if isinstance(method, EditMessageText):
            return Message(message_id=method.message_id, date=now, chat=Chat(id=method.chat_id, type="private"),
                           from_user=User(id=1, is_bot=True, first_name="bot"), text=method.text,
                           reply_markup=method.reply_markup).as_(bot)
        if isinstance(method, GetFile):
            return File(file_id=method.file_id, file_unique_id="u", file_size=len(self.files.get(method.file_id, b"")),
                        file_path=f"documents/{method.file_id}").as_(bot)
        if isinstance(method, (AnswerCallbackQuery, DeleteMessage, DeleteWebhook, SetMyCommands)):
            return True
        return True

    # ---- helpers for assertions
    def sent_texts(self) -> list[str]:
        return [c.text for c in self.calls if isinstance(c, (SendMessage, EditMessageText)) and c.text]

    def last_text(self) -> str:
        texts = self.sent_texts()
        return texts[-1] if texts else ""

    def all_text(self) -> str:
        return "\n---\n".join(self.sent_texts())

    def last_markup(self):
        for c in reversed(self.calls):
            if isinstance(c, (SendMessage, EditMessageText)) and getattr(c.reply_markup, "inline_keyboard", None):
                return c.reply_markup
        return None

    def buttons(self) -> dict[str, str]:
        """text -> callback_data of the most recent inline keyboard."""
        kb = self.last_markup()
        out = {}
        if kb:
            for row in kb.inline_keyboard:
                for b in row:
                    out[b.text] = b.callback_data
        return out

    def find_button(self, substr: str) -> str | None:
        for text, data in self.buttons().items():
            if substr in text or (data and substr in data):
                return data
        return None

    def clear(self):
        self.calls.clear()


def _parse_multipart(request: httpx.Request) -> dict[str, tuple[str | None, bytes]]:
    """name -> (filename, bytes) for a multipart/form-data request body."""
    from email.parser import BytesParser
    from email.policy import default
    ctype = request.headers.get("content-type", "")
    msg = BytesParser(policy=default).parsebytes(b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + request.content)
    out = {}
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        out[name] = (part.get_param("filename", header="content-disposition"), part.get_payload(decode=True) or b"")
    return out


class FakeCloudflare:
    """In-memory emulation of the Cloudflare API v4 endpoints the bot uses (response envelopes, multipart uploads,
    errors) — so every flow is exercised end-to-end without a real account."""

    ACCOUNT = "acc123"

    def __init__(self, *, token_policies: list | None = None, deny: set[str] | None = None):
        self.workers: dict[str, dict] = {}
        self.secrets: dict[str, dict[str, str]] = {}
        self.crons: dict[str, list[str]] = {}
        self.subdomain_enabled: dict[str, bool] = {}
        self.deployments: dict[str, list[dict]] = {}
        self.versions: dict[str, list[dict]] = {}
        self.kv: dict[str, dict] = {}
        self.kv_data: dict[str, dict[str, str]] = {}
        self.d1: dict[str, dict] = {}
        self.d1_queries: list[tuple[str, str]] = []
        self.r2: dict[str, dict] = {}
        self.queues: dict[str, dict] = {}
        self.zones = {"z1": {"id": "z1", "name": "example.com", "status": "active", "plan": {"name": "Free"}}}
        self.routes: dict[str, list[dict]] = {"z1": []}
        self.domains: list[dict] = []
        self.requests: list[tuple[str, str]] = []
        self.uploads: list[dict] = []
        self.deny = deny or set()           # path substrings that return 10000 auth error
        self.fail_next: tuple[int, int, str] | None = None
        self.rate_limit_once = False
        self.valid_tokens = {TOKEN_CF}
        self.token_policies = token_policies
        self._n = 0
        self.add_worker("hello-api", "export default { async fetch(req, env) { return new Response(env.GREETING) } }",
                        [{"type": "plain_text", "name": "GREETING", "text": "hi"}])

    def _id(self, prefix="id"):
        self._n += 1
        return f"{prefix}{self._n:04d}"

    def add_worker(self, name, code, bindings=None, compat="2025-01-01"):
        vid = self._id("ver-")
        self.workers[name] = {"id": name, "code": {"worker.js": code.encode()}, "main": "worker.js",
                              "bindings": bindings or [], "compatibility_date": compat, "compatibility_flags": [],
                              "handlers": ["fetch"], "modified_on": "2026-10-01T00:00:00Z", "created_on": "2026-09-01T00:00:00Z",
                              "logpush": False, "observability": {"enabled": False}}
        self.secrets.setdefault(name, {})
        self.crons.setdefault(name, [])
        self.subdomain_enabled[name] = True
        self.versions.setdefault(name, []).insert(0, {"id": vid, "metadata": {"number": len(self.versions.get(name, [])) + 1,
                                                       "created_on": "2026-10-01T00:00:00Z", "source": "api"}})
        self.deployments.setdefault(name, []).insert(0, {"id": self._id("dep-"), "source": "api", "strategy": "percentage",
                                                         "created_on": "2026-10-01T00:00:00Z", "author_email": "me@example.com",
                                                         "versions": [{"version_id": vid, "percentage": 100}]})

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/client/v4")
        method = request.method
        self.requests.append((method, path))

        def ok(result=None, status=200, info=None):
            body = {"success": True, "errors": [], "messages": [], "result": result}
            if info:
                body["result_info"] = info
            return httpx.Response(status, json=body)

        def err(status, code, msg):
            return httpx.Response(status, json={"success": False, "errors": [{"code": code, "message": msg}], "messages": [], "result": None})

        auth = request.headers.get("authorization", "")
        gk = request.headers.get("x-auth-key")
        if gk:
            if gk != GLOBAL_KEY or request.headers.get("x-auth-email") != "me@example.com":
                return err(403, 9103, "Unknown X-Auth-Key or X-Auth-Email")
        elif auth.removeprefix("Bearer ") not in self.valid_tokens:
            return err(401, 1000, "Invalid API Token")
        if self.fail_next:
            st, code, msg = self.fail_next
            self.fail_next = None
            return err(st, code, msg)
        if self.rate_limit_once:
            self.rate_limit_once = False
            return httpx.Response(429, headers={"Retry-After": "1"}, json={"success": False, "errors": [{"code": 971, "message": "rate limited"}]})
        if any(d in path for d in self.deny):
            return err(403, 10000, "Authentication error")
        A = f"/accounts/{self.ACCOUNT}"

        if path == "/user/tokens/verify":
            return ok({"id": "tok1", "status": "active", "expires_on": "2027-01-01T00:00:00Z"})
        if path == "/user/tokens/tok1":
            if self.token_policies is None:
                return err(403, 10000, "Authentication error")
            return ok({"id": "tok1", "policies": self.token_policies})
        if path == "/user":
            return ok({"id": "u1", "email": "me@example.com"})
        if path == "/accounts":
            return ok([{"id": self.ACCOUNT, "name": "My Account"}], info={"page": 1, "total_pages": 1})
        if path == "/zones":
            name = request.url.params.get("name")
            zs = [z for z in self.zones.values() if not name or z["name"] == name]
            return ok(zs, info={"page": 1, "total_pages": 1})
        if path == "/graphql":
            q = json.loads(request.content)
            script = q["variables"].get("script")
            rows = [{"sum": {"requests": 120, "errors": 3, "subrequests": 10}, "quantiles": {"cpuTimeP50": 1500, "cpuTimeP99": 9000},
                     "dimensions": {"scriptName": n, "status": "success"}} for n in self.workers if not script or n == script]
            return httpx.Response(200, json={"data": {"viewer": {"accounts": [{"workersInvocationsAdaptive": rows}]}}, "errors": None})
        if path.startswith("/zones/"):
            parts = path.split("/")
            zid = parts[2]
            if parts[3:5] == ["workers", "routes"]:
                if len(parts) == 5 and method == "GET":
                    return ok(self.routes.get(zid, []))
                if len(parts) == 5 and method == "POST":
                    body = json.loads(request.content)
                    r = {"id": self._id("route"), **body}
                    self.routes.setdefault(zid, []).append(r)
                    return ok(r)
                if method == "DELETE":
                    self.routes[zid] = [r for r in self.routes.get(zid, []) if r["id"] != parts[5]]
                    return ok({"id": parts[5]})
        if not path.startswith(A):
            return err(404, 7003, f"Could not route to {path}")
        rest = path[len(A):].strip("/").split("/")

        if rest == ["workers", "subdomain"]:
            return ok({"subdomain": "myacct"})
        if rest[:2] == ["workers", "scripts"]:
            if len(rest) == 2:
                return ok([{k: w[k] for k in ("id", "handlers", "modified_on", "created_on", "compatibility_date")} for w in self.workers.values()])
            name = rest[2]
            sub = rest[3:]
            if not sub and method == "PUT":
                parts = _parse_multipart(request)
                meta = json.loads(parts.pop("metadata")[1])
                main = meta.get("main_module") or meta.get("body_part")
                if main not in parts:
                    return err(400, 10021, "No such module")
                old = self.workers.get(name)
                resolved = []
                for b in meta.get("bindings", []):
                    if b["type"] == "inherit":
                        prev = next((x for x in (old or {}).get("bindings", []) if x["name"] == b["name"]), None)
                        if prev:
                            resolved.append(prev)
                        elif b["name"] in self.secrets.get(name, {}):
                            pass
                        continue
                    if b["type"] == "secret_text":
                        self.secrets.setdefault(name, {})[b["name"]] = b["text"]
                        continue
                    if b["type"] == "kv_namespace" and b["namespace_id"] not in self.kv:
                        return err(400, 10041, f"KV namespace {b['namespace_id']} not found")
                    resolved.append(b)
                self.uploads.append({"name": name, "metadata": meta, "modules": {k: v[1] for k, v in parts.items()}})
                code_text = parts[main][1].decode()
                self.add_worker(name, code_text, resolved, meta.get("compatibility_date", "2021-11-02"))
                self.workers[name]["code"] = {k: v[1] for k, v in parts.items()}
                self.workers[name]["main"] = main
                self.workers[name]["compatibility_flags"] = meta.get("compatibility_flags", [])
                hs = [h for h in ("fetch", "scheduled", "queue") if h in code_text]
                self.workers[name]["handlers"] = hs
                return ok({"id": name, "etag": "e1", "handlers": hs, "compatibility_date": meta.get("compatibility_date")})
            w = self.workers.get(name)
            if w is None:
                return err(404, 10007, "workers.api.error.script_not_found")
            if not sub and method == "DELETE":
                del self.workers[name]
                return ok(None)
            if sub == ["settings"] and method == "GET":
                secrets = [{"type": "secret_text", "name": n} for n in self.secrets.get(name, {})]
                return ok({"bindings": w["bindings"] + secrets, "compatibility_date": w["compatibility_date"],
                           "compatibility_flags": w["compatibility_flags"], "logpush": w["logpush"], "usage_model": "standard"})
            if sub == ["settings"] and method == "PATCH":
                st = json.loads(_parse_multipart(request)["settings"][1])
                if "bindings" in st:
                    nb = []
                    for b in st["bindings"]:
                        if b["type"] == "inherit":
                            prev = next((x for x in w["bindings"] if x["name"] == b["name"]), None)
                            if prev:
                                nb.append(prev)
                            continue
                        nb.append(b)
                    w["bindings"] = nb
                for k in ("compatibility_date", "compatibility_flags"):
                    if k in st:
                        w[k] = st[k]
                return ok({"bindings": w["bindings"]})
            if sub == ["script-settings"]:
                if method == "PATCH":
                    w.update(json.loads(request.content))
                return ok({"logpush": w["logpush"], "observability": w["observability"]})
            if sub == ["content", "v2"]:
                boundary = "cfbnd"
                body = b""
                for fname, data in w["code"].items():
                    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{fname}\"; filename=\"{fname}\"\r\n"
                             f"Content-Type: application/javascript+module\r\n\r\n").encode() + data + b"\r\n"
                body += f"--{boundary}--\r\n".encode()
                return httpx.Response(200, content=body, headers={"content-type": f"multipart/form-data; boundary={boundary}",
                                                                  "cf-entrypoint": w["main"]})
            if sub == ["secrets"]:
                if method == "GET":
                    return ok([{"name": n, "type": "secret_text"} for n in self.secrets.get(name, {})])
                body = json.loads(request.content)
                self.secrets.setdefault(name, {})[body["name"]] = body["text"]
                return ok({"name": body["name"], "type": "secret_text"})
            if sub[:1] == ["secrets"] and method == "DELETE":
                self.secrets.get(name, {}).pop(sub[1], None)
                return ok(None)
            if sub == ["schedules"]:
                if method == "PUT":
                    self.crons[name] = [c["cron"] for c in json.loads(request.content)]
                return ok({"schedules": [{"cron": c} for c in self.crons.get(name, [])]})
            if sub == ["subdomain"]:
                if method == "POST":
                    self.subdomain_enabled[name] = json.loads(request.content)["enabled"]
                return ok({"enabled": self.subdomain_enabled.get(name, False), "previews_enabled": False})
            if sub == ["deployments"]:
                if method == "POST":
                    body = json.loads(request.content)
                    d = {"id": self._id("dep-"), "source": "api", "strategy": "percentage", "created_on": "2026-10-02T00:00:00Z",
                         "author_email": "me@example.com", "versions": body["versions"], "annotations": body.get("annotations", {})}
                    self.deployments[name].insert(0, d)
                    return ok(d)
                return ok({"deployments": self.deployments.get(name, [])})
            if sub == ["versions"]:
                return ok({"items": self.versions.get(name, [])})
        if rest == ["workers", "domains"]:
            if method == "PUT":
                body = json.loads(request.content)
                d = {"id": self._id("dom"), **body}
                self.domains.append(d)
                return ok(d)
            svc = request.url.params.get("service")
            return ok([d for d in self.domains if not svc or d["service"] == svc])
        if rest[:2] == ["workers", "domains"] and method == "DELETE":
            self.domains = [d for d in self.domains if d["id"] != rest[2]]
            return ok(None)
        if rest[:3] == ["storage", "kv", "namespaces"]:
            if len(rest) == 3:
                if method == "POST":
                    title = json.loads(request.content)["title"]
                    if any(n["title"] == title for n in self.kv.values()):
                        return err(400, 10014, "a namespace with this account ID and title already exists")
                    nid_ = self._id("kv")
                    self.kv[nid_] = {"id": nid_, "title": title}
                    self.kv_data[nid_] = {}
                    return ok(self.kv[nid_])
                return ok(list(self.kv.values()), info={"page": 1, "total_pages": 1})
            ns = rest[3]
            if len(rest) == 4 and method == "DELETE":
                self.kv.pop(ns, None)
                return ok(None)
            if rest[4:] == ["keys"]:
                return ok([{"name": k} for k in self.kv_data.get(ns, {})])
            if rest[4] == "values":
                key = rest[5]
                if method == "PUT":
                    self.kv_data[ns][key] = _parse_multipart(request)["value"][1].decode()
                    return ok(None)
                if method == "DELETE":
                    self.kv_data[ns].pop(key, None)
                    return ok(None)
                if key not in self.kv_data.get(ns, {}):
                    return err(404, 10009, "key not found")
                return httpx.Response(200, text=self.kv_data[ns][key])
        if rest[:2] == ["d1", "database"]:
            if len(rest) == 2:
                if method == "POST":
                    name = json.loads(request.content)["name"]
                    u = self._id("d1-")
                    self.d1[u] = {"uuid": u, "name": name, "num_tables": 0}
                    return ok(self.d1[u])
                return ok(list(self.d1.values()), info={"page": 1, "total_pages": 1})
            dbid = rest[2]
            if len(rest) == 3 and method == "DELETE":
                self.d1.pop(dbid, None)
                return ok(None)
            if rest[3:] == ["query"]:
                sql = json.loads(request.content)["sql"]
                self.d1_queries.append((dbid, sql))
                results = [{"name": "notes"}] if "sqlite_master" in sql else [{"x": 1}]
                return ok([{"results": results, "success": True, "meta": {"rows_read": 1, "rows_written": 0, "changes": 0, "duration": 0.2}}])
        if rest[:2] == ["r2", "buckets"]:
            if len(rest) == 2:
                if method == "POST":
                    name = json.loads(request.content)["name"]
                    self.r2[name] = {"name": name, "creation_date": "2026-10-01"}
                    return ok(self.r2[name])
                return ok({"buckets": list(self.r2.values())})
            if method == "DELETE":
                self.r2.pop(rest[2], None)
                return ok(None)
        if rest[:1] == ["queues"]:
            if len(rest) == 1:
                if method == "POST":
                    name = json.loads(request.content)["queue_name"]
                    q = {"queue_id": self._id("q"), "queue_name": name}
                    self.queues[q["queue_id"]] = q
                    return ok(q)
                return ok(list(self.queues.values()))
            if method == "DELETE":
                self.queues.pop(rest[1], None)
                return ok(None)
        return err(404, 7003, f"unhandled {method} {path}")


class FakeHost:
    """Minimal GitHub API emulation for the HOST repo only (checkpoint branch + workflow dispatch)."""

    def __init__(self, repo: str = "owner/cfbot-host"):
        self.repo = repo
        self.branches = {"main"}
        self.files: dict[tuple[str, str], bytes] = {}
        self.dispatches: list[dict] = []
        self.puts = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        pre = f"/repos/{self.repo}"
        if not path.startswith(pre):
            return httpx.Response(404, json={"message": "Not Found"})
        rest = path[len(pre):]
        body = json.loads(request.content) if request.content else {}
        if rest == "":
            return httpx.Response(200, json={"default_branch": "main"})
        if rest.startswith("/git/ref/heads/"):
            br = rest.split("/git/ref/heads/")[1]
            if br in self.branches:
                return httpx.Response(200, json={"object": {"sha": "s0"}})
            return httpx.Response(404, json={"message": "Not Found"})
        if rest == "/git/refs" and request.method == "POST":
            self.branches.add(body["ref"].split("/")[-1])
            return httpx.Response(201, json={})
        if rest.startswith("/contents/"):
            fp = rest[len("/contents/"):]
            br = request.url.params.get("ref") or body.get("branch")
            if request.method == "GET":
                if (br, fp) not in self.files:
                    return httpx.Response(404, json={"message": "Not Found"})
                return httpx.Response(200, json={"encoding": "base64", "sha": "x",
                                                 "content": base64.b64encode(self.files[(br, fp)]).decode()})
            if request.method == "PUT":
                self.files[(body["branch"], fp)] = base64.b64decode(body["content"])
                self.puts += 1
                return httpx.Response(201, json={"content": {}})
        if rest.startswith("/actions/workflows/") and rest.endswith("/dispatches"):
            self.dispatches.append({"workflow": rest.split("/")[3], **body})
            return httpx.Response(204)
        return httpx.Response(404, json={"message": f"unhandled {rest}"})


class Harness:
    def __init__(self, tmp_path, fake_cf: FakeCloudflare, env: dict | None = None, host: FakeHost | None = None):
        import os
        os.environ.update({"BOT_TOKEN": "123456:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "STATE_KEY": "unit-test-state-key-123456",
                           "DATA_DIR": str(tmp_path / "data"), "WORKSPACE_DIR": str(tmp_path / "ws"), **(env or {})})
        self.settings = Settings()
        self.db = Database(self.settings.db_path)
        self.cf = fake_cf
        self.host = host or FakeHost()
        self.tmp_path = tmp_path
        self._uid = 1
        self._mid = 1

    async def __aenter__(self):
        await self.db.open()
        self.bot, self.dp, self.app = build(self.settings, self.db)
        self.session = FakeSession()
        self.bot._session = self.session
        self.bot.session = self.session
        fake, host = self.cf, self.host
        orig_cf = cfclient.CloudflareClient.__init__
        orig_host = github_host.HostRepoClient.__init__

        def patched_cf(self_, *a, **kw):
            orig_cf(self_, *a, **kw)
            self_._client = httpx.AsyncClient(base_url=cfclient.API, transport=httpx.MockTransport(fake.handler),
                                              headers=self_._client.headers)

        def patched_host(self_, token, **kw):
            orig_host(self_, token, **kw)
            self_._client = httpx.AsyncClient(base_url=github_host.API, transport=httpx.MockTransport(host.handler),
                                              headers=self_._client.headers)
        self._orig = (orig_cf, orig_host)
        cfclient.CloudflareClient.__init__ = patched_cf
        github_host.HostRepoClient.__init__ = patched_host
        return self

    async def __aexit__(self, *exc):
        cfclient.CloudflareClient.__init__, github_host.HostRepoClient.__init__ = self._orig
        for t in list(self.app.ai_tasks.values()):
            if not t.done():
                t.cancel()
        await asyncio.sleep(0)
        await self.db.close()

    # ------------------------------------------------------------ updates
    def _user(self):
        return User(id=USER_ID, is_bot=False, first_name="Tester", username="tester")

    def _chat(self):
        return Chat(id=CHAT_ID, type="private")

    def _message(self, text: str | None = None, document: Document | None = None) -> Message:
        self._mid += 1
        return Message(message_id=self._mid, date=int(time.time()), chat=self._chat(), from_user=self._user(),
                       text=text, document=document)

    async def feed(self, update: Update):
        await self.dp.feed_update(self.bot, update)
        await asyncio.sleep(0)

    async def text(self, text: str):
        self._uid += 1
        await self.feed(Update(update_id=self._uid, message=self._message(text)))

    cmd = text

    async def tap(self, data: str, message_id: int | None = None):
        self._uid += 1
        bot_msg = Message(message_id=message_id or self.session._mid, date=int(time.time()), chat=self._chat(),
                          from_user=User(id=1, is_bot=True, first_name="bot"), text="…")
        cb = CallbackQuery(id=str(self._uid), from_user=self._user(), chat_instance="ci", data=data, message=bot_msg)
        await self.feed(Update(update_id=self._uid, callback_query=cb))

    async def tap_button(self, substr: str):
        data = self.session.find_button(substr)
        assert data, f"no button matching {substr!r} in {list(self.session.buttons())}"
        await self.tap(data)
        return data

    async def doc(self, file_name: str, content: bytes, mime="application/octet-stream"):
        self._uid += 1
        fid = f"file{self._uid}"
        self.session.files[fid] = content
        d = Document(file_id=fid, file_unique_id=f"u{fid}", file_name=file_name, mime_type=mime, file_size=len(content))
        await self.feed(Update(update_id=self._uid, message=self._message(document=d)))

    async def wait_ai(self, timeout=10):
        task = self.app.ai_tasks.get(USER_ID)
        if task:
            await asyncio.wait_for(task, timeout)


def make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for p, d in files.items():
            zf.writestr(p, d)
    return buf.getvalue()
