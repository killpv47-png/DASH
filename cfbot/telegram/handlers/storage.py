"""Storage manager: KV namespaces (+keys), D1 databases (+SQL console), R2 buckets, Queues, zones;
bind any of them to a Worker."""

from __future__ import annotations

import json

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ...cloudflare.client import CloudflareError
from ...i18n import t
from ..app import AppContext
from ..keyboards import back_menu, cancel_kb, ib, name_from_id, nid, register_names, rows
from ..states import StorageFlow
from ..utils import edit_or_send, esc
from .router_bridge import entry
from .workers import cf_err

router = Router(name="storage")
KINDS = {"kv": "🗂 KV", "d1": "🗄 D1", "r2": "🪣 R2", "q": "📨 Queues"}
BIND_TYPE = {"kv": "kv_namespace", "d1": "d1", "r2": "r2_bucket", "q": "queue"}


def home_kb(lang: str):
    return rows([ib(KINDS["kv"], "st:ls:kv"), ib(KINDS["d1"], "st:ls:d1")],
                [ib(KINDS["r2"], "st:ls:r2"), ib(KINDS["q"], "st:ls:q")],
                [ib(t(lang, "btn_zones"), "st:zones")], [ib(t(lang, "btn_menu"), "menu:home")])


@entry("st:home")
async def entry_st(msg: Message, app: AppContext, lang: str, state: FSMContext):
    await edit_or_send(msg, t(lang, "st_home"), home_kb(lang))


@router.message(Command("storage"))
async def cmd_storage(msg: Message, state: FSMContext, lang: str):
    await state.clear()
    await edit_or_send(msg, t(lang, "st_home"), home_kb(lang))


@router.callback_query(F.data == "st:home")
async def cb_home(cb: CallbackQuery, state: FSMContext, lang: str):
    await state.clear()
    await edit_or_send(cb, t(lang, "st_home"), home_kb(lang))


async def _list(cf, kind: str) -> list[tuple[str, str]]:
    """[(label, ref)] — ref is the id used by the API (KV id, D1 uuid, bucket name, queue id|name)."""
    if kind == "kv":
        return [(n["title"], n["id"]) for n in await cf.list_kv()]
    if kind == "d1":
        return [(f"{d['name']} ({d.get('num_tables', '?')} tables)", d["uuid"]) for d in await cf.list_d1()]
    if kind == "r2":
        return [(b["name"], b["name"]) for b in await cf.list_r2()]
    return [(q["queue_name"], f"{q['queue_id']}|{q['queue_name']}") for q in await cf.list_queues()]


@router.callback_query(F.data.startswith("st:ls:"))
async def cb_list(cb: CallbackQuery, state: FSMContext, app: AppContext, lang: str):
    kind = cb.data.split(":")[2]
    await state.clear()
    cf = await app.cf(cb.from_user.id)
    if not cf:
        return
    try:
        items = await _list(cf, kind)
    except CloudflareError as e:
        await edit_or_send(cb, cf_err(lang, e), back_menu(lang, "st:home"))
        return
    finally:
        await cf.aclose()
    register_names(ref for _, ref in items)
    kb = rows(*[[ib(label[:50], f"st:o:{kind}:{nid(ref)}")] for label, ref in items[:25]],
              [ib(t(lang, "btn_st_create"), f"st:new:{kind}")], [ib(t(lang, "btn_back"), "st:home")])
    await edit_or_send(cb, t(lang, "st_list", kind=KINDS[kind], n=len(items)), kb)


# ------------------------------------------------------------------ create
@router.callback_query(F.data.startswith("st:new:"))
async def cb_new(cb: CallbackQuery, state: FSMContext, lang: str):
    kind = cb.data.split(":")[2]
    await state.set_state(StorageFlow.create_name)
    await state.update_data(kind=kind)
    await edit_or_send(cb, t(lang, "st_ask_name", kind=KINDS[kind]), cancel_kb(lang))


@router.message(StorageFlow.create_name, F.text & ~F.text.startswith("/"))
async def got_name(msg: Message, state: FSMContext, app: AppContext, lang: str):
    data = await state.get_data()
    await state.clear()
    kind, name = data["kind"], msg.text.strip()
    if kind == "__bind__":
        import re
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            await state.set_state(StorageFlow.create_name)
            await state.update_data(kind="__bind__")
            await msg.answer(t(lang, "sec_name_bad"), parse_mode="HTML")
            return
        await do_bind(msg, app, lang, name)
        return
    cf = await app.cf(msg.from_user.id)
    if not cf:
        return
    try:
        if kind == "kv":
            r = await cf.create_kv(name)
            ref = r["id"]
        elif kind == "d1":
            r = await cf.create_d1(name)
            ref = r["uuid"]
        elif kind == "r2":
            await cf.create_r2(name.lower())
            ref = name.lower()
        else:
            r = await cf.create_queue(name.lower())
            ref = f"{r.get('queue_id', '')}|{r.get('queue_name', name.lower())}"
        await app.notifier.send(msg.chat.id, t(lang, "st_created", kind=KINDS[kind], name=esc(name), id=esc(ref.split("|")[0])),
                                kind="storage", markup=rows([ib(t(lang, "btn_open"), f"st:o:{kind}:{nid(ref)}")],
                                                            [ib(t(lang, "btn_back"), f"st:ls:{kind}")]))
    except CloudflareError as e:
        await msg.answer(cf_err(lang, e), parse_mode="HTML")
    finally:
        await cf.aclose()


# ------------------------------------------------------------------ open one resource
@router.callback_query(F.data.startswith("st:o:"))
async def cb_open(cb: CallbackQuery, state: FSMContext, app: AppContext, lang: str):
    _, _, kind, h = cb.data.split(":")
    ref = name_from_id(h)
    if not ref:
        return
    await state.clear()
    btns = []
    detail = ""
    cf = await app.cf(cb.from_user.id)
    if not cf:
        return
    try:
        if kind == "kv":
            keys = await cf.kv_keys(ref, limit=30)
            detail = "\n".join(f"🔑 <code>{esc(k['name'])}</code>" for k in keys) or t(lang, "none")
            btns += [[ib(t(lang, "btn_kv_get"), f"st:kvget:{h}"), ib(t(lang, "btn_kv_put"), f"st:kvput:{h}")]]
        elif kind == "d1":
            tables = await cf.d1_query(ref, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '\\_cf\\_%' ESCAPE '\\' ORDER BY name")
            rows_ = (tables[0].get("results") if tables else []) or []
            detail = "\n".join(f"📋 <code>{esc(r['name'])}</code>" for r in rows_) or t(lang, "none")
            btns += [[ib(t(lang, "btn_d1_sql"), f"st:sql:{h}")]]
        elif kind == "q":
            detail = f"id <code>{esc(ref.split('|')[0])}</code>"
    except CloudflareError as e:
        detail = cf_err(lang, e)
    finally:
        await cf.aclose()
    label = ref.split("|")[-1] if kind == "q" else ref
    btns += [[ib(t(lang, "btn_bind_worker"), f"st:bind:{kind}:{h}")],
             [ib(t(lang, "btn_st_delete"), f"st:del:{kind}:{h}")], [ib(t(lang, "btn_back"), f"st:ls:{kind}")]]
    await edit_or_send(cb, t(lang, "st_item", kind=KINDS[kind], ref=esc(label), detail=detail)[:4000], rows(*btns))


# ------------------------------------------------------------------ KV keys
@router.callback_query(F.data.startswith("st:kvget:"))
async def cb_kvget(cb: CallbackQuery, state: FSMContext, lang: str):
    await state.set_state(StorageFlow.kv_key)
    await state.update_data(ns=name_from_id(cb.data.split(":")[2]), h=cb.data.split(":")[2])
    await edit_or_send(cb, t(lang, "kv_ask_key"), cancel_kb(lang))


@router.message(StorageFlow.kv_key, F.text)
async def got_kv_key(msg: Message, state: FSMContext, app: AppContext, lang: str):
    data = await state.get_data()
    await state.clear()
    cf = await app.cf(msg.from_user.id)
    if not cf:
        return
    try:
        v = await cf.kv_get(data["ns"], msg.text.strip())
        await msg.answer(t(lang, "kv_value", key=esc(msg.text.strip()), value=esc(v if v is not None else "∅ (not found)")[:3500]),
                         parse_mode="HTML", reply_markup=back_menu(lang, f"st:o:kv:{data['h']}"))
    except CloudflareError as e:
        await msg.answer(cf_err(lang, e), parse_mode="HTML")
    finally:
        await cf.aclose()


@router.callback_query(F.data.startswith("st:kvput:"))
async def cb_kvput(cb: CallbackQuery, state: FSMContext, lang: str):
    await state.set_state(StorageFlow.kv_put_key)
    await state.update_data(ns=name_from_id(cb.data.split(":")[2]), h=cb.data.split(":")[2])
    await edit_or_send(cb, t(lang, "kv_ask_key"), cancel_kb(lang))


@router.message(StorageFlow.kv_put_key, F.text)
async def got_kvput_key(msg: Message, state: FSMContext, lang: str):
    await state.update_data(key=msg.text.strip())
    await state.set_state(StorageFlow.kv_put_value)
    await msg.answer(t(lang, "kv_ask_value"), parse_mode="HTML", reply_markup=cancel_kb(lang))


@router.message(StorageFlow.kv_put_value, F.text)
async def got_kvput_value(msg: Message, state: FSMContext, app: AppContext, lang: str):
    data = await state.get_data()
    await state.clear()
    cf = await app.cf(msg.from_user.id)
    if not cf:
        return
    try:
        await cf.kv_put(data["ns"], data["key"], msg.text)
        await msg.answer(t(lang, "kv_saved", key=esc(data["key"])), parse_mode="HTML", reply_markup=back_menu(lang, f"st:o:kv:{data['h']}"))
    except CloudflareError as e:
        await msg.answer(cf_err(lang, e), parse_mode="HTML")
    finally:
        await cf.aclose()


# ------------------------------------------------------------------ D1 SQL console
@router.callback_query(F.data.startswith("st:sql:"))
async def cb_sql(cb: CallbackQuery, state: FSMContext, lang: str):
    await state.set_state(StorageFlow.d1_sql)
    await state.update_data(db=name_from_id(cb.data.split(":")[2]), h=cb.data.split(":")[2])
    await edit_or_send(cb, t(lang, "d1_ask_sql"), cancel_kb(lang))


@router.message(StorageFlow.d1_sql, F.text)
async def got_sql(msg: Message, state: FSMContext, app: AppContext, lang: str):
    data = await state.get_data()
    sql = msg.text.strip()
    cf = await app.cf(msg.from_user.id)
    if not cf:
        return
    try:
        res = await cf.d1_query(data["db"], sql)
        out = []
        for r in res or []:
            meta = r.get("meta") or {}
            out.append(json.dumps(r.get("results") or [], ensure_ascii=False, indent=1)[:2500])
            out.append(f"rows_read={meta.get('rows_read')} rows_written={meta.get('rows_written')} changes={meta.get('changes')} "
                       f"duration={meta.get('duration')}ms")
        await msg.answer(t(lang, "d1_result", sql=esc(sql[:200]), out=esc("\n".join(out))[:3600]), parse_mode="HTML",
                         reply_markup=rows([ib(t(lang, "btn_d1_more"), f"st:sql:{data['h']}")], [ib(t(lang, "btn_back"), f"st:o:d1:{data['h']}")]))
    except CloudflareError as e:
        await msg.answer(cf_err(lang, e), parse_mode="HTML")
    finally:
        await cf.aclose()
    await state.clear()


# ------------------------------------------------------------------ delete
@router.callback_query(F.data.startswith("st:del:"))
async def cb_del(cb: CallbackQuery, state: FSMContext, lang: str):
    _, _, kind, h = cb.data.split(":")
    ref = name_from_id(h) or ""
    label = ref.split("|")[-1]
    await state.set_state(StorageFlow.delete_confirm)
    await state.update_data(kind=kind, ref=ref, label=label)
    await edit_or_send(cb, t(lang, "st_delete_confirm", kind=KINDS[kind], name=esc(label)), cancel_kb(lang))


@router.message(StorageFlow.delete_confirm, F.text)
async def got_del(msg: Message, state: FSMContext, app: AppContext, lang: str):
    data = await state.get_data()
    await state.clear()
    if msg.text.strip() != data["label"]:
        await msg.answer(t(lang, "worker_delete_mismatch"), parse_mode="HTML")
        return
    cf = await app.cf(msg.from_user.id)
    if not cf:
        return
    kind, ref = data["kind"], data["ref"]
    try:
        if kind == "kv":
            await cf.delete_kv(ref)
        elif kind == "d1":
            await cf.delete_d1(ref)
        elif kind == "r2":
            await cf.delete_r2(ref)
        else:
            await cf.delete_queue(ref.split("|")[0])
        await msg.answer(t(lang, "st_deleted", name=esc(data["label"])), parse_mode="HTML", reply_markup=back_menu(lang, f"st:ls:{kind}"))
    except CloudflareError as e:
        await msg.answer(cf_err(lang, e), parse_mode="HTML")
    finally:
        await cf.aclose()


# ------------------------------------------------------------------ bind to worker
@router.callback_query(F.data.startswith("st:bind:"))
async def cb_bind(cb: CallbackQuery, app: AppContext, lang: str):
    _, _, kind, h = cb.data.split(":")
    ws = await app.workers(cb.from_user.id)
    register_names(w["id"] for w in ws)
    kb = rows(*[[ib(f"⚡ {w['id']}", f"st:bw:{kind}:{h}:{nid(w['id'])}")] for w in ws[:20]], [ib(t(lang, "btn_back"), f"st:o:{kind}:{h}")])
    await edit_or_send(cb, t(lang, "st_pick_worker"), kb)


@router.callback_query(F.data.startswith("st:bindto:"))
async def cb_bindto(cb: CallbackQuery, lang: str):
    """From a Worker → pick resource type, then the resource."""
    r = cb.data.split(":")[2]
    kb = rows(*[[ib(KINDS[k], f"st:bt:{r}:{k}")] for k in KINDS], [ib(t(lang, "btn_back"), f"wk:bind:{r}")])
    await edit_or_send(cb, t(lang, "st_pick_kind"), kb)


@router.callback_query(F.data.startswith("st:bt:"))
async def cb_bindto_kind(cb: CallbackQuery, app: AppContext, lang: str):
    _, _, r, kind = cb.data.split(":")
    cf = await app.cf(cb.from_user.id)
    if not cf:
        return
    try:
        items = await _list(cf, kind)
    except CloudflareError as e:
        await edit_or_send(cb, cf_err(lang, e), back_menu(lang, f"wk:bind:{r}"))
        return
    finally:
        await cf.aclose()
    register_names(ref for _, ref in items)
    kb = rows(*[[ib(label[:50], f"st:bw:{kind}:{nid(ref)}:{r}")] for label, ref in items[:20]],
              [ib(t(lang, "btn_st_create"), f"st:new:{kind}")], [ib(t(lang, "btn_back"), f"st:bindto:{r}")])
    await edit_or_send(cb, t(lang, "st_list", kind=KINDS[kind], n=len(items)), kb)


_PENDING_BIND: dict[int, dict] = {}


@router.callback_query(F.data.startswith("st:bw:"))
async def cb_bind_worker(cb: CallbackQuery, state: FSMContext, lang: str):
    _, _, kind, h, r = cb.data.split(":")
    _PENDING_BIND[cb.from_user.id] = {"kind": kind, "ref": name_from_id(h), "worker": name_from_id(r)}
    await state.set_state(StorageFlow.create_name)
    await state.update_data(kind="__bind__")
    await edit_or_send(cb, t(lang, "st_ask_binding"), cancel_kb(lang))


async def do_bind(msg: Message, app: AppContext, lang: str, binding_name: str):
    pb = _PENDING_BIND.pop(msg.from_user.id, None)
    if not pb or not pb["ref"] or not pb["worker"]:
        return
    kind, ref = pb["kind"], pb["ref"]
    b = {"type": BIND_TYPE[kind], "name": binding_name}
    if kind == "kv":
        b["namespace_id"] = ref
    elif kind == "d1":
        b["id"] = ref
    elif kind == "r2":
        b["bucket_name"] = ref
    else:
        b["queue_name"] = ref.split("|")[-1]
    cf = await app.cf(msg.from_user.id)
    if not cf:
        return
    try:
        await cf.add_binding(pb["worker"], b)
        await msg.answer(t(lang, "st_bound", binding=esc(binding_name), worker=esc(pb["worker"])), parse_mode="HTML",
                         reply_markup=back_menu(lang, f"wk:bind:{nid(pb['worker'])}"))
    except CloudflareError as e:
        await msg.answer(cf_err(lang, e), parse_mode="HTML")
    finally:
        await cf.aclose()


# ------------------------------------------------------------------ zones
@router.callback_query(F.data == "st:zones")
async def cb_zones(cb: CallbackQuery, app: AppContext, lang: str):
    cf = await app.cf(cb.from_user.id)
    if not cf:
        return
    try:
        zones = await cf.list_zones()
    except CloudflareError as e:
        await edit_or_send(cb, cf_err(lang, e), back_menu(lang, "st:home"))
        return
    finally:
        await cf.aclose()
    body = "\n".join(f"🌐 <code>{esc(z['name'])}</code> — {esc(z.get('status', ''))} · {esc((z.get('plan') or {}).get('name', ''))}" for z in zones[:40]) or t(lang, "none")
    await edit_or_send(cb, t(lang, "zones_title", n=len(zones), list=body)[:4000], back_menu(lang, "st:home"))
