"""Deploy code to a Worker: send .js/.mjs/.py/.zip or paste code → analysis → plan review → real deploy.

Flow
  1. pick an existing Worker (update) or "new Worker" (ask name)
  2. user sends a file or pastes code
  3. ``bundle.from_upload`` + ``analyzer`` → analysis report (handlers, bindings, vars/secrets, flags, blockers)
  4. ``deployer.build_plan`` → one row per binding; user taps a row to choose
        create new KV/D1/R2/Queue · link existing (pick from list or type id) · enter value · skip
  5. "Deploy" is only enabled when nothing is pending and there are no blockers
  6. ``deployer.execute`` creates resources, uploads with bindings, sets crons, enables workers.dev
Secret values typed by the user are deleted from the chat immediately and kept only in memory
until the upload (never written to the DB / checkpoint).
"""

from __future__ import annotations

import io
import secrets as _secrets

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ...cloudflare.analyzer import AUTO_CREATABLE, KIND_LABEL, storage_advice
from ...cloudflare.bundle import Bundle, BundleError, from_code, from_upload
from ...cloudflare.client import SCRIPT_NAME_RE, CloudflareError
from ...cloudflare.deployer import Plan, build_plan, execute, resource_name
from ...i18n import t
from ..app import AppContext
from ..keyboards import back_menu, cancel_kb, ib, name_from_id, nid, register_names, rows, worker_picker
from ..states import Deploy
from ..utils import edit_or_send, esc, human_size, safe_delete
from .router_bridge import entry
from .workers import cf_err

router = Router(name="deploy")
# per-user in-memory state for the flow (bundle bytes + plan with secret values)
_BUNDLES: dict[int, Bundle] = {}
_PLANS: dict[int, Plan] = {}


# ------------------------------------------------------------------ step 1: target
async def pick_target(event, app: AppContext, tg_id: int, lang: str, page: int, state: FSMContext):
    await state.clear()
    try:
        ws = await app.workers(tg_id)
    except CloudflareError as e:
        await edit_or_send(event, cf_err(lang, e), back_menu(lang))
        return
    kb, _ = worker_picker(lang, ws, page, "dp:w", extra=[[ib(t(lang, "btn_dp_new"), "dp:new")]])
    await edit_or_send(event, t(lang, "dp_pick"), kb)


@entry("dp:pick:0")
async def entry_dp(msg: Message, app: AppContext, lang: str, state: FSMContext):
    await pick_target(msg, app, msg.from_user.id, lang, 0, state)


@router.message(Command("deploy"))
async def cmd_deploy(msg: Message, state: FSMContext, app: AppContext, lang: str):
    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) == 2 and SCRIPT_NAME_RE.match(parts[1].strip()):
        await ask_code(msg, state, lang, parts[1].strip())
    else:
        await pick_target(msg, app, msg.from_user.id, lang, 0, state)


@router.callback_query(F.data.startswith("dp:pick:"))
async def cb_pick(cb: CallbackQuery, state: FSMContext, app: AppContext, lang: str):
    await pick_target(cb, app, cb.from_user.id, lang, int(cb.data.split(":")[2]), state)


@router.callback_query(F.data.startswith("dp:w:"))
async def cb_worker(cb: CallbackQuery, state: FSMContext, lang: str):
    name = name_from_id(cb.data.split(":")[2])
    if name:
        await ask_code(cb, state, lang, name)


@router.callback_query(F.data == "dp:new")
async def cb_new(cb: CallbackQuery, state: FSMContext, lang: str):
    await state.clear()
    await state.set_state(Deploy.name)
    await edit_or_send(cb, t(lang, "dp_ask_name"), cancel_kb(lang))


@router.message(Deploy.name, F.text & ~F.text.startswith("/"))
async def got_name(msg: Message, state: FSMContext, lang: str):
    name = msg.text.strip().lower()
    if not SCRIPT_NAME_RE.match(name):
        await msg.answer(t(lang, "worker_name_bad"), parse_mode="HTML")
        return
    await ask_code(msg, state, lang, name)


async def ask_code(event, state: FSMContext, lang: str, name: str):
    await state.set_state(Deploy.code)
    await state.update_data(worker=name)
    nid(name)
    await edit_or_send(event, t(lang, "dp_send_code", name=esc(name)), cancel_kb(lang))


# ------------------------------------------------------------------ step 2-3: code → analysis
@router.message(Deploy.code, F.document)
async def got_file(msg: Message, state: FSMContext, app: AppContext, lang: str):
    doc = msg.document
    if doc.file_size and doc.file_size > 20 * 1024 * 1024:
        await msg.answer(t(lang, "dp_too_big"), parse_mode="HTML")
        return
    buf = io.BytesIO()
    try:
        await app.bot.download(doc, destination=buf)
    except Exception as e:
        await msg.answer(t(lang, "dp_fail", error=esc(str(e)[:200])), parse_mode="HTML")
        return
    try:
        bundle = from_upload(doc.file_name or "worker.js", buf.getvalue())
    except BundleError as e:
        await msg.answer(t(lang, "dp_bad_bundle", error=esc(str(e))), parse_mode="HTML", reply_markup=cancel_kb(lang))
        return
    await analyze_and_plan(msg, state, app, lang, bundle)


@router.message(Deploy.code, F.text & ~F.text.startswith("/"))
async def got_text_code(msg: Message, state: FSMContext, app: AppContext, lang: str):
    code = msg.text
    if "export default" not in code and "addEventListener" not in code and "def on_fetch" not in code and "WorkerEntrypoint" not in code:
        await msg.answer(t(lang, "dp_not_code"), parse_mode="HTML")
        return
    try:
        bundle = from_code(code, "worker.py" if ("def on_fetch" in code or "WorkerEntrypoint" in code) and "export" not in code else "worker.js")
    except BundleError as e:
        await msg.answer(t(lang, "dp_bad_bundle", error=esc(str(e))), parse_mode="HTML")
        return
    await analyze_and_plan(msg, state, app, lang, bundle)


async def analyze_and_plan(msg: Message, state: FSMContext, app: AppContext, lang: str, bundle: Bundle, name: str | None = None):
    data = await state.get_data()
    name = name or data.get("worker") or bundle.analysis.name_hint or "my-worker"
    tg_id = msg.chat.id
    job_id = _secrets.token_hex(4)
    await app.db.create_job(job_id, tg_id, "deploy", f"Deploy {bundle.source_name or 'code'} → {name}")
    await app.notifier.step(tg_id, f"Code received: {bundle.count} module(s), {human_size(bundle.total_bytes)}", job_id=job_id)
    cf = await app.cf(tg_id)
    if not cf:
        await msg.answer(t(lang, "need_token"), parse_mode="HTML")
        return
    existing_bindings, existing_secrets = [], set()
    try:
        if name in {w["id"] for w in await app.workers(tg_id)}:
            existing_bindings = [b for b in (await cf.get_worker_settings(name)).get("bindings") or [] if b.get("type") != "secret_text"]
            existing_secrets = {s["name"] for s in await cf.list_secrets(name)}
    except CloudflareError:
        pass
    finally:
        await cf.aclose()
    a = bundle.analysis
    plan = build_plan(name, a, existing_bindings=existing_bindings, existing_secrets=existing_secrets)
    _BUNDLES[tg_id] = bundle
    _PLANS[tg_id] = plan
    await state.set_state(Deploy.plan)
    await state.update_data(worker=name, job_id=job_id)
    await msg.answer(analysis_text(lang, bundle)[:4000], parse_mode="HTML", disable_web_page_preview=True)
    await app.notifier.step(tg_id, f"Analyzed: {len(a.handlers)} handler(s), {len(a.bindings)} binding(s), "
                                   f"{len(a.blockers)} blocker(s)", job_id=job_id, ok=not a.blockers)
    await show_plan(msg, tg_id, lang)


def analysis_text(lang: str, b: Bundle) -> str:
    a = b.analysis
    needs = "\n".join(f"• <code>{esc(x.name)}</code> → <b>{esc(KIND_LABEL.get(x.kind, x.kind))}</b> <i>({esc(x.reason)})</i>"
                      for x in a.bindings) or t(lang, "none")
    storage = "\n".join(f"💡 {esc(storage_advice(k))}" for k in sorted({x.kind for x in a.storage_needed if x.kind in AUTO_CREATABLE}))
    text = t(lang, "dp_analysis", main=esc(a.main_module), fmt=esc(a.format), size=human_size(b.total_bytes),
             modules=len(b.modules), handlers=esc(", ".join(a.handlers) or "—"), needs=needs,
             compat=esc(a.compatibility_date), flags=esc(", ".join(a.compatibility_flags) or "—"),
             crons=esc(", ".join(a.crons) or "—"), config=esc(a.config_file or "—"))
    if storage:
        text += "\n\n" + storage
    if a.durable_object_classes:
        text += "\n🧱 Durable Objects: " + esc(", ".join(a.durable_object_classes))
    if a.routes:
        text += "\n🛣 " + t(lang, "dp_routes_note", routes=esc(", ".join(a.routes)))
    if a.warnings:
        text += "\n\n" + "\n".join(f"⚠️ {esc(w)}" for w in a.warnings)
    if a.blockers:
        text += "\n\n" + "\n".join(f"⛔ {esc(w)}" for w in a.blockers)
    if b.skipped:
        text += "\n" + t(lang, "dp_skipped", n=len(b.skipped))
    return text


ACTION_ICON = {"pending": "❓", "create": "🆕", "link": "🔗", "value": "✏️", "keep": "♻️", "ai": "🧠", "skip": "⏭"}


def plan_text(lang: str, p: Plan, blockers: list[str]) -> str:
    lines = []
    for it in p.items:
        what = {"create": t(lang, "plan_create", name=esc(resource_name(p.worker, it.name))),
                "link": f"→ <code>{esc(it.target)}</code>", "value": t(lang, "plan_value_set"), "keep": t(lang, "plan_keep"),
                "ai": "Workers AI", "skip": t(lang, "plan_skip"), "pending": t(lang, "plan_pending")}[it.action]
        lines.append(f"{ACTION_ICON[it.action]} <code>{esc(it.name)}</code> ({esc(KIND_LABEL.get(it.kind, it.kind))}) {what}")
    body = "\n".join(lines) or t(lang, "none")
    state = t(lang, "plan_blocked") if blockers else (t(lang, "plan_pending_n", n=len(p.pending)) if p.pending else t(lang, "plan_ready"))
    return t(lang, "plan_title", name=esc(p.worker), mode=t(lang, "plan_update" if p.existing else "plan_new"), items=body,
             crons=esc(", ".join(p.crons) or "—"), wdev=t(lang, "yes" if p.enable_workers_dev else "no"), state=state)


def plan_kb(lang: str, p: Plan, blockers: list[str]):
    kb = [[ib(f"{ACTION_ICON[it.action]} {it.name}", f"dp:it:{i}")] for i, it in enumerate(p.items) if it.action != "keep"][:20]
    kb.append([ib(t(lang, "btn_plan_cron"), "dp:cron"), ib(t(lang, "btn_plan_wdev"), "dp:wdev")])
    if not blockers and not p.pending:
        kb.append([ib(t(lang, "btn_plan_deploy"), "dp:go")])
    kb.append([ib(t(lang, "btn_cancel"), "flow:cancel")])
    return rows(*kb)


async def show_plan(event, tg_id: int, lang: str):
    p, b = _PLANS.get(tg_id), _BUNDLES.get(tg_id)
    if not p or not b:
        return
    await edit_or_send(event, plan_text(lang, p, b.analysis.blockers)[:4000], plan_kb(lang, p, b.analysis.blockers))


# ------------------------------------------------------------------ step 4: plan editing
def _item_kb(lang: str, i: int, kind: str):
    btns = []
    if kind in AUTO_CREATABLE:
        btns.append([ib(t(lang, "btn_it_create"), f"dp:act:{i}:create")])
        btns.append([ib(t(lang, "btn_it_link"), f"dp:act:{i}:pick")])
    elif kind in ("var", "secret"):
        btns.append([ib(t(lang, "btn_it_value"), f"dp:act:{i}:value")])
        other = "secret" if kind == "var" else "var"
        btns.append([ib(t(lang, f"btn_it_as_{other}"), f"dp:act:{i}:as_{other}")])
    elif kind == "ai":
        btns.append([ib("🧠 Workers AI", f"dp:act:{i}:ai")])
    else:
        btns.append([ib(t(lang, "btn_it_target"), f"dp:act:{i}:link")])
    kinds = ["kv", "d1", "r2", "queue", "var", "secret", "service", "ai"]
    btns.append([ib(f"⇄ {k}", f"dp:kind:{i}:{k}") for k in kinds[:4]])
    btns.append([ib(f"⇄ {k}", f"dp:kind:{i}:{k}") for k in kinds[4:]])
    btns.append([ib(t(lang, "btn_it_skip"), f"dp:act:{i}:skip"), ib(t(lang, "btn_back"), "dp:plan")])
    return rows(*btns)


@router.callback_query(Deploy.plan, F.data == "dp:plan")
async def cb_plan(cb: CallbackQuery, state: FSMContext, lang: str):
    await show_plan(cb, cb.from_user.id, lang)


@router.callback_query(F.data.startswith("dp:it:"))
async def cb_item(cb: CallbackQuery, state: FSMContext, lang: str):
    p = _PLANS.get(cb.from_user.id)
    i = int(cb.data.split(":")[2])
    if not p or i >= len(p.items):
        return
    it = p.items[i]
    await state.set_state(Deploy.plan)
    await edit_or_send(cb, t(lang, "plan_item", name=esc(it.name), kind=esc(KIND_LABEL.get(it.kind, it.kind)),
                             note=esc(it.note or "—"), advice=esc(storage_advice(it.kind))), _item_kb(lang, i, it.kind))


@router.callback_query(F.data.startswith("dp:kind:"))
async def cb_kind(cb: CallbackQuery, state: FSMContext, lang: str):
    _, _, i, kind = cb.data.split(":")
    p = _PLANS.get(cb.from_user.id)
    if not p:
        return
    it = p.items[int(i)]
    it.kind, it.action, it.target, it.value = kind, ("create" if kind in AUTO_CREATABLE else "ai" if kind == "ai" else "pending"), "", None
    await cb_item(cb.model_copy(update={"data": f"dp:it:{i}"}), state, lang)


@router.callback_query(F.data.startswith("dp:act:"))
async def cb_act(cb: CallbackQuery, state: FSMContext, app: AppContext, lang: str):
    _, _, i, act = cb.data.split(":")
    tg_id = cb.from_user.id
    p = _PLANS.get(tg_id)
    if not p:
        return
    it = p.items[int(i)]
    if act in ("create", "skip", "ai"):
        it.action, it.target = act, ""
        await show_plan(cb, tg_id, lang)
    elif act in ("as_var", "as_secret"):
        it.kind, it.action, it.value = act[3:], "pending", None
        await cb_item(cb.model_copy(update={"data": f"dp:it:{i}"}), state, lang)
    elif act == "value":
        await state.set_state(Deploy.value)
        await state.update_data(item=int(i))
        key = "dp_ask_secret" if it.kind == "secret" else "dp_ask_var"
        await edit_or_send(cb, t(lang, key, name=esc(it.name)), rows([ib(t(lang, "btn_back"), "dp:plan")]))
    elif act == "link":
        await state.set_state(Deploy.link)
        await state.update_data(item=int(i))
        await edit_or_send(cb, t(lang, "dp_ask_target", name=esc(it.name), kind=esc(KIND_LABEL.get(it.kind, it.kind))),
                           rows([ib(t(lang, "btn_back"), "dp:plan")]))
    elif act == "pick":
        cf = await app.cf(tg_id)
        if not cf:
            return
        try:
            if it.kind == "kv":
                opts = [(n["title"], n["id"]) for n in await cf.list_kv()]
            elif it.kind == "d1":
                opts = [(d["name"], d["uuid"]) for d in await cf.list_d1()]
            elif it.kind == "r2":
                opts = [(b["name"], b["name"]) for b in await cf.list_r2()]
            else:
                opts = [(q["queue_name"], q["queue_name"]) for q in await cf.list_queues()]
        except CloudflareError as e:
            await edit_or_send(cb, cf_err(lang, e), rows([ib(t(lang, "btn_back"), f"dp:it:{i}")]))
            return
        finally:
            await cf.aclose()
        register_names(v for _, v in opts)
        kb = rows(*[[ib(f"🔗 {label[:40]}", f"dp:ln:{i}:{nid(v)}")] for label, v in opts[:20]],
                  [ib(t(lang, "btn_it_target"), f"dp:act:{i}:link"), ib(t(lang, "btn_back"), f"dp:it:{i}")])
        await edit_or_send(cb, t(lang, "dp_pick_existing", kind=esc(KIND_LABEL.get(it.kind, it.kind)), n=len(opts)), kb)


@router.callback_query(F.data.startswith("dp:ln:"))
async def cb_link_pick(cb: CallbackQuery, state: FSMContext, lang: str):
    _, _, i, h = cb.data.split(":")
    p = _PLANS.get(cb.from_user.id)
    target = name_from_id(h)
    if not p or not target:
        return
    it = p.items[int(i)]
    it.action, it.target = "link", target
    await state.set_state(Deploy.plan)
    await show_plan(cb, cb.from_user.id, lang)


@router.message(Deploy.value, F.text)
async def got_value(msg: Message, state: FSMContext, lang: str):
    data = await state.get_data()
    p = _PLANS.get(msg.from_user.id)
    if not p:
        return
    it = p.items[data["item"]]
    it.value = msg.text if it.kind == "secret" else msg.text.strip()
    it.action = "value"
    if it.kind == "secret":
        await safe_delete(msg)
    await state.set_state(Deploy.plan)
    await show_plan(msg, msg.from_user.id, lang)


@router.message(Deploy.link, F.text)
async def got_link(msg: Message, state: FSMContext, lang: str):
    data = await state.get_data()
    p = _PLANS.get(msg.from_user.id)
    if not p:
        return
    it = p.items[data["item"]]
    it.target, it.action = msg.text.strip(), "link"
    await state.set_state(Deploy.plan)
    await show_plan(msg, msg.from_user.id, lang)


@router.callback_query(F.data == "dp:cron")
async def cb_cron(cb: CallbackQuery, state: FSMContext, lang: str):
    await state.set_state(Deploy.cron)
    await edit_or_send(cb, t(lang, "dp_ask_cron"), rows([ib(t(lang, "btn_back"), "dp:plan")]))


@router.message(Deploy.cron, F.text)
async def got_cron(msg: Message, state: FSMContext, lang: str):
    from .ops import parse_crons
    p = _PLANS.get(msg.from_user.id)
    if not p:
        return
    crons, bad = parse_crons(msg.text)
    if bad:
        await msg.answer(t(lang, "cron_bad", bad=esc(", ".join(bad))), parse_mode="HTML")
        return
    p.crons = crons
    await state.set_state(Deploy.plan)
    await show_plan(msg, msg.from_user.id, lang)


@router.callback_query(F.data == "dp:wdev")
async def cb_wdev(cb: CallbackQuery, state: FSMContext, lang: str):
    p = _PLANS.get(cb.from_user.id)
    if p:
        p.enable_workers_dev = not p.enable_workers_dev
        await state.set_state(Deploy.plan)
        await show_plan(cb, cb.from_user.id, lang)


# ------------------------------------------------------------------ step 6: execute
@router.callback_query(F.data == "dp:go")
async def cb_go(cb: CallbackQuery, state: FSMContext, app: AppContext, lang: str):
    tg_id = cb.from_user.id
    p, b = _PLANS.get(tg_id), _BUNDLES.get(tg_id)
    data = await state.get_data()
    if not p or not b or p.pending or b.analysis.blockers:
        return
    await state.clear()
    job_id = data.get("job_id")
    status = await edit_or_send(cb, t(lang, "dp_starting", name=esc(p.worker)))

    async def progress(m: str):
        if job_id:
            await app.db.job_step(job_id, m, True)
        if status:
            await app.notifier.edit(cb.message.chat.id, status.message_id, t(lang, "dp_progress", msg=esc(m)), min_interval=0.3)

    cf = await app.cf(tg_id)
    if not cf:
        return
    try:
        report = await execute(cf, p, b.modules, progress=progress, service_worker=b.analysis.format == "service_worker")
    except CloudflareError as e:
        if job_id:
            await app.db.finish_job(job_id, "failed")
        await app.notifier.step(tg_id, t(lang, "dp_fail", error=esc(e.message)) + "\n" + cf_err(lang, e), job_id=job_id, ok=False)
        await app.notifier.send(tg_id, "↩️", markup=plan_kb(lang, p, []), store=False)
        await state.set_state(Deploy.plan)
        await state.update_data(worker=p.worker, job_id=job_id)
        return
    finally:
        await cf.aclose()
    _BUNDLES.pop(tg_id, None)
    _PLANS.pop(tg_id, None)
    if job_id:
        await app.db.finish_job(job_id, "done")
    app.worker_cache.pop(tg_id, None)
    created = "\n".join(f"🆕 {esc(c['kind'].upper())} <code>{esc(c['name'])}</code> → {esc(c['binding'])}" for c in report["created"]) or "—"
    binds = ", ".join(f"{esc(x['name'])}({esc(x['type'])})" for x in report["bindings"]) or "—"
    text = t(lang, "dp_done", name=esc(p.worker), url=esc(report.get("url") or "—"), created=created, bindings=binds,
             crons=esc(", ".join(report.get("crons") or []) or "—"))
    if report.get("warnings"):
        text += "\n" + "\n".join(f"⚠️ {esc(w)}" for w in report["warnings"])
    r = nid(p.worker)
    kb = rows([ib(t(lang, "btn_open_card"), f"wk:card:{r}"), ib(t(lang, "btn_w_test"), f"ops:test:{r}")],
              [ib(t(lang, "btn_menu"), "menu:home")])
    await app.notifier.step(tg_id, text, job_id=None)
    await app.notifier.send(tg_id, "👇", markup=kb, store=False)


def plan_for_tests(tg_id: int) -> Plan | None:
    return _PLANS.get(tg_id)
