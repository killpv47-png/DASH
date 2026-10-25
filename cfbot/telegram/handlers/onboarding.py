"""/start → language → Cloudflare credential (token guide with official template links) → verify → scan → menu."""

from __future__ import annotations

import json
import re

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ...cloudflare.access import LEVELS
from ...cloudflare.client import GLOBAL_KEY_RE, CloudflareClient, CloudflareError
from ...cloudflare.scanner import scan_account
from ...cloudflare.tokens import DOCS_GLOBAL_KEY, DOCS_PERMISSIONS, FEATURE_PERMS, PRESETS, hint_for
from ...i18n import LANG_NAMES, t
from ..app import AppContext
from ..keyboards import ib, lang_keyboard, main_inline, main_reply_keyboard, persist_ids, register_names, rows, ub
from ..states import Onboard
from ..utils import edit_or_send, esc, safe_delete
from .router_bridge import entry

router = Router(name="onboarding")
# API tokens: legacy 40-char [A-Za-z0-9_-] or the newer prefixed format (cfut_/cfat_…). Global API Key: 37 hex chars.
TOKEN_RE = re.compile(r"^(?:cf[a-z]{1,3}_[A-Za-z0-9_\-]{20,}|[A-Za-z0-9_\-]{40,})$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ------------------------------------------------------------------ start / language
@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext, app: AppContext, user_row):
    await state.clear()
    if not user_row["cf_token_enc"]:
        await state.set_state(Onboard.lang)
        await msg.answer(t("en", "choose_lang"), reply_markup=lang_keyboard(), parse_mode="HTML")
    else:
        await show_menu(msg, app, user_row["tg_id"])


@router.message(Command("lang", "language"))
async def cmd_lang(msg: Message):
    await msg.answer(t("en", "choose_lang"), reply_markup=lang_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("lang:set:"))
async def cb_lang(cb: CallbackQuery, state: FSMContext, app: AppContext, user_row):
    code = cb.data.split(":")[2]
    if code not in LANG_NAMES:
        return
    await app.db.set_user_fields(cb.from_user.id, lang=code)
    await cb.message.edit_text(t(code, "lang_set", lang=LANG_NAMES[code]), parse_mode="HTML")
    if not user_row["cf_token_enc"]:
        await state.set_state(Onboard.token)
        await cb.message.answer(t(code, "welcome"), parse_mode="HTML", disable_web_page_preview=True,
                                reply_markup=token_menu_kb(code))
    else:
        await show_menu(cb.message, app, cb.from_user.id)


# ------------------------------------------------------------------ token guide
def token_menu_kb(lang: str):
    return rows(
        [ib(t(lang, "tok_btn_full"), "tok:p:full")],
        [ib(t(lang, "tok_btn_workers"), "tok:p:workers"), ib(t(lang, "tok_btn_storage"), "tok:p:storage")],
        [ib(t(lang, "tok_btn_routes"), "tok:p:routes"), ib(t(lang, "tok_btn_readonly"), "tok:p:readonly")],
        [ib(t(lang, "tok_btn_global"), "tok:gk")],
        [ib(t(lang, "tok_btn_matrix"), "tok:matrix")],
        [ib(t(lang, "tok_btn_paste"), "tok:paste")],
    )


async def token_home(event, state: FSMContext, lang: str):
    await state.set_state(Onboard.token)
    await edit_or_send(event, t(lang, "tok_home"), token_menu_kb(lang))


@entry("tok:home")
async def entry_tok(msg: Message, app: AppContext, lang: str, state: FSMContext):
    await token_home(msg, state, lang)


@router.message(Command("token", "tokens"))
async def cmd_token(msg: Message, state: FSMContext, lang: str):
    await token_home(msg, state, lang)


@router.callback_query(F.data == "tok:home")
async def cb_tok_home(cb: CallbackQuery, state: FSMContext, lang: str):
    await token_home(cb, state, lang)


@router.callback_query(F.data.startswith("tok:p:"))
async def cb_preset(cb: CallbackQuery, state: FSMContext, lang: str):
    p = PRESETS.get(cb.data.split(":")[2])
    if not p:
        return
    await state.set_state(Onboard.token)
    perms = "\n".join(f"• {esc(x)}" for x in p.human_perms())
    risk = t(lang, f"risk_{p.risk}")
    text = t(lang, "tok_preset", title=t(lang, f"tok_btn_{p.key}"), desc=t(lang, p.i18n), perms=perms, risk=risk)
    kb = rows([ub(t(lang, "tok_open_user"), p.user_url())], [ub(t(lang, "tok_open_account"), p.account_url())],
              [ib(t(lang, "tok_btn_paste"), "tok:paste")], [ib(t(lang, "btn_back"), "tok:home")])
    await edit_or_send(cb, text, kb)


@router.callback_query(F.data == "tok:matrix")
async def cb_matrix(cb: CallbackQuery, lang: str):
    body = "\n".join(f"• <b>{esc(k)}</b>\n  → {esc(v)}" for k, v in FEATURE_PERMS.items())
    await edit_or_send(cb, t(lang, "tok_matrix", list=body, docs=DOCS_PERMISSIONS),
                       rows([ib(t(lang, "btn_back"), "tok:home")]))


@router.callback_query(F.data == "tok:gk")
async def cb_global(cb: CallbackQuery, state: FSMContext, lang: str):
    kb = rows([ub(t(lang, "tok_open_gk"), "https://dash.cloudflare.com/profile/api-tokens")],
              [ib(t(lang, "tok_gk_use"), "tok:gk:go")], [ib(t(lang, "btn_back"), "tok:home")])
    await edit_or_send(cb, t(lang, "tok_global", docs=DOCS_GLOBAL_KEY), kb)


@router.callback_query(F.data == "tok:gk:go")
async def cb_global_go(cb: CallbackQuery, state: FSMContext, lang: str):
    await state.set_state(Onboard.gk_email)
    await edit_or_send(cb, t(lang, "gk_ask_email"), rows([ib(t(lang, "btn_cancel"), "flow:cancel")]))


@router.callback_query(F.data == "tok:paste")
async def cb_paste(cb: CallbackQuery, state: FSMContext, lang: str):
    await state.set_state(Onboard.token)
    await edit_or_send(cb, t(lang, "send_token"), rows([ib(t(lang, "btn_back"), "tok:home")]))


# ------------------------------------------------------------------ credential entry
@router.message(Onboard.token, F.text & ~F.text.startswith("/"))
async def got_token(msg: Message, state: FSMContext, app: AppContext, lang: str):
    token = (msg.text or "").strip()
    await safe_delete(msg)  # never leave the token in chat history
    if GLOBAL_KEY_RE.match(token):
        await state.update_data(gk_key=token)
        await state.set_state(Onboard.gk_email)
        await msg.answer(t(lang, "gk_detected"), parse_mode="HTML")
        return
    if not TOKEN_RE.match(token):
        await msg.answer(t(lang, "token_invalid"), parse_mode="HTML", reply_markup=token_menu_kb(lang))
        return
    await _verify_and_save(msg, state, app, lang, {"mode": "token", "token": token})


@router.message(Onboard.gk_email, F.text & ~F.text.startswith("/"))
async def got_email(msg: Message, state: FSMContext, app: AppContext, lang: str):
    email = msg.text.strip()
    if not EMAIL_RE.match(email):
        await msg.answer(t(lang, "gk_email_bad"), parse_mode="HTML")
        return
    data = await state.get_data()
    if data.get("gk_key"):
        await _verify_and_save(msg, state, app, lang, {"mode": "global_key", "email": email, "key": data["gk_key"]})
        return
    await state.update_data(gk_email=email)
    await state.set_state(Onboard.gk_key)
    await msg.answer(t(lang, "gk_ask_key"), parse_mode="HTML")


@router.message(Onboard.gk_key, F.text & ~F.text.startswith("/"))
async def got_gk(msg: Message, state: FSMContext, app: AppContext, lang: str):
    key = msg.text.strip()
    await safe_delete(msg)
    if not GLOBAL_KEY_RE.match(key):
        await msg.answer(t(lang, "gk_key_bad"), parse_mode="HTML")
        return
    data = await state.get_data()
    await _verify_and_save(msg, state, app, lang, {"mode": "global_key", "email": data.get("gk_email", ""), "key": key})


async def _verify_and_save(msg: Message, state: FSMContext, app: AppContext, lang: str, cred: dict):
    status = await msg.answer(t(lang, "token_checking"), parse_mode="HTML")
    cf = app.client_from(cred)
    try:
        v = await cf.verify()
    except CloudflareError as e:
        await cf.aclose()
        hint = hint_for(e.codes)
        await status.edit_text(t(lang, "token_bad", error=esc(e.message), hint=esc(hint)), parse_mode="HTML",
                               reply_markup=token_menu_kb(lang))
        return
    except Exception as e:  # network
        await cf.aclose()
        await status.edit_text(t(lang, "token_bad", error=esc(str(e)[:200]), hint=""), parse_mode="HTML")
        return
    if v.get("status") and v["status"] != "active":
        await cf.aclose()
        await status.edit_text(t(lang, "token_bad", error=f"token status: {esc(v['status'])}", hint=""), parse_mode="HTML")
        return
    cred["kind"] = v.get("kind")
    await app.save_credential(msg.chat.id, cred)
    await app.db.set_user_fields(msg.chat.id, cf_account_id=v.get("account_id") or None)
    await state.clear()
    await status.edit_text(t(lang, "token_saved", kind=t(lang, f"kind_{v.get('kind', 'user')}")), parse_mode="HTML")
    await run_scan(msg, app, msg.chat.id, lang, cf)
    await show_menu(msg, app, msg.chat.id)


# ------------------------------------------------------------------ scan
async def run_scan(msg: Message, app: AppContext, tg_id: int, lang: str, cf: CloudflareClient | None = None,
                   account_id: str | None = None):
    if cf is None:
        cf = await app.cf(tg_id)
        if not cf:
            await msg.answer(t(lang, "need_token"), parse_mode="HTML")
            return
    status = await msg.answer(t(lang, "scan_step", step="credentials"), parse_mode="HTML")

    async def progress(step: str):
        await app.notifier.edit(msg.chat.id, status.message_id, t(lang, "scan_step", step=step), min_interval=0.4)

    u = await app.db.get_user(tg_id)
    try:
        res = await scan_account(cf, account_id=account_id or (u["cf_account_id"] if u else None), progress=progress)
    except CloudflareError as e:
        await status.edit_text(t(lang, "error_generic", error=esc(e.message)), parse_mode="HTML")
        return
    finally:
        await cf.aclose()
    level = res.level or LEVELS["GHOST"]
    await app.db.set_user_fields(tg_id, cf_email=res.email or None, cf_account_id=res.account_id or None,
                                 cf_account_name=res.account_name or None,
                                 cf_caps=json.dumps(res.caps.as_dict() if res.caps else {}), access_level=level.name)
    app.worker_cache[tg_id] = res.workers
    register_names(w["id"] for w in res.workers)
    await persist_ids(app.db)
    c = res.caps
    yes, no = "✅", "—"
    caps = " · ".join(f"{lbl} {yes if getattr(c, k, False) else no}" for k, lbl in
                      (("workers_write", "Workers"), ("kv", "KV"), ("d1", "D1"), ("r2", "R2"), ("queues", "Queues"),
                       ("zones", "Zones"), ("analytics", "Analytics"))) if c else "—"
    text = t(lang, "scan_report", email=esc(res.email or "—"), kind=t(lang, f"kind_{res.kind or 'user'}"),
             account=esc(res.account_name or res.account_id or "—"), accounts=len(res.accounts),
             workers=len(res.workers), kv=len(res.kv), d1=len(res.d1), r2=len(res.r2), queues=len(res.queues),
             zones=len(res.zones), subdomain=esc(f"{res.subdomain}.workers.dev" if res.subdomain else "—"),
             level_emoji=level.emoji, level=level.name, level_desc=t(lang, level.description_key), caps=caps,
             exact=t(lang, "caps_exact" if c and c.exact else "caps_probed"),
             expires=esc(res.expires_on or "—"))
    if c and c.perm_names:
        text += "\n" + t(lang, "scan_perms", perms=esc(", ".join(c.perm_names[:20])))
    if res.workers:
        text += "\n\n" + "\n".join(f"⚡ <code>{esc(w['id'])}</code>" for w in res.workers[:15])
    if res.errors:
        text += "\n\n" + t(lang, "scan_errors", errors=esc("; ".join(res.errors)[:600]))
    kb = None
    if len(res.accounts) > 1:
        register_names(a["id"] for a in res.accounts)
        from ..keyboards import nid
        kb = rows(*[[ib(("✅ " if a["id"] == res.account_id else "🏢 ") + a.get("name", a["id"])[:40], f"acct:set:{nid(a['id'])}")]
                    for a in res.accounts[:10]])
    await status.edit_text(text[:4000], parse_mode="HTML", disable_web_page_preview=True, reply_markup=kb)
    await app.db.add_notification(tg_id, "scan", f"Account scan: {len(res.workers)} Workers, level {level.name}")


@router.callback_query(F.data.startswith("acct:set:"))
async def cb_account(cb: CallbackQuery, app: AppContext, lang: str):
    from ..keyboards import name_from_id
    acc = name_from_id(cb.data.split(":")[2])
    if not acc:
        return
    await app.db.set_user_fields(cb.from_user.id, cf_account_id=acc)
    app.worker_cache.pop(cb.from_user.id, None)
    await run_scan(cb.message, app, cb.from_user.id, lang, account_id=acc)


async def show_menu(msg: Message, app: AppContext, tg_id: int):
    u = await app.db.get_user(tg_id)
    lang = u["lang"] or "en"
    level = LEVELS.get(u["access_level"] or "", LEVELS["GHOST"])
    who = u["cf_account_name"] or u["cf_email"] or u["cf_account_id"] or "?"
    await msg.answer(t(lang, "menu_title", account=esc(who), level_emoji=level.emoji),
                     reply_markup=main_reply_keyboard(lang), parse_mode="HTML")
    await msg.answer("👇", reply_markup=main_inline(lang))
