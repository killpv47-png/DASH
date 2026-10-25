"""Workers: list, card, code view/download, bindings, settings, watch/unwatch, delete."""

from __future__ import annotations

import io
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from ...cloudflare.client import CloudflareError
from ...cloudflare.tokens import hint_for
from ...i18n import t
from ..app import AppContext
from ..keyboards import back_menu, cancel_kb, ib, name_from_id, nid, rows, worker_card_kb, worker_picker
from ..states import WorkerEdit
from ..utils import age, edit_or_send, esc, human_size
from .router_bridge import entry

router = Router(name="workers")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

BINDING_ICON = {"kv_namespace": "🗂", "d1": "🗄", "r2_bucket": "🪣", "queue": "📨", "plain_text": "📝", "secret_text": "🔐",
                "ai": "🧠", "service": "🔗", "durable_object_namespace": "🧱", "analytics_engine": "📈", "vectorize": "🧭",
                "hyperdrive": "🚀", "json": "📝", "assets": "🖼", "version_metadata": "🏷"}


def cf_err(lang: str, e: CloudflareError) -> str:
    h = hint_for(e.codes)
    return t(lang, "error_generic", error=esc(e.message)) + (f"\n💡 {esc(h)}" if h else "")


def binding_desc(b: dict) -> str:
    tp = b.get("type", "")
    extra = b.get("namespace_id") or b.get("id") or b.get("bucket_name") or b.get("queue_name") or b.get("service") or \
        b.get("class_name") or b.get("dataset") or b.get("index_name") or (b.get("text", "")[:40] if tp == "plain_text" else "")
    return f"{BINDING_ICON.get(tp, '•')} <code>{esc(b.get('name'))}</code> — {esc(tp)}" + (f" · <code>{esc(extra)}</code>" if extra else "")


async def list_workers(event, app: AppContext, tg_id: int, lang: str, page: int, refresh: bool = False):
    try:
        ws = await app.workers(tg_id, refresh=refresh)
    except CloudflareError as e:
        await edit_or_send(event, cf_err(lang, e), back_menu(lang))
        return
    if not await app.credential_for(tg_id):
        await edit_or_send(event, t(lang, "need_token"), back_menu(lang))
        return
    extra = [[ib(t(lang, "btn_new_worker"), "nw:start"), ib(t(lang, "btn_refresh"), "wk:refresh")]]
    if not ws:
        await edit_or_send(event, t(lang, "workers_empty"), rows(*extra, [ib(t(lang, "btn_menu"), "menu:home")]))
        return
    kb, pages = worker_picker(lang, ws, page, "wk:card", extra=extra)
    await edit_or_send(event, t(lang, "workers_title", n=len(ws), page=page + 1, pages=pages), kb)


@entry("wk:list:0")
async def entry_workers(msg: Message, app: AppContext, lang: str, state: FSMContext):
    await list_workers(msg, app, msg.from_user.id, lang, 0)


@router.message(Command("workers"))
async def cmd_workers(msg: Message, app: AppContext, lang: str):
    await list_workers(msg, app, msg.from_user.id, lang, 0, refresh=True)


@router.callback_query(F.data.startswith("wk:list:") | F.data.startswith("wk:pick:"))
async def cb_list(cb: CallbackQuery, app: AppContext, lang: str):
    await list_workers(cb, app, cb.from_user.id, lang, int(cb.data.split(":")[2]))


@router.callback_query(F.data == "wk:refresh")
async def cb_refresh(cb: CallbackQuery, app: AppContext, lang: str):
    await list_workers(cb, app, cb.from_user.id, lang, 0, refresh=True)


async def show_card(event, app: AppContext, tg_id: int, lang: str, name: str):
    cf = await app.cf(tg_id)
    if not cf:
        await edit_or_send(event, t(lang, "need_token"))
        return
    try:
        ws = {w["id"]: w for w in await app.workers(tg_id)}
        settings = await cf.get_worker_settings(name)
        sub = await cf.account_subdomain()
        try:
            wdev = (await cf.get_worker_subdomain(name)).get("enabled")
        except CloudflareError:
            wdev = None
        try:
            crons = [s.get("cron") for s in await cf.get_schedules(name)]
        except CloudflareError:
            crons = []
    except CloudflareError as e:
        await edit_or_send(event, cf_err(lang, e), back_menu(lang, "wk:list:0"))
        return
    finally:
        await cf.aclose()
    w = ws.get(name, {})
    bindings = settings.get("bindings") or []
    url = f"https://{name}.{sub}.workers.dev" if sub and wdev else "—"
    watched = any(x["worker"] == name for x in await app.db.list_watches(tg_id))
    text = t(lang, "worker_card", name=esc(name), url=esc(url), handlers=esc(", ".join(w.get("handlers") or []) or "—"),
             compat=esc(settings.get("compatibility_date") or w.get("compatibility_date") or "—"),
             flags=esc(", ".join(settings.get("compatibility_flags") or []) or "—"),
             modified=age(w.get("modified_on")), created=age(w.get("created_on")),
             usage=esc(settings.get("usage_model") or w.get("usage_model") or "standard"),
             crons=esc(", ".join(crons) or "—"), nb=len(bindings),
             bindings="\n".join(binding_desc(b) for b in bindings[:25]) or t(lang, "none"),
             logpush=t(lang, "yes" if settings.get("logpush") else "no"))
    await edit_or_send(event, text[:4000], worker_card_kb(lang, name, watched))


@router.callback_query(F.data.startswith("wk:card:"))
async def cb_card(cb: CallbackQuery, app: AppContext, lang: str):
    name = name_from_id(cb.data.split(":")[2])
    if name:
        await show_card(cb, app, cb.from_user.id, lang, name)


@router.message(Command("worker"))
async def cmd_worker(msg: Message, app: AppContext, lang: str):
    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await msg.answer("Usage: /worker &lt;name&gt;", parse_mode="HTML")
        return
    name = parts[1].strip()
    nid(name)
    await show_card(msg, app, msg.from_user.id, lang, name)


# ------------------------------------------------------------------ code
@router.callback_query(F.data.startswith("wk:code:"))
async def cb_code(cb: CallbackQuery, app: AppContext, lang: str):
    name = name_from_id(cb.data.split(":")[2])
    cf = await app.cf(cb.from_user.id)
    if not name or not cf:
        return
    try:
        modules = await cf.get_worker_content(name)
    except CloudflareError as e:
        await edit_or_send(cb, cf_err(lang, e), back_menu(lang, f"wk:card:{nid(name)}"))
        return
    finally:
        await cf.aclose()
    listing = "\n".join(f"📄 <code>{esc(k)}</code> — {human_size(len(v))}" for k, v in modules.items())
    main = next(iter(modules))
    preview = modules[main].decode("utf-8", errors="replace")[:2500]
    await edit_or_send(cb, t(lang, "worker_code", name=esc(name), files=listing, main=esc(main), code=esc(preview))[:4000],
                       back_menu(lang, f"wk:card:{nid(name)}"))
    # full download as ZIP (so the user can edit and re-deploy)
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in modules.items():
            z.writestr(k, v)
    try:
        await app.bot.send_document(cb.from_user.id, BufferedInputFile(buf.getvalue(), f"{name}.zip"),
                                    caption=t(lang, "worker_code_zip", name=esc(name)), parse_mode="HTML")
    except Exception:
        pass


# ------------------------------------------------------------------ bindings
@router.callback_query(F.data.startswith("wk:bind:"))
async def cb_bindings(cb: CallbackQuery, app: AppContext, lang: str):
    r = cb.data.split(":")[2]
    name = name_from_id(r)
    cf = await app.cf(cb.from_user.id)
    if not name or not cf:
        return
    try:
        bindings = (await cf.get_worker_settings(name)).get("bindings") or []
    except CloudflareError as e:
        await edit_or_send(cb, cf_err(lang, e), back_menu(lang, f"wk:card:{r}"))
        return
    finally:
        await cf.aclose()
    kb = rows(*[[ib(f"✖️ {b['name']}", f"wk:unbind:{r}:{b['name']}")] for b in bindings if b.get("type") != "secret_text"][:15],
              [ib(t(lang, "btn_bind_add"), f"st:bindto:{r}")],
              [ib(t(lang, "btn_back"), f"wk:card:{r}"), ib(t(lang, "btn_menu"), "menu:home")])
    await edit_or_send(cb, t(lang, "bindings_title", name=esc(name),
                             list="\n".join(binding_desc(b) for b in bindings) or t(lang, "none"))[:4000], kb)


@router.callback_query(F.data.startswith("wk:unbind:"))
async def cb_unbind(cb: CallbackQuery, app: AppContext, lang: str):
    _, _, r, bname = cb.data.split(":", 3)
    name = name_from_id(r)
    cf = await app.cf(cb.from_user.id)
    if not name or not cf:
        return
    try:
        await cf.delete_binding(name, bname)
        await app.notifier.send(cb.from_user.id, t(lang, "binding_removed", binding=esc(bname), name=esc(name)), kind="worker")
    except CloudflareError as e:
        await app.notifier.send(cb.from_user.id, cf_err(lang, e), kind="error")
    finally:
        await cf.aclose()
    await cb_bindings(cb.model_copy(update={"data": f"wk:bind:{r}"}), app, lang)


# ------------------------------------------------------------------ watch
@router.callback_query(F.data.startswith("wk:watch:"))
async def cb_watch(cb: CallbackQuery, app: AppContext, lang: str):
    name = name_from_id(cb.data.split(":")[2])
    if not name:
        return
    u = await app.db.get_user(cb.from_user.id)
    await app.db.add_watch(cb.from_user.id, name, u["cf_account_id"])
    await app.notifier.send(cb.from_user.id, t(lang, "watch_on", name=esc(name)), kind="watch")
    await show_card(cb, app, cb.from_user.id, lang, name)


@router.callback_query(F.data.startswith("wk:unwatch:"))
async def cb_unwatch(cb: CallbackQuery, app: AppContext, lang: str):
    name = name_from_id(cb.data.split(":")[2])
    if not name:
        return
    await app.db.remove_watch(cb.from_user.id, name)
    await app.notifier.send(cb.from_user.id, t(lang, "watch_off", name=esc(name)), kind="watch")
    await show_card(cb, app, cb.from_user.id, lang, name)


# ------------------------------------------------------------------ settings
def _edit_kb(lang: str, name: str):
    r = nid(name)
    return rows(
        [ib(t(lang, "btn_wdev_on"), f"wk:wdev:1:{r}"), ib(t(lang, "btn_wdev_off"), f"wk:wdev:0:{r}")],
        [ib(t(lang, "btn_logpush"), f"wk:logpush:{r}"), ib(t(lang, "btn_observability"), f"wk:obs:{r}")],
        [ib(t(lang, "btn_compat"), f"wk:compat:{r}"), ib(t(lang, "btn_nodecompat"), f"wk:node:{r}")],
        [ib(t(lang, "btn_back"), f"wk:card:{r}"), ib(t(lang, "btn_menu"), "menu:home")],
    )


@router.callback_query(F.data.startswith("wk:edit:"))
async def cb_edit(cb: CallbackQuery, lang: str):
    name = name_from_id(cb.data.split(":")[2])
    if name:
        await edit_or_send(cb, t(lang, "worker_edit_title", name=esc(name)), _edit_kb(lang, name))


async def _apply(cb: CallbackQuery, app: AppContext, lang: str, name: str, coro_factory, label: str):
    cf = await app.cf(cb.from_user.id)
    if not cf:
        return
    try:
        await coro_factory(cf)
        await app.notifier.send(cb.from_user.id, t(lang, "worker_updated", name=esc(name), what=esc(label)), kind="worker")
    except CloudflareError as e:
        await app.notifier.send(cb.from_user.id, cf_err(lang, e), kind="error")
    finally:
        await cf.aclose()
    await edit_or_send(cb, t(lang, "worker_edit_title", name=esc(name)), _edit_kb(lang, name))


@router.callback_query(F.data.startswith("wk:wdev:"))
async def cb_wdev(cb: CallbackQuery, app: AppContext, lang: str):
    _, _, on, r = cb.data.split(":")
    name = name_from_id(r)
    if name:
        await _apply(cb, app, lang, name, lambda cf: cf.set_worker_subdomain(name, on == "1"), f"workers.dev = {on == '1'}")


@router.callback_query(F.data.startswith("wk:logpush:"))
async def cb_logpush(cb: CallbackQuery, app: AppContext, lang: str):
    name = name_from_id(cb.data.split(":")[2])
    if not name:
        return

    async def go(cf):
        cur = await cf.get_script_settings(name)
        await cf.patch_script_settings(name, {"logpush": not cur.get("logpush")})
    await _apply(cb, app, lang, name, go, "logpush toggled")


@router.callback_query(F.data.startswith("wk:obs:"))
async def cb_obs(cb: CallbackQuery, app: AppContext, lang: str):
    name = name_from_id(cb.data.split(":")[2])
    if not name:
        return

    async def go(cf):
        cur = (await cf.get_script_settings(name)).get("observability") or {}
        await cf.patch_script_settings(name, {"observability": {"enabled": not cur.get("enabled"), "head_sampling_rate": 1}})
    await _apply(cb, app, lang, name, go, "observability (Workers Logs) toggled")


@router.callback_query(F.data.startswith("wk:node:"))
async def cb_node(cb: CallbackQuery, app: AppContext, lang: str):
    name = name_from_id(cb.data.split(":")[2])
    if not name:
        return

    async def go(cf):
        cur = await cf.get_worker_settings(name)
        flags = set(cur.get("compatibility_flags") or [])
        flags ^= {"nodejs_compat"}
        await cf.patch_worker_settings(name, {"compatibility_flags": sorted(flags)})
    await _apply(cb, app, lang, name, go, "nodejs_compat toggled")


@router.callback_query(F.data.startswith("wk:compat:"))
async def cb_compat(cb: CallbackQuery, state: FSMContext, lang: str):
    name = name_from_id(cb.data.split(":")[2])
    await state.set_state(WorkerEdit.compat)
    await state.update_data(worker=name)
    await edit_or_send(cb, t(lang, "ask_compat"), cancel_kb(lang))


@router.message(WorkerEdit.compat, F.text)
async def got_compat(msg: Message, state: FSMContext, app: AppContext, lang: str):
    d = msg.text.strip()
    if not DATE_RE.match(d):
        await msg.answer(t(lang, "compat_bad"), parse_mode="HTML")
        return
    data = await state.get_data()
    await state.clear()
    name = data["worker"]
    cf = await app.cf(msg.from_user.id)
    if not cf:
        return
    try:
        await cf.patch_worker_settings(name, {"compatibility_date": d})
        await msg.answer(t(lang, "worker_updated", name=esc(name), what=f"compatibility_date = {d}"), parse_mode="HTML",
                         reply_markup=_edit_kb(lang, name))
    except CloudflareError as e:
        await msg.answer(cf_err(lang, e), parse_mode="HTML", reply_markup=_edit_kb(lang, name))
    finally:
        await cf.aclose()


# ------------------------------------------------------------------ delete
@router.callback_query(F.data.startswith("wk:del:"))
async def cb_delete(cb: CallbackQuery, state: FSMContext, lang: str):
    name = name_from_id(cb.data.split(":")[2])
    if not name:
        return
    await state.set_state(WorkerEdit.delete_confirm)
    await state.update_data(worker=name)
    await edit_or_send(cb, t(lang, "worker_delete_confirm", name=esc(name)), cancel_kb(lang))


@router.message(WorkerEdit.delete_confirm, F.text)
async def got_delete(msg: Message, state: FSMContext, app: AppContext, lang: str):
    data = await state.get_data()
    await state.clear()
    name = data["worker"]
    if msg.text.strip() != name:
        await msg.answer(t(lang, "worker_delete_mismatch"), parse_mode="HTML")
        return
    cf = await app.cf(msg.from_user.id)
    if not cf:
        return
    try:
        await cf.delete_worker(name, force=True)
        app.worker_cache.pop(msg.from_user.id, None)
        await app.db.remove_watch(msg.from_user.id, name)
        await app.notifier.send(msg.from_user.id, t(lang, "worker_deleted", name=esc(name)), kind="worker",
                                markup=back_menu(lang, "wk:list:0"))
    except CloudflareError as e:
        await msg.answer(cf_err(lang, e), parse_mode="HTML")
    finally:
        await cf.aclose()
