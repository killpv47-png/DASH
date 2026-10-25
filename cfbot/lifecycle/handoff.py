"""Run lifecycle while hosted on GitHub Actions (the bot itself manages Cloudflare).

A job dies at 6h.  ``LifecycleManager``:
  * checkpoints the DB every ``checkpoint_interval_s`` (only when changed)
  * at ``max_run_minutes`` (or on demand) performs a HANDOFF:
      1. tell every user  2. final checkpoint  3. dispatch the same workflow
      again via HOST_PAT  4. stop polling and exit 0 (the workflow ``concurrency``
      group makes the new run wait, so there is never a double-poll)
  * runs the "watch" poller that notifies users about new deployments of Workers they follow.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable

from ..core.config import Settings
from ..core.db import Database
from ..core.notify import Notifier
from ..cloudflare.client import CloudflareClient, CloudflareError
from ..hosting import HostError, HostRepoClient
from ..i18n import t
from .checkpoint import Checkpointer

log = logging.getLogger(__name__)



class LifecycleManager:
    def __init__(self, settings: Settings, db: Database, notifier: Notifier, checkpointer: Checkpointer,
                 *, stop: Callable[[], Awaitable[None]], cf_factory: Callable[[int], Awaitable[CloudflareClient | None]]):
        self.s = settings
        self.db = db
        self.notifier = notifier
        self.cp = checkpointer
        self.stop = stop
        self.cf_factory = cf_factory
        self.started = time.time()
        self.handing_off = False
        self._tasks: list[asyncio.Task] = []

    async def start(self, restored: str):
        for u in await self.db.all_users():
            await self.notifier.send(
                u["tg_id"],
                t(u["lang"], "lifecycle_hello", run=self.s.run_id or "local", attempt=self.s.run_attempt,
                  restored=restored, minutes=self.s.max_run_minutes), kind="system")
            if not self.cp.enabled and self.s.in_actions:
                await self.notifier.send(u["tg_id"], t(u["lang"], "lifecycle_no_pat"), kind="system")
        self._tasks.append(asyncio.create_task(self._checkpoint_loop(), name="checkpoint"))
        self._tasks.append(asyncio.create_task(self._budget_loop(), name="budget"))
        self._tasks.append(asyncio.create_task(self._watch_loop(), name="watch"))

    async def shutdown(self):
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _checkpoint_loop(self):
        from ..telegram.keyboards import persist_ids
        while True:
            await asyncio.sleep(self.s.checkpoint_interval_s)
            try:
                await persist_ids(self.db)
                await self.cp.save()
            except Exception as e:
                log.warning("periodic checkpoint failed: %s", e)

    async def _budget_loop(self):
        if not self.s.in_actions:
            return
        deadline = self.started + self.s.max_run_minutes * 60
        while time.time() < deadline:
            await asyncio.sleep(min(30, max(1, deadline - time.time())))
        await self.handoff(reason="budget")

    async def _watch_loop(self):
        await asyncio.sleep(15)
        while True:
            try:
                await self.poll_watches()
            except Exception:
                log.exception("watch poll failed")
            await asyncio.sleep(60)

    async def poll_watches(self):
        """Notify when a watched Worker gets a new deployment (deploy, rollback, settings change)."""
        watches = await self.db.list_watches()
        if not watches:
            return
        clients: dict[int, CloudflareClient | None] = {}
        try:
            for w in watches:
                uid = w["tg_id"]
                if uid not in clients:
                    clients[uid] = await self.cf_factory(uid)
                cf = clients[uid]
                if cf is None:
                    continue
                try:
                    deps = await cf.list_deployments(w["worker"])
                except CloudflareError:
                    continue
                if not deps:
                    continue
                latest = deps[0]
                if w["last_deployment"] == latest.get("id"):
                    continue
                if w["last_deployment"] is not None:  # first poll only records the baseline
                    user = await self.db.get_user(uid)
                    lang = user["lang"] if user else "en"
                    ann = latest.get("annotations") or {}
                    versions = ", ".join(f"{v.get('version_id', '')[:8]} ({v.get('percentage')}%)" for v in latest.get("versions") or [])
                    await self.notifier.send(uid, t(lang, "watch_event", worker=w["worker"], source=latest.get("source", ""),
                                                    author=latest.get("author_email", "") or "—", versions=versions,
                                                    message=ann.get("workers/message", "") or "—",
                                                    when=latest.get("created_on", "")), kind="watch")
                await self.db.update_watch(w["id"], latest.get("id"))
        finally:
            for cf in clients.values():
                if cf:
                    await cf.aclose()

    async def handoff(self, *, reason: str = "manual") -> bool:
        if self.handing_off:
            return False
        self.handing_off = True
        log.info("handoff starting (reason=%s)", reason)
        users = await self.db.all_users()
        for u in users:
            await self.notifier.send(u["tg_id"], t(u["lang"], "lifecycle_bye"), kind="system")
        try:
            from ..telegram.keyboards import persist_ids
            await persist_ids(self.db)
            await self.cp.save(force=True)
        except Exception as e:
            log.error("final checkpoint failed: %s", e)
            for u in users:
                await self.notifier.send(u["tg_id"], t(u["lang"], "export_fail", error=str(e)[:200]), kind="system")
        dispatched = await self.dispatch_next_run()
        if not dispatched and self.s.in_actions:
            log.error("could not dispatch next run — relying on cron watchdog")
        await asyncio.sleep(1)
        await self.stop()
        return dispatched

    async def dispatch_next_run(self) -> bool:
        if not (self.s.in_actions and self.s.host_pat and self.s.host_repo):
            return False
        async with HostRepoClient(self.s.host_pat) as host:
            try:
                ref = await host.default_branch(self.s.host_repo)
                await host.dispatch(self.s.host_repo, self.s.workflow_file, ref, {"reason": "handoff"})
                return True
            except HostError as e:
                log.error("dispatch failed: %s", e)
                return False
