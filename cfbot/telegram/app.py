"""Shared application context injected into every handler via aiogram's workflow data."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from aiogram import Bot

from ..cloudflare.client import CloudflareClient
from ..core.config import Settings
from ..core.crypto import decrypt_str, encrypt_str
from ..core.db import Database
from ..core.notify import Notifier
from ..core.redact import register_secret
from ..i18n import t as _t

log = logging.getLogger(__name__)


@dataclass
class AppContext:
    settings: Settings
    db: Database
    bot: Bot
    notifier: Notifier
    lifecycle: Optional[object] = None  # LifecycleManager (set after construction)
    agents: dict[int, object] = field(default_factory=dict)   # tg_id -> Agent
    ai_tasks: dict[int, asyncio.Task] = field(default_factory=dict)
    worker_cache: dict[int, list[dict]] = field(default_factory=dict)

    # ------------------------------------------------------------ helpers
    async def lang(self, tg_id: int) -> str:
        u = await self.db.get_user(tg_id)
        return (u["lang"] if u else None) or "en"

    async def t(self, tg_id: int, key: str, **kw) -> str:
        return _t(await self.lang(tg_id), key, **kw)

    # ------------------------------------------------------------ credentials
    async def credential_for(self, tg_id: int) -> dict | None:
        """{mode: 'token', token} or {mode: 'global_key', email, key} — decrypted in memory only."""
        u = await self.db.get_user(tg_id)
        if not u or not u["cf_token_enc"]:
            return None
        try:
            cred = json.loads(decrypt_str(u["cf_token_enc"], self.settings.state_key))
        except Exception:
            log.error("cannot decrypt Cloudflare credential for %s (STATE_KEY changed?)", tg_id)
            return None
        register_secret(cred.get("token"))
        register_secret(cred.get("key"))
        return cred

    async def save_credential(self, tg_id: int, cred: dict) -> None:
        register_secret(cred.get("token"))
        register_secret(cred.get("key"))
        await self.db.set_user_fields(tg_id, cf_token_enc=encrypt_str(json.dumps(cred), self.settings.state_key))

    @staticmethod
    def client_from(cred: dict, account_id: str = "", on_wait=None) -> CloudflareClient:
        if cred.get("mode") == "global_key":
            return CloudflareClient(email=cred["email"], global_key=cred["key"], account_id=account_id, on_wait=on_wait)
        return CloudflareClient(cred["token"], account_id=account_id, on_wait=on_wait)

    async def cf(self, tg_id: int) -> CloudflareClient | None:
        cred = await self.credential_for(tg_id)
        if not cred:
            return None
        u = await self.db.get_user(tg_id)

        async def on_wait(secs: float, kind: str):
            await self.notifier.send(tg_id, await self.t(tg_id, "cf_wait", secs=int(secs)), kind="wait", store=False)

        cf = self.client_from(cred, (u["cf_account_id"] if u else "") or "", on_wait)
        cf.token_kind = "global_key" if cred.get("mode") == "global_key" else (cred.get("kind") or "user")
        return cf

    async def workers(self, tg_id: int, refresh: bool = False) -> list[dict]:
        if not refresh and tg_id in self.worker_cache:
            return self.worker_cache[tg_id]
        cf = await self.cf(tg_id)
        if not cf:
            return []
        try:
            ws = await cf.list_workers()
        finally:
            await cf.aclose()
        ws = sorted(ws, key=lambda w: w.get("modified_on") or "", reverse=True)
        self.worker_cache[tg_id] = ws
        from .keyboards import persist_ids, register_names
        register_names(w["id"] for w in ws)
        await persist_ids(self.db)
        return ws

    # ---------------------------------------------------------------- AI cfg
    async def ai_config(self, tg_id: int) -> dict | None:
        cfg = await self.db.kv_get(f"ai:{tg_id}")
        if not cfg or not cfg.get("model"):
            return None
        try:
            cfg["api_key"] = decrypt_str(bytes.fromhex(cfg["api_key_enc"]), self.settings.state_key)
        except Exception:
            return None
        register_secret(cfg["api_key"])
        return cfg

    async def save_ai_config(self, tg_id: int, base_url: str, api_key: str, model: str | None) -> None:
        register_secret(api_key)
        await self.db.kv_set(f"ai:{tg_id}", {
            "base_url": base_url, "api_key_enc": encrypt_str(api_key, self.settings.state_key).hex(), "model": model,
        })

    @property
    def workspace(self) -> Path:
        return self.settings.workspace_dir
