"""Worker secrets & plain-text variables: list / create / update / delete / detect-from-code."""

from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ...cloudflare.analyzer import analyze_sources
from ...cloudflare.client import CloudflareError
from ...i18n import t
from ..app import AppContext
from ..keyboards import back_menu, cancel_kb, ib, name_from_id, nid, rows, worker_picker
from ..states import SecretFlow
from ..utils import edit_or_send, esc, safe_delete
from .router_bridge import entry
from .workers import cf_err

router = Router(name="secrets")
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,99}$")


async def pick_worker(event, app: AppContext, tg_id: int, lang: str, page: int, state: FSMContext):
    await state.clear()
    try:
        ws = await app.workers(tg_id)
    except CloudflareError as e:
        await edit_or_send(event, cf_err(lang, e), back_menu(lang))
        return
    if not ws:
        await edit_or_send(event, t(lang, "workers_empty"), back_menu(lang))
        return
    kb, _ = worker_picker(lang, ws, page, "sec:w")
    await edit_or_send(event, t(lang, "sec_pick"), kb)


@entry("sec:pick:0")
async def entry_sec(msg: Message, app: AppContext, lang: str, state: FSMContext):
    await pick_worker(msg, app, msg.from_user.id, lang, 0, state)


@router.message(Command("secrets"))
async def cmd_secrets(msg: Message, state: FSMContext, app: AppContext, lang: str):
    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) == 2:
        nid(parts[1].strip())
        await show_secrets(msg, app, msg.from_user.id, lang, parts[1].strip())
    else:
        await pick_worker(msg, app, msg.from_user.id, lang, 0, state)


@router.callback_query(F.data.startswith("sec:pick:"))
async def cb_pick(cb: CallbackQuery, state: FSMContext, app: AppContext, lang: str):
    await pick_worker(cb, app, cb.from_user.id, lang, int(cb.data.split(":")[2]), state)


@router.callback_query(F.data.startswith("sec:w:"))
async def cb_worker(cb: CallbackQuery, app: AppContext, lang: str):
    name = name_from_id(cb.data.split(":")[2])
    if name:
        await show_secrets(cb, app, cb.from_user.id, lang, name)


async def show_secrets(event, app: AppContext, tg_id: int, lang: str, name: str):
    cf = await app.cf(tg_id)
    if not cf:
        await edit_or_send(event, t(lang, "need_token"))
        return
    try:
        secrets = await cf.list_secrets(name)
    except CloudflareError as e:
        await edit_or_send(event, cf_err(lang, e), back_menu(lang, f"wk:card:{nid(name)}"))
        return
    finally:
        await cf.aclose()
    r = nid(name)
    body = "\n".join(t(lang, "sec_item", name=esc(s["name"])) for s in secrets) or t(lang, "sec_none")
    kb = rows(*[[ib(f"🔐 {s['name']}", f"sec:one:{r}:{s['name']}")] for s in secrets[:20]],
              [ib(t(lang, "btn_sec_add"), f"sec:add:{r}"), ib(t(lang, "btn_sec_scan"), f"sec:scan:{r}")],
              [ib(t(lang, "btn_sec_vars"), f"sec:vars:{r}")],
              [ib(t(lang, "btn_back"), f"wk:card:{r}"), ib(t(lang, "btn_menu"), "menu:home")])
    await edit_or_send(event, t(lang, "sec_title", name=esc(name), n=len(secrets), list=body), kb)


@router.callback_query(F.data.startswith("sec:one:"))
async def cb_one(cb: CallbackQuery, lang: str):
    _, _, r, key = cb.data.split(":", 3)
    name = name_from_id(r)
    kb = rows([ib(t(lang, "btn_sec_update"), f"sec:new:{r}:{key}"), ib(t(lang, "btn_sec_delete"), f"sec:del:{r}:{key}")],
              [ib(t(lang, "btn_back"), f"sec:w:{r}")])
    await edit_or_send(cb, t(lang, "sec_actions", key=esc(key), name=esc(name)), kb)


@router.callback_query(F.data.startswith("sec:add:"))
async def cb_add(cb: CallbackQuery, state: FSMContext, lang: str):
    await state.set_state(SecretFlow.name)
    await state.update_data(worker=name_from_id(cb.data.split(":")[2]))
    await edit_or_send(cb, t(lang, "sec_ask_name"), cancel_kb(lang))


@router.message(SecretFlow.name, F.text)
async def got_name(msg: Message, state: FSMContext, lang: str):
    key = msg.text.strip()
    if not NAME_RE.match(key):
        await msg.answer(t(lang, "sec_name_bad"), parse_mode="HTML")
        return
    await state.update_data(key=key)
    await state.set_state(SecretFlow.value)
    await msg.answer(t(lang, "sec_ask_value", key=esc(key)), parse_mode="HTML", reply_markup=cancel_kb(lang))


@router.callback_query(F.data.startswith("sec:new:"))
async def cb_new_named(cb: CallbackQuery, state: FSMContext, lang: str):
    _, _, r, key = cb.data.split(":", 3)
    await state.set_state(SecretFlow.value)
    await state.update_data(worker=name_from_id(r), key=key)
    await edit_or_send(cb, t(lang, "sec_ask_value", key=esc(key)), cancel_kb(lang))


@router.message(SecretFlow.value, F.text)
async def got_value(msg: Message, state: FSMContext, app: AppContext, lang: str):
    value = msg.text
    await safe_delete(msg)
    data = await state.get_data()
    await state.clear()
    name, key = data["worker"], data["key"]
    cf = await app.cf(msg.from_user.id)
    if not cf:
        return
    try:
        await cf.put_secret(name, key, value)
        await app.notifier.send(msg.chat.id, t(lang, "sec_saved", key=esc(key), name=esc(name)), kind="secrets",
                                markup=back_menu(lang, f"sec:w:{nid(name)}"))
    except CloudflareError as e:
        await app.notifier.send(msg.chat.id, cf_err(lang, e), kind="error")
    finally:
        await cf.aclose()


@router.callback_query(F.data.startswith("sec:del:"))
async def cb_del(cb: CallbackQuery, app: AppContext, lang: str):
    _, _, r, key = cb.data.split(":", 3)
    name = name_from_id(r)
    cf = await app.cf(cb.from_user.id)
    if not name or not cf:
        return
    try:
        await cf.delete_secret(name, key)
        await app.notifier.send(cb.from_user.id, t(lang, "sec_deleted", key=esc(key)), kind="secrets")
    except CloudflareError as e:
        await app.notifier.send(cb.from_user.id, cf_err(lang, e), kind="error")
    finally:
        await cf.aclose()
    await show_secrets(cb, app, cb.from_user.id, lang, name)


@router.callback_query(F.data.startswith("sec:scan:"))
async def cb_scan(cb: CallbackQuery, app: AppContext, lang: str):
    """Download the deployed code, find env.X used as var/secret, compare with what is bound."""
    r = cb.data.split(":")[2]
    name = name_from_id(r)
    cf = await app.cf(cb.from_user.id)
    if not name or not cf:
        return
    try:
        modules = await cf.get_worker_content(name)
        bound = {b["name"] for b in (await cf.get_worker_settings(name)).get("bindings") or []}
    except CloudflareError as e:
        await edit_or_send(cb, cf_err(lang, e), back_menu(lang, f"sec:w:{r}"))
        return
    finally:
        await cf.aclose()
    texts = {k: v.decode("utf-8", errors="replace") for k, v in modules.items() if k.endswith((".js", ".mjs", ".cjs", ".py"))}
    if not texts:
        await edit_or_send(cb, t(lang, "sec_detect_none"), back_menu(lang, f"sec:w:{r}"))
        return
    a = analyze_sources(texts, next(iter(texts)))
    needed = [b for b in a.bindings]
    missing = [b for b in needed if b.name not in bound]
    kb = rows(*[[ib(f"{'🔐' if b.kind == 'secret' else '📝' if b.kind == 'var' else '🧩'} {b.name}",
                    f"sec:new:{r}:{b.name}" if b.kind in ("secret", "var") else f"st:bindto:{r}")] for b in missing[:12]],
              [ib(t(lang, "btn_back"), f"sec:w:{r}")])
    await edit_or_send(cb, t(lang, "sec_detect_result",
                             all=", ".join(f"<code>{esc(b.name)}</code>({esc(b.kind)})" for b in needed) or "—",
                             missing=", ".join(esc(b.name) for b in missing) or "—"), kb)


# ------------------------------------------------------------- variables (plain_text bindings)
@router.callback_query(F.data.startswith("sec:vars:"))
async def cb_vars(cb: CallbackQuery, app: AppContext, lang: str):
    r = cb.data.split(":")[2]
    name = name_from_id(r)
    cf = await app.cf(cb.from_user.id)
    if not name or not cf:
        return
    try:
        variables = [b for b in (await cf.get_worker_settings(name)).get("bindings") or [] if b.get("type") in ("plain_text", "json")]
    except CloudflareError as e:
        await edit_or_send(cb, cf_err(lang, e), back_menu(lang, f"sec:w:{r}"))
        return
    finally:
        await cf.aclose()
    body = "\n".join(t(lang, "vars_item", key=esc(v["name"]), value=esc(str(v.get("text", v.get("json", ""))))[:60]) for v in variables) or t(lang, "none")
    kb = rows(*[[ib(f"✖️ {v['name']}", f"wk:unbind:{r}:{v['name']}")] for v in variables[:10]],
              [ib(t(lang, "btn_var_add"), f"sec:varadd:{r}")], [ib(t(lang, "btn_back"), f"sec:w:{r}")])
    await edit_or_send(cb, t(lang, "vars_title", name=esc(name), list=body), kb)


@router.callback_query(F.data.startswith("sec:varadd:"))
async def cb_varadd(cb: CallbackQuery, state: FSMContext, lang: str):
    await state.set_state(SecretFlow.var_name)
    await state.update_data(worker=name_from_id(cb.data.split(":")[2]))
    await edit_or_send(cb, t(lang, "var_ask_name"), cancel_kb(lang))


@router.message(SecretFlow.var_name, F.text)
async def got_var_name(msg: Message, state: FSMContext, lang: str):
    key = msg.text.strip()
    if not NAME_RE.match(key):
        await msg.answer(t(lang, "sec_name_bad"), parse_mode="HTML")
        return
    await state.update_data(key=key)
    await state.set_state(SecretFlow.var_value)
    await msg.answer(t(lang, "var_ask_value", key=esc(key)), parse_mode="HTML", reply_markup=cancel_kb(lang))


@router.message(SecretFlow.var_value, F.text)
async def got_var_value(msg: Message, state: FSMContext, app: AppContext, lang: str):
    data = await state.get_data()
    await state.clear()
    cf = await app.cf(msg.from_user.id)
    if not cf:
        return
    try:
        await cf.set_var(data["worker"], data["key"], msg.text.strip())
        await app.notifier.send(msg.chat.id, t(lang, "var_saved", key=esc(data["key"])), kind="secrets",
                                markup=back_menu(lang, f"sec:vars:{nid(data['worker'])}"))
    except CloudflareError as e:
        await app.notifier.send(msg.chat.id, cf_err(lang, e), kind="error")
    finally:
        await cf.aclose()
