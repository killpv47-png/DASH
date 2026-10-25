"""New Worker wizard: name → template (or own code) → analysis + resource plan → deploy.

Replaces the old "new repository" wizard. Templates are real, deployable Workers;
the resource plan (KV / D1 / R2 creation, vars, secrets, crons) is shared with the
deploy flow (handlers/deploy.py) so creation and configuration are automatic.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ...cloudflare.bundle import from_code
from ...cloudflare.client import SCRIPT_NAME_RE, CloudflareError
from ...cloudflare.templates import TEMPLATES
from ...i18n import t
from ..app import AppContext
from ..keyboards import cancel_kb, ib, rows
from ..states import Deploy, NewWorker
from ..utils import edit_or_send, esc
from .deploy import analyze_and_plan, ask_code
from .router_bridge import entry

router = Router(name="newworker")


async def start(event, app: AppContext, lang: str, state: FSMContext):
    await state.clear()
    await state.set_state(NewWorker.name)
    await edit_or_send(event, t(lang, "nw_name"), cancel_kb(lang))


@entry("nw:start")
async def entry_nw(msg: Message, app: AppContext, lang: str, state: FSMContext):
    await start(msg, app, lang, state)


@router.message(Command("newworker", "new"))
async def cmd_new(msg: Message, state: FSMContext, app: AppContext, lang: str):
    await start(msg, app, lang, state)


@router.callback_query(F.data == "nw:start")
async def cb_start(cb: CallbackQuery, state: FSMContext, app: AppContext, lang: str):
    await start(cb, app, lang, state)


@router.message(NewWorker.name, F.text & ~F.text.startswith("/"))
async def got_name(msg: Message, state: FSMContext, app: AppContext, lang: str):
    name = msg.text.strip().lower()
    if not SCRIPT_NAME_RE.match(name):
        await msg.answer(t(lang, "worker_name_bad"), parse_mode="HTML")
        return
    try:
        existing = {w["id"] for w in await app.workers(msg.from_user.id, refresh=True)}
    except CloudflareError:
        existing = set()
    if name in existing:
        await msg.answer(t(lang, "nw_exists", name=esc(name)), parse_mode="HTML")
        return
    await state.update_data(worker=name)
    await state.set_state(NewWorker.template)
    kb = rows(*[[ib(v["title"], f"nw:tpl:{k}")] for k, v in TEMPLATES.items()],
              [ib(t(lang, "btn_nw_own"), "nw:own")], [ib(t(lang, "btn_cancel"), "flow:cancel")])
    await msg.answer(t(lang, "nw_template", name=esc(name)), reply_markup=kb, parse_mode="HTML")


@router.callback_query(NewWorker.template, F.data == "nw:own")
async def cb_own(cb: CallbackQuery, state: FSMContext, lang: str):
    data = await state.get_data()
    await ask_code(cb, state, lang, data["worker"])


@router.callback_query(NewWorker.template, F.data.startswith("nw:tpl:"))
async def cb_tpl(cb: CallbackQuery, state: FSMContext, app: AppContext, lang: str):
    key = cb.data.split(":")[2]
    tpl = TEMPLATES.get(key)
    if not tpl:
        return
    data = await state.get_data()
    name = data["worker"]
    bundle = from_code(tpl["code"], "worker.js")
    if tpl.get("crons"):
        bundle.analysis.crons = list(tpl["crons"])
    await state.set_state(Deploy.code)
    await state.update_data(worker=name)
    await edit_or_send(cb, t(lang, "nw_tpl_chosen", title=esc(tpl["title"]), name=esc(name)))
    await analyze_and_plan(cb.message, state, app, lang, bundle, name=name)
