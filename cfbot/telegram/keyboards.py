"""Inline + reply keyboards.  Callback data is compact: ``ns:action:arg``."""

from __future__ import annotations

import hashlib
from typing import Iterable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from ..i18n import LANG_NAMES, t

# Telegram limits callback_data to 64 bytes, so Worker / resource names are referenced by a short hash.
# The map is mirrored into the DB (kv "name_ids") so buttons in old messages keep working
# after a restart; see ``persist_ids`` / ``load_ids``.
_IDS: dict[str, str] = {}
_DIRTY: set[str] = set()


def nid(name: str) -> str:
    h = hashlib.sha1(name.encode()).hexdigest()[:10]
    if h not in _IDS:
        _IDS[h] = name
        _DIRTY.add(h)
    return h


def name_from_id(h: str) -> str | None:
    return _IDS.get(h)


async def load_ids(db) -> None:
    try:
        _IDS.update(await db.kv_get("name_ids", {}) or {})
    except Exception:
        pass


async def persist_ids(db) -> None:
    if not _DIRTY:
        return
    try:
        await db.kv_set("name_ids", _IDS)
        _DIRTY.clear()
    except Exception:
        pass


def register_names(names: Iterable[str]) -> None:
    for n in names:
        nid(n)


def ib(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data[:64])


def ub(text: str, url: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, url=url)


def rows(*btns: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(r) for r in btns if r])


def lang_keyboard() -> InlineKeyboardMarkup:
    items = list(LANG_NAMES.items())
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib(name, f"lang:set:{code}") for code, name in items[i:i + 2]] for i in range(0, len(items), 2)
    ])


MENU_KEYS = ("btn_workers", "btn_new_worker", "btn_deploy", "btn_storage", "btn_secrets", "btn_ai", "btn_scan",
             "btn_notifs", "btn_settings", "btn_help", "btn_tokens", "btn_analytics")


def main_reply_keyboard(lang: str) -> ReplyKeyboardMarkup:
    k = lambda key: KeyboardButton(text=t(lang, key))  # noqa: E731
    return ReplyKeyboardMarkup(
        keyboard=[
            [k("btn_workers"), k("btn_new_worker"), k("btn_deploy")],
            [k("btn_storage"), k("btn_secrets"), k("btn_ai")],
            [k("btn_analytics"), k("btn_scan"), k("btn_notifs")],
            [k("btn_tokens"), k("btn_settings"), k("btn_help")],
        ],
        resize_keyboard=True, is_persistent=True,
    )


def main_inline(lang: str) -> InlineKeyboardMarkup:
    return rows(
        [ib(t(lang, "btn_workers"), "wk:list:0"), ib(t(lang, "btn_new_worker"), "nw:start")],
        [ib(t(lang, "btn_deploy"), "dp:pick:0"), ib(t(lang, "btn_secrets"), "sec:pick:0")],
        [ib(t(lang, "btn_storage"), "st:home"), ib(t(lang, "btn_analytics"), "ops:metrics")],
        [ib(t(lang, "btn_ai"), "ai:home"), ib(t(lang, "btn_scan"), "scan:run")],
        [ib(t(lang, "btn_tokens"), "tok:home"), ib(t(lang, "btn_notifs"), "notif:list")],
        [ib(t(lang, "btn_settings"), "set:home"), ib(t(lang, "btn_help"), "help:home")],
    )


def back_menu(lang: str, back: str | None = None) -> InlineKeyboardMarkup:
    r = [ib(t(lang, "btn_menu"), "menu:home")]
    if back:
        r.insert(0, ib(t(lang, "btn_back"), back))
    return rows(r)


def cancel_kb(lang: str) -> InlineKeyboardMarkup:
    return rows([ib(t(lang, "btn_cancel"), "flow:cancel")])


def paginate(lang: str, items: list[tuple[str, str]], page: int, prefix: str, per_page: int = 8,
             extra: list[list[InlineKeyboardButton]] | None = None) -> tuple[InlineKeyboardMarkup, int]:
    pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(page, pages - 1))
    chunk = items[page * per_page:(page + 1) * per_page]
    kb = [[ib(text, data)] for text, data in chunk]
    nav = []
    if page > 0:
        nav.append(ib(t(lang, "btn_prev"), f"{prefix}:{page - 1}"))
    if page < pages - 1:
        nav.append(ib(t(lang, "btn_more"), f"{prefix}:{page + 1}"))
    if nav:
        kb.append(nav)
    for row in extra or []:
        kb.append(row)
    kb.append([ib(t(lang, "btn_menu"), "menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=kb), pages


def worker_picker(lang: str, workers: list[dict], page: int, action: str,
                  extra: list[list[InlineKeyboardButton]] | None = None) -> tuple[InlineKeyboardMarkup, int]:
    register_names(w["id"] for w in workers)
    items = [(("⚡ " + w["id"])[:60], f"{action}:{nid(w['id'])}") for w in workers]
    return paginate(lang, items, page, f"{action.split(':')[0]}:pick", extra=extra)


def worker_card_kb(lang: str, name: str, watched: bool) -> InlineKeyboardMarkup:
    r = nid(name)
    return rows(
        [ib(t(lang, "btn_w_deploy"), f"dp:w:{r}"), ib(t(lang, "btn_w_code"), f"wk:code:{r}")],
        [ib(t(lang, "btn_w_secrets"), f"sec:w:{r}"), ib(t(lang, "btn_w_bindings"), f"wk:bind:{r}")],
        [ib(t(lang, "btn_w_deployments"), f"ops:deps:{r}"), ib(t(lang, "btn_w_cron"), f"ops:cron:{r}")],
        [ib(t(lang, "btn_w_routes"), f"ops:routes:{r}"), ib(t(lang, "btn_w_metrics"), f"ops:m:{r}")],
        [ib(t(lang, "btn_w_test"), f"ops:test:{r}"), ib(t(lang, "btn_w_settings"), f"wk:edit:{r}")],
        [ib(t(lang, "btn_w_unwatch" if watched else "btn_w_watch"), f"wk:{'unwatch' if watched else 'watch'}:{r}"),
         ib(t(lang, "btn_w_ai"), f"ai:w:{r}")],
        [ib(t(lang, "btn_w_delete"), f"wk:del:{r}")],
        [ib(t(lang, "btn_back"), "wk:list:0"), ib(t(lang, "btn_menu"), "menu:home")],
    )


def ai_home_kb(lang: str) -> InlineKeyboardMarkup:
    return rows(
        [ib(t(lang, "btn_ai_new"), "ai:new"), ib(t(lang, "btn_ai_sessions"), "ai:sessions")],
        [ib(t(lang, "btn_ai_memory"), "ai:memory"), ib(t(lang, "btn_ai_skills"), "ai:skills")],
        [ib(t(lang, "btn_ai_model"), "ai:setup"), ib(t(lang, "btn_ai_stop"), "ai:stop")],
        [ib(t(lang, "btn_menu"), "menu:home")],
    )


def ai_stop_kb(lang: str) -> InlineKeyboardMarkup:
    return rows([ib(t(lang, "btn_ai_stop"), "ai:stop")])
