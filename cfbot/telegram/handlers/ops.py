"""Worker operations (replaces the old GitHub Actions screen):
deployments & versions + rollback, cron triggers, routes, custom domains, test request, metrics."""

from __future__ import annotations

import re
import time

import httpx
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ...cloudflare.client import CloudflareError
from ...i18n import t
from ..app import AppContext
from ..keyboards import back_menu, cancel_kb, ib, name_from_id, nid, register_names, rows
from ..states import OpsFlow
from ..utils import age, edit_or_send, esc
from .router_bridge import entry
from .workers import cf_err

router = Router(name="ops")
_CRON_FIELD = r"[\d\*/,\-A-Za-z?LW#]+"
CRON_RE = re.compile(rf"^{_CRON_FIELD}(\s+{_CRON_FIELD}){{4}}$")


def parse_crons(text: str) -> tuple[list[str], list[str]]:
    items = [c.strip() for c in re.split(r"[\n;]+", text or "") if c.strip()]
    if len(items) == 1 and items[0] in ("-", "none", "clear"):
        return [], []
    bad = [c for c in items if not CRON_RE.match(c)]
    return items, bad


# ------------------------------------------------------------------ deployments / versions / rollback
@router.callback_query(F.data.startswith("ops:deps:"))
async def cb_deps(cb: CallbackQuery, app: AppContext, lang: str):
    r = cb.data.split(":")[2]
    name = name_from_id(r)
    cf = await app.cf(cb.from_user.id)
    if not name or not cf:
        return
    try:
        deps = await cf.list_deployments(name)
        versions = await cf.list_versions(name, per_page=8)
    except CloudflareError as e:
        await edit_or_send(cb, cf_err(lang, e), back_menu(lang, f"wk:card:{r}"))
        return
    finally:
        await cf.aclose()
    active = {v.get("version_id") for v in (deps[0].get("versions") if deps else [])}
    dbody = "\n".join(t(lang, "dep_item", when=age(d.get("created_on")), source=esc(d.get("source", "")),
                        author=esc(d.get("author_email", "") or "—"),
                        versions=esc(", ".join(f"{v.get('version_id', '')[:8]}·{v.get('percentage')}%" for v in d.get("versions") or [])))
                      for d in deps[:6]) or t(lang, "none")
    vbody = "\n".join(t(lang, "ver_item", id=esc(v["id"][:8]), n=(v.get("metadata") or {}).get("number", "?"),
                        when=age((v.get("metadata") or {}).get("created_on")),
                        source=esc((v.get("metadata") or {}).get("source", "")),
                        active="🟢" if v["id"] in active else "⚪️",
                        msg=esc(((v.get("annotations") or {}).get("workers/message") or "")[:40]))
                      for v in versions) or t(lang, "none")
    register_names(v["id"] for v in versions)
    kb = rows(*[[ib(t(lang, "btn_rollback", id=v["id"][:8]), f"ops:rb:{r}:{nid(v['id'])}")] for v in versions if v["id"] not in active][:6],
              [ib(t(lang, "btn_refresh"), f"ops:deps:{r}")],
              [ib(t(lang, "btn_back"), f"wk:card:{r}"), ib(t(lang, "btn_menu"), "menu:home")])
    await edit_or_send(cb, t(lang, "deps_title", name=esc(name), deps=dbody, versions=vbody)[:4000], kb)


@router.callback_query(F.data.startswith("ops:rb:"))
async def cb_rollback_ask(cb: CallbackQuery, lang: str):
    _, _, r, h = cb.data.split(":")
    vid = name_from_id(h)
    if not vid:
        return
    await edit_or_send(cb, t(lang, "rollback_confirm", id=esc(vid[:8]), name=esc(name_from_id(r) or "")),
                       rows([ib(t(lang, "btn_yes"), f"ops:rbgo:{r}:{h}"), ib(t(lang, "btn_no"), f"ops:deps:{r}")]))


@router.callback_query(F.data.startswith("ops:rbgo:"))
async def cb_rollback(cb: CallbackQuery, app: AppContext, lang: str):
    _, _, r, h = cb.data.split(":")
    name, vid = name_from_id(r), name_from_id(h)
    cf = await app.cf(cb.from_user.id)
    if not name or not vid or not cf:
        return
    try:
        await cf.deploy_version(name, vid, message="rollback via Cloudflare Control Bot")
        await app.notifier.send(cb.from_user.id, t(lang, "rollback_done", id=esc(vid[:8]), name=esc(name)), kind="worker",
                                markup=back_menu(lang, f"ops:deps:{r}"))
    except CloudflareError as e:
        await app.notifier.send(cb.from_user.id, cf_err(lang, e), kind="error")
    finally:
        await cf.aclose()


# ------------------------------------------------------------------ cron triggers
@router.callback_query(F.data.startswith("ops:cron:"))
async def cb_cron(cb: CallbackQuery, state: FSMContext, app: AppContext, lang: str):
    r = cb.data.split(":")[2]
    name = name_from_id(r)
    cf = await app.cf(cb.from_user.id)
    if not name or not cf:
        return
    try:
        crons = [s.get("cron") for s in await cf.get_schedules(name)]
    except CloudflareError as e:
        await edit_or_send(cb, cf_err(lang, e), back_menu(lang, f"wk:card:{r}"))
        return
    finally:
        await cf.aclose()
    await state.set_state(OpsFlow.cron)
    await state.update_data(worker=name)
    await edit_or_send(cb, t(lang, "cron_title", name=esc(name), crons=esc("\n".join(crons) or "—")),
                       rows([ib(t(lang, "btn_cron_clear"), f"ops:cronclr:{r}")], [ib(t(lang, "btn_back"), f"wk:card:{r}")]))


async def _set_crons(event, app: AppContext, lang: str, name: str, crons: list[str]):
    tg_id = event.from_user.id
    cf = await app.cf(tg_id)
    if not cf:
        return
    try:
        res = await cf.set_schedules(name, crons)
        await app.notifier.send(tg_id, t(lang, "cron_saved", name=esc(name), crons=esc(", ".join(s.get("cron", "") for s in res) or "—")),
                                kind="worker", markup=back_menu(lang, f"wk:card:{nid(name)}"))
    except CloudflareError as e:
        await app.notifier.send(tg_id, cf_err(lang, e), kind="error")
    finally:
        await cf.aclose()


@router.message(OpsFlow.cron, F.text & ~F.text.startswith("/"))
async def got_cron(msg: Message, state: FSMContext, app: AppContext, lang: str):
    crons, bad = parse_crons(msg.text)
    if bad:
        await msg.answer(t(lang, "cron_bad", bad=esc(", ".join(bad))), parse_mode="HTML")
        return
    data = await state.get_data()
    await state.clear()
    await _set_crons(msg, app, lang, data["worker"], crons)


@router.callback_query(F.data.startswith("ops:cronclr:"))
async def cb_cron_clear(cb: CallbackQuery, state: FSMContext, app: AppContext, lang: str):
    name = name_from_id(cb.data.split(":")[2])
    await state.clear()
    if name:
        await _set_crons(cb, app, lang, name, [])


# ------------------------------------------------------------------ routes & custom domains
@router.callback_query(F.data.startswith("ops:routes:"))
async def cb_routes(cb: CallbackQuery, state: FSMContext, app: AppContext, lang: str):
    r = cb.data.split(":")[2]
    name = name_from_id(r)
    cf = await app.cf(cb.from_user.id)
    if not name or not cf:
        return
    await state.clear()
    try:
        routes = await cf.worker_routes(name)
        try:
            domains = await cf.list_domains(service=name)
        except CloudflareError:
            domains = []
        sub = await cf.account_subdomain()
    except CloudflareError as e:
        await edit_or_send(cb, cf_err(lang, e), back_menu(lang, f"wk:card:{r}"))
        return
    finally:
        await cf.aclose()
    for x in routes:
        nid(f"{x['zone_id']}|{x['id']}")
    for d in domains:
        nid(d["id"])
    rbody = "\n".join(f"🛣 <code>{esc(x['pattern'])}</code> ({esc(x['zone_name'])})" for x in routes) or t(lang, "none")
    dbody = "\n".join(f"🌐 <code>{esc(d['hostname'])}</code>" for d in domains) or t(lang, "none")
    kb = rows(*[[ib(f"✖️ {x['pattern'][:40]}", f"ops:rdel:{r}:{nid(x['zone_id'] + '|' + x['id'])}")] for x in routes[:8]],
              *[[ib(f"✖️ {d['hostname'][:40]}", f"ops:ddel:{r}:{nid(d['id'])}")] for d in domains[:8]],
              [ib(t(lang, "btn_route_add"), f"ops:radd:{r}"), ib(t(lang, "btn_domain_add"), f"ops:dadd:{r}")],
              [ib(t(lang, "btn_back"), f"wk:card:{r}"), ib(t(lang, "btn_menu"), "menu:home")])
    await edit_or_send(cb, t(lang, "routes_title", name=esc(name), wdev=esc(f"https://{name}.{sub}.workers.dev" if sub else "—"),
                             routes=rbody, domains=dbody)[:4000], kb)


@router.callback_query(F.data.startswith("ops:radd:"))
async def cb_route_add(cb: CallbackQuery, state: FSMContext, lang: str):
    await state.set_state(OpsFlow.route)
    await state.update_data(worker=name_from_id(cb.data.split(":")[2]))
    await edit_or_send(cb, t(lang, "route_ask"), cancel_kb(lang))


@router.callback_query(F.data.startswith("ops:dadd:"))
async def cb_domain_add(cb: CallbackQuery, state: FSMContext, lang: str):
    await state.set_state(OpsFlow.domain)
    await state.update_data(worker=name_from_id(cb.data.split(":")[2]))
    await edit_or_send(cb, t(lang, "domain_ask"), cancel_kb(lang))


async def _zone_for(cf, host: str) -> dict | None:
    host = host.split("/")[0].lstrip("*.").lower()
    zones = await cf.list_zones()
    best = None
    for z in zones:
        zn = z["name"].lower()
        if host == zn or host.endswith("." + zn):
            if not best or len(zn) > len(best["name"]):
                best = z
    return best


@router.message(OpsFlow.route, F.text & ~F.text.startswith("/"))
async def got_route(msg: Message, state: FSMContext, app: AppContext, lang: str):
    pattern = msg.text.strip()
    data = await state.get_data()
    await state.clear()
    name = data["worker"]
    cf = await app.cf(msg.from_user.id)
    if not cf:
        return
    try:
        z = await _zone_for(cf, pattern)
        if not z:
            await msg.answer(t(lang, "zone_not_found", host=esc(pattern)), parse_mode="HTML")
            return
        await cf.create_route(z["id"], pattern, name)
        await msg.answer(t(lang, "route_added", pattern=esc(pattern), zone=esc(z["name"])), parse_mode="HTML",
                         reply_markup=back_menu(lang, f"ops:routes:{nid(name)}"))
    except CloudflareError as e:
        await msg.answer(cf_err(lang, e), parse_mode="HTML")
    finally:
        await cf.aclose()


@router.message(OpsFlow.domain, F.text & ~F.text.startswith("/"))
async def got_domain(msg: Message, state: FSMContext, app: AppContext, lang: str):
    host = msg.text.strip().lower().removeprefix("https://").removeprefix("http://").split("/")[0]
    data = await state.get_data()
    await state.clear()
    name = data["worker"]
    cf = await app.cf(msg.from_user.id)
    if not cf:
        return
    try:
        z = await _zone_for(cf, host)
        if not z:
            await msg.answer(t(lang, "zone_not_found", host=esc(host)), parse_mode="HTML")
            return
        await cf.attach_domain(host, name, z["id"])
        await msg.answer(t(lang, "domain_added", host=esc(host)), parse_mode="HTML",
                         reply_markup=back_menu(lang, f"ops:routes:{nid(name)}"))
    except CloudflareError as e:
        await msg.answer(cf_err(lang, e), parse_mode="HTML")
    finally:
        await cf.aclose()


@router.callback_query(F.data.startswith("ops:rdel:"))
async def cb_route_del(cb: CallbackQuery, state: FSMContext, app: AppContext, lang: str):
    _, _, r, h = cb.data.split(":")
    ref = name_from_id(h)
    cf = await app.cf(cb.from_user.id)
    if not ref or not cf:
        return
    zone_id, route_id = ref.split("|", 1)
    try:
        await cf.delete_route(zone_id, route_id)
        await app.notifier.send(cb.from_user.id, t(lang, "route_deleted"), kind="worker")
    except CloudflareError as e:
        await app.notifier.send(cb.from_user.id, cf_err(lang, e), kind="error")
    finally:
        await cf.aclose()
    await cb_routes(cb.model_copy(update={"data": f"ops:routes:{r}"}), state, app, lang)


@router.callback_query(F.data.startswith("ops:ddel:"))
async def cb_domain_del(cb: CallbackQuery, state: FSMContext, app: AppContext, lang: str):
    _, _, r, h = cb.data.split(":")
    did = name_from_id(h)
    cf = await app.cf(cb.from_user.id)
    if not did or not cf:
        return
    try:
        await cf.detach_domain(did)
        await app.notifier.send(cb.from_user.id, t(lang, "domain_deleted"), kind="worker")
    except CloudflareError as e:
        await app.notifier.send(cb.from_user.id, cf_err(lang, e), kind="error")
    finally:
        await cf.aclose()
    await cb_routes(cb.model_copy(update={"data": f"ops:routes:{r}"}), state, app, lang)


# ------------------------------------------------------------------ test request
@router.callback_query(F.data.startswith("ops:test:"))
async def cb_test(cb: CallbackQuery, state: FSMContext, lang: str):
    await state.set_state(OpsFlow.test_path)
    await state.update_data(worker=name_from_id(cb.data.split(":")[2]))
    await edit_or_send(cb, t(lang, "test_ask"), rows([ib(t(lang, "btn_test_root"), "ops:testroot")], [ib(t(lang, "btn_cancel"), "flow:cancel")]))


async def _run_test(event, state: FSMContext, app: AppContext, lang: str, path: str):
    data = await state.get_data()
    await state.clear()
    name = data.get("worker")
    tg_id = event.from_user.id
    cf = await app.cf(tg_id)
    if not cf or not name:
        return
    try:
        sub = await cf.account_subdomain()
    finally:
        await cf.aclose()
    if not sub:
        await app.notifier.send(tg_id, t(lang, "test_no_subdomain"), kind="worker")
        return
    method, _, p = path.partition(" ") if path.split(" ")[0].upper() in ("GET", "POST", "PUT", "DELETE", "HEAD") else ("GET", "", path)
    p = p or "/"
    url = f"https://{name}.{sub}.workers.dev{p if p.startswith('/') else '/' + p}"
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as c:
            resp = await c.request(method.upper(), url)
        ms = int((time.time() - start) * 1000)
        body = resp.text[:1500]
        await app.notifier.send(tg_id, t(lang, "test_result", method=esc(method.upper()), url=esc(url), status=resp.status_code, ms=ms,
                                         ctype=esc(resp.headers.get("content-type", "")), ray=esc(resp.headers.get("cf-ray", "—")),
                                         body=esc(body)), kind="worker", markup=back_menu(lang, f"wk:card:{nid(name)}"))
    except httpx.HTTPError as e:
        await app.notifier.send(tg_id, t(lang, "test_fail", url=esc(url), error=esc(str(e)[:200])), kind="error")


@router.callback_query(OpsFlow.test_path, F.data == "ops:testroot")
async def cb_test_root(cb: CallbackQuery, state: FSMContext, app: AppContext, lang: str):
    await _run_test(cb, state, app, lang, "/")


@router.message(OpsFlow.test_path, F.text)  # paths start with "/" — /cancel & /menu are caught earlier by the menu router
async def got_test(msg: Message, state: FSMContext, app: AppContext, lang: str):
    await _run_test(msg, state, app, lang, msg.text.strip())


# ------------------------------------------------------------------ metrics
async def _metrics(event, app: AppContext, tg_id: int, lang: str, name: str | None, hours: int = 24):
    cf = await app.cf(tg_id)
    if not cf:
        await edit_or_send(event, t(lang, "need_token"))
        return
    try:
        m = await cf.worker_metrics(name, hours=hours)
    except CloudflareError as e:
        await edit_or_send(event, cf_err(lang, e) + "\n" + t(lang, "metrics_perm"), back_menu(lang, f"wk:card:{nid(name)}" if name else None))
        return
    finally:
        await cf.aclose()
    scripts = sorted(m["scripts"].items(), key=lambda kv: kv[1]["requests"], reverse=True)
    body = "\n".join(t(lang, "metrics_item", name=esc(sn), req=v["requests"], err=v["errors"], sub=v["subrequests"],
                       p50=round(v["cpu_p50"] / 1000, 2), p99=round(v["cpu_p99"] / 1000, 2),
                       rate=round(100 * v["errors"] / v["requests"], 2) if v["requests"] else 0)
                     for sn, v in scripts[:15]) or t(lang, "metrics_none")
    back = f"wk:card:{nid(name)}" if name else None
    prefix = f"ops:m:{nid(name)}" if name else "ops:metrics"
    kb = rows([ib("1h", f"{prefix}:1"), ib("24h", f"{prefix}:24"), ib("7d", f"{prefix}:168")],
              [ib(t(lang, "btn_back"), back)] if back else [], [ib(t(lang, "btn_menu"), "menu:home")])
    await edit_or_send(event, t(lang, "metrics_title", scope=esc(name or t(lang, "all_workers")), hours=hours, list=body)[:4000], kb)


@entry("ops:metrics")
async def entry_metrics(msg: Message, app: AppContext, lang: str, state: FSMContext):
    await _metrics(msg, app, msg.from_user.id, lang, None)


@router.message(Command("metrics", "analytics"))
async def cmd_metrics(msg: Message, app: AppContext, lang: str):
    parts = (msg.text or "").split(maxsplit=1)
    await _metrics(msg, app, msg.from_user.id, lang, parts[1].strip() if len(parts) == 2 else None)


@router.callback_query(F.data.startswith("ops:metrics"))
async def cb_metrics_all(cb: CallbackQuery, app: AppContext, lang: str):
    parts = cb.data.split(":")
    await _metrics(cb, app, cb.from_user.id, lang, None, int(parts[2]) if len(parts) > 2 else 24)


@router.callback_query(F.data.startswith("ops:m:"))
async def cb_metrics(cb: CallbackQuery, app: AppContext, lang: str):
    parts = cb.data.split(":")
    name = name_from_id(parts[2])
    if name:
        await _metrics(cb, app, cb.from_user.id, lang, name, int(parts[3]) if len(parts) > 3 else 24)
