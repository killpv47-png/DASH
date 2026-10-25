"""Settings: language, Cloudflare credential, account switch, AI reconfigure, export state, restart (handoff)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ...cloudflare.access import LEVELS
from ...i18n import LANG_NAMES, t
from ..app import AppContext
from ..keyboards import back_menu, ib, lang_keyboard, rows
from ..utils import edit_or_send, esc
from .router_bridge import entry

router = Router(name="settings")


async def show(event, app: AppContext, tg_id: int, lang: str):
    u = await app.db.get_user(tg_id)
    ai = await app.db.kv_get(f"ai:{tg_id}")
    watches = await app.db.list_watches(tg_id)
    level = LEVELS.get(u["access_level"] or "", LEVELS["GHOST"])
    s = app.settings
    runtime = f"hosted on GitHub Actions run #{s.run_id} ({s.host_repo})" if s.in_actions else "local"
    text = t(lang, "settings_title", lang=LANG_NAMES.get(lang, lang), email=esc(u["cf_email"] or "—"),
             account=esc(u["cf_account_name"] or u["cf_account_id"] or "—"),
             level=f"{level.emoji} {level.name}", ai=esc(f"{ai['model']} @ {ai['base_url']}") if ai and ai.get("model") else "—",
             watches=", ".join(esc(w["worker"]) for w in watches) or "—", runtime=esc(runtime))
    kb = rows(
        [ib(t(lang, "btn_change_lang"), "set:lang"), ib(t(lang, "btn_change_token"), "tok:home")],
        [ib(t(lang, "btn_switch_account"), "set:accounts"), ib(t(lang, "btn_forget_token"), "set:forget")],
        [ib(t(lang, "btn_ai_reset"), "ai:setup"), ib(t(lang, "btn_export"), "set:export")],
        [ib(t(lang, "btn_restart"), "set:restart")],
        [ib(t(lang, "btn_menu"), "menu:home")],
    )
    await edit_or_send(event, text, kb)


@entry("set:home")
async def entry_settings(msg: Message, app: AppContext, lang: str, state: FSMContext):
    await show(msg, app, msg.from_user.id, lang)


@router.message(Command("settings"))
async def cmd_settings(msg: Message, app: AppContext, lang: str):
    await show(msg, app, msg.from_user.id, lang)


@router.callback_query(F.data == "set:home")
async def cb_home(cb: CallbackQuery, app: AppContext, lang: str):
    await show(cb, app, cb.from_user.id, lang)


@router.callback_query(F.data == "set:lang")
async def cb_lang(cb: CallbackQuery):
    await edit_or_send(cb, t("en", "choose_lang"), lang_keyboard())


@router.callback_query(F.data == "set:accounts")
async def cb_accounts(cb: CallbackQuery, app: AppContext, lang: str):
    from .onboarding import run_scan
    await run_scan(cb.message, app, cb.from_user.id, lang)


@router.callback_query(F.data == "set:forget")
async def cb_forget(cb: CallbackQuery, lang: str):
    await edit_or_send(cb, t(lang, "forget_confirm"),
                       rows([ib(t(lang, "btn_yes"), "set:forget:yes"), ib(t(lang, "btn_no"), "set:home")]))


@router.callback_query(F.data == "set:forget:yes")
async def cb_forget_yes(cb: CallbackQuery, app: AppContext, lang: str):
    await app.db.set_user_fields(cb.from_user.id, cf_token_enc=None, cf_caps=None, access_level=None)
    app.worker_cache.pop(cb.from_user.id, None)
    agent = app.agents.pop(cb.from_user.id, None)
    if agent:
        await agent.close()
    await edit_or_send(cb, t(lang, "forget_done"), back_menu(lang))


@router.callback_query(F.data == "set:export")
async def cb_export(cb: CallbackQuery, app: AppContext, lang: str):
    lc = app.lifecycle
    if not lc or not lc.cp.enabled:
        await app.notifier.send(cb.from_user.id, t(lang, "lifecycle_no_pat"), kind="system")
        return
    try:
        await lc.cp.save(force=True)
        await app.notifier.send(cb.from_user.id, t(lang, "export_done"), kind="system")
    except Exception as e:
        await app.notifier.send(cb.from_user.id, t(lang, "export_fail", error=esc(str(e)[:200])), kind="system")


@router.message(Command("restart"))
async def cmd_restart(msg: Message, lang: str):
    await msg.answer(t(lang, "restart_confirm"), parse_mode="HTML",
                     reply_markup=rows([ib(t(lang, "btn_yes"), "set:restart:yes"), ib(t(lang, "btn_no"), "menu:home")]))


@router.callback_query(F.data == "set:restart")
async def cb_restart(cb: CallbackQuery, lang: str):
    await edit_or_send(cb, t(lang, "restart_confirm"),
                       rows([ib(t(lang, "btn_yes"), "set:restart:yes"), ib(t(lang, "btn_no"), "set:home")]))


@router.callback_query(F.data == "set:restart:yes")
async def cb_restart_yes(cb: CallbackQuery, app: AppContext, lang: str):
    lc = app.lifecycle
    if not lc:
        return
    if not app.settings.in_actions:
        await edit_or_send(cb, t(lang, "restart_not_actions"), back_menu(lang))
    else:
        await edit_or_send(cb, t(lang, "restart_go"))
    import asyncio
    asyncio.create_task(lc.handoff(reason="manual"))
