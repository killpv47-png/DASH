"""Docs button: architecture, Workers, tokens, AI, commands, security — EN and FA (other languages get EN)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ...i18n import t
from ..app import AppContext
from ..keyboards import ib, rows
from ..utils import edit_or_send
from .router_bridge import entry

router = Router(name="help")

DOCS = {
    "en": {
        "home": (
            "📖 <b>Cloudflare Control Bot — Documentation</b>\n\n"
            "Manage your Cloudflare account from Telegram — above all <b>Workers</b>: create, deploy code (with automatic "
            "analysis of what the code needs), secrets & variables, KV / D1 / R2 / Queues, cron triggers, routes, custom "
            "domains, deployments & rollback, metrics — plus <b>CLOUDFLARE_AI</b>, an agent that can do all of it for you.\n\n"
            "Pick a section:"
        ),
        "arch": (
            "🏗 <b>Architecture</b>\n\n"
            "<b>Runtime</b>: Python 3.12 · aiogram 3 · SQLite (WAL + FTS5) · httpx → Cloudflare API v4\n\n"
            "• <code>cloudflare/client.py</code> API client (token or Global Key, retry, 429 handling)\n"
            "• <code>cloudflare/analyzer.py</code> reads your code: handlers, every <code>env.X</code> → binding type\n"
            "• <code>cloudflare/deployer.py</code> plan → create KV/D1/R2/Queue → upload → crons → workers.dev\n"
            "• <code>cloudflare/tokens.py</code> token presets with official template links\n"
            "• <code>telegram/</code> handlers · <code>ai/</code> CLOUDFLARE_AI · <code>lifecycle/</code> checkpoint + self-restart\n\n"
            "<b>Access levels</b>: 👑 GOD · 🏛 ARCHITECT · 🛠 ENGINEER · 👁 OBSERVER · 👻 GHOST — computed from the token's "
            "permissions (exact when the token has <i>API Tokens Read</i>, otherwise probed).\n\n"
            "<b>Hosting</b>: the bot can run as a long job on GitHub Actions; before the 6h limit it checkpoints its encrypted "
            "DB to the host repo and starts a new run (HOST_PAT). This is only hosting — no GitHub features are exposed."
        ),
        "workers": (
            "⚡ <b>Workers</b>\n\n"
            "<b>Deploy</b>: 🚀 Deploy → pick a Worker or new → send a <code>.js/.mjs/.py</code> file, a <code>.zip</code> "
            "project (wrangler.toml/json is read) or paste the code.\n"
            "The bot shows the <b>analysis</b>: handlers (fetch / scheduled / queue…), each binding the code uses and its type, "
            "Node compat, blockers (npm imports must be bundled, TypeScript compiled).\n"
            "Then the <b>plan</b>: for each binding choose 🆕 create (KV / D1 / R2 / Queue are created for you), 🔗 link an "
            "existing one, ✏️ enter a value (vars / secrets — secret messages are deleted), or ⏭ skip. Existing bindings and "
            "secrets of an updated Worker are kept.\n\n"
            "<b>Manage</b>: card (URL, bindings, crons) · code view + ZIP download · secrets & vars · bindings · deployments "
            "& rollback · cron triggers · routes & custom domains · test request · metrics · settings (workers.dev, logpush, "
            "observability, compatibility date, nodejs_compat) · delete."
        ),
        "tokens": (
            "🔑 <b>Tokens</b>\n\n"
            "Use 🔑 Token guide: each preset opens the official Cloudflare page with the permissions pre-filled "
            "(user-owned or account-owned token). Presets: Full · Workers deploy · Workers + Storage · Routes & Domains · Read only.\n\n"
            "<b>“GID / all access”</b>: Cloudflare has no credential called GID. Real options: the <b>Full</b> preset "
            "(recommended: scoped, revocable, can expire) or the legacy <b>Global API Key</b> (email + key; every permission "
            "on every account, cannot be limited — highest risk).\n\n"
            "Tokens are verified (<code>/user/tokens/verify</code> or <code>/accounts/{id}/tokens/verify</code>) and stored "
            "encrypted."
        ),
        "ai": (
            "🤖 <b>CLOUDFLARE_AI</b>\n\n"
            "<b>Setup</b>: BASE_URL → API_KEY → pick a model (any OpenAI-compatible provider).\n\n"
            "<b>Tools</b>: cloudflare_api (Workers, analyze, deploy, secrets, vars, crons, routes, domains, deployments, "
            "rollback, metrics, KV, D1 SQL, R2, Queues, raw) · cloudflare_docs (official docs as Markdown) · terminal · files · "
            "web search (Tavily) · memory · skills · todo · session search · Telegram files.\n\n"
            "Rules it follows: analyze before deploy, never invent secret values or ids, confirm destructive actions, verify "
            "after deploying. Rate limits → waits and resumes the same step; survives restarts."
        ),
        "cmds": (
            "⌨️ <b>Commands</b>\n\n"
            "/start · /menu · /lang · /token (token guide) · /scan\n"
            "/workers · /worker &lt;name&gt; · /newworker · /deploy [name]\n"
            "/secrets [name] · /storage · /metrics [name]\n"
            "/ai &lt;text&gt; · /ai_new · /ai_stop · /ai_setup\n"
            "/notifications · /settings · /restart · /help · /cancel\n\n"
            "Everything is also reachable from the reply keyboard and inline buttons. With CLOUDFLARE_AI configured, any "
            "plain text goes to the agent."
        ),
        "sec": (
            "🔒 <b>Security</b>\n\n"
            "• Cloudflare credentials are encrypted (AES-256-GCM, scrypt from STATE_KEY); the whole DB is encrypted again "
            "before a checkpoint leaves the runner.\n"
            "• Messages with tokens / secret values are deleted right after reading; secret values never touch the DB.\n"
            "• Every message, log line and AI output passes a redactor (Cloudflare tokens, Global API Key, bot token…).\n"
            "• Prefer least-privilege presets; the Global API Key cannot be scoped.\n"
            "• Owner lock (OWNER_IDS or first user). Destructive actions require typing the name or confirming."
        ),
    },
    "fa": {
        "home": (
            "📖 <b>ربات مدیریت Cloudflare — راهنما</b>\n\n"
            "مدیریت اکانت Cloudflare از داخل تلگرام — به‌خصوص <b>Workers</b>: ساخت، دیپلوی کد (با تحلیل خودکار نیازهای کد)، "
            "Secrets و Variables، KV / D1 / R2 / Queues، Cron، Route و دامنهٔ اختصاصی، نسخه‌ها و Rollback، آمار — به‌همراه "
            "<b>CLOUDFLARE_AI</b> که همهٔ این کارها را می‌تواند برایتان انجام دهد.\n\n"
            "یک بخش انتخاب کنید:"
        ),
        "arch": (
            "🏗 <b>معماری</b>\n\n"
            "<b>محیط اجرا</b>: Python 3.12 · aiogram 3 · SQLite · httpx → Cloudflare API v4\n\n"
            "• <code>cloudflare/client.py</code> کلاینت API (توکن یا Global Key، تلاش مجدد، مدیریت 429)\n"
            "• <code>cloudflare/analyzer.py</code> تحلیل کد: هندلرها، هر <code>env.X</code> ← نوع Binding\n"
            "• <code>cloudflare/deployer.py</code> برنامه ← ساخت KV/D1/R2/Queue ← آپلود ← Cron ← workers.dev\n"
            "• <code>cloudflare/tokens.py</code> قالب‌های توکن با لینک رسمی\n"
            "• <code>telegram/</code> هندلرها · <code>ai/</code> CLOUDFLARE_AI · <code>lifecycle/</code> ذخیره و ری‌استارت خودکار\n\n"
            "<b>سطوح دسترسی</b>: 👑 GOD · 🏛 ARCHITECT · 🛠 ENGINEER · 👁 OBSERVER · 👻 GHOST — از مجوزهای توکن محاسبه می‌شود.\n\n"
            "<b>میزبانی</b>: ربات می‌تواند به‌صورت یک جاب طولانی روی GitHub Actions اجرا شود و قبل از سقف ۶ ساعت، دیتابیس "
            "رمزنگاری‌شده را ذخیره و اجرای بعدی را شروع کند (HOST_PAT). این فقط محل اجراست؛ قابلیت گیت‌هابی در ربات نیست."
        ),
        "workers": (
            "⚡ <b>Workers</b>\n\n"
            "<b>دیپلوی</b>: 🚀 دیپلوی ← انتخاب Worker یا جدید ← ارسال فایل <code>.js/.mjs/.py</code>، پروژهٔ <code>.zip</code> "
            "(wrangler.toml/json خوانده می‌شود) یا پیست کد.\n"
            "ربات <b>تحلیل</b> را نشان می‌دهد: هندلرها، هر Binding و نوعش، نیاز به Node، موانع (پکیج npm باید باندل شود، "
            "TypeScript باید کامپایل شود).\n"
            "سپس <b>برنامه</b>: برای هر Binding ‏🆕 ساخت (KV / D1 / R2 / Queue خودکار ساخته می‌شود)، 🔗 اتصال به منبع موجود، "
            "✏️ وارد کردن مقدار (Variable / Secret — پیام Secret پاک می‌شود) یا ⏭ رد کردن. Bindingها و Secretهای فعلی "
            "Worker هنگام آپدیت حفظ می‌شوند.\n\n"
            "<b>مدیریت</b>: کارت (آدرس، Bindingها، Cron) · مشاهده و دانلود کد · Secret و Variable · Bindingها · نسخه‌ها و "
            "Rollback · Cron · Route و دامنه · تست درخواست · آمار · تنظیمات (workers.dev، logpush، observability، "
            "compatibility date، nodejs_compat) · حذف."
        ),
        "tokens": (
            "🔑 <b>توکن‌ها</b>\n\n"
            "از 🔑 راهنمای توکن استفاده کنید: هر گزینه صفحهٔ رسمی Cloudflare را با مجوزهای از پیش انتخاب‌شده باز می‌کند "
            "(توکن کاربری یا توکن اکانت). گزینه‌ها: کامل · دیپلوی Workers · ‏Workers + ذخیره‌سازی · Route و دامنه · فقط‌خواندنی.\n\n"
            "<b>«توکن GID با همهٔ دسترسی‌ها»</b>: در Cloudflare اعتباری به نام GID وجود ندارد. گزینه‌های واقعی: قالب <b>کامل</b> "
            "(پیشنهادی: محدودپذیر، قابل لغو، تاریخ انقضا) یا <b>Global API Key</b> قدیمی (ایمیل + کلید؛ همهٔ دسترسی‌ها روی همهٔ "
            "اکانت‌ها، غیرقابل محدودسازی — بیشترین ریسک).\n\n"
            "توکن‌ها اعتبارسنجی و رمزنگاری‌شده ذخیره می‌شوند."
        ),
        "ai": (
            "🤖 <b>CLOUDFLARE_AI</b>\n\n"
            "<b>راه‌اندازی</b>: BASE_URL ← API_KEY ← انتخاب مدل (هر سرویس سازگار با OpenAI).\n\n"
            "<b>ابزارها</b>: cloudflare_api (Workers، تحلیل، دیپلوی، Secret، Variable، Cron، Route، دامنه، نسخه‌ها، Rollback، "
            "آمار، KV، SQL روی D1، R2، Queues، raw) · cloudflare_docs (مستندات رسمی) · ترمینال · فایل‌ها · جست‌وجوی وب · حافظه · "
            "مهارت‌ها · todo · جست‌وجوی نشست‌ها · فایل‌های تلگرام.\n\n"
            "قواعد: قبل از دیپلوی تحلیل، هیچ مقدار Secret یا شناسه‌ای را حدس نمی‌زند، برای کارهای مخرب تأیید می‌گیرد، بعد از "
            "دیپلوی بررسی می‌کند. در محدودیت نرخ صبر و ادامه می‌دهد؛ ری‌استارت را هم تحمل می‌کند."
        ),
        "cmds": (
            "⌨️ <b>دستورات</b>\n\n"
            "/start · /menu · /lang · /token (راهنمای توکن) · /scan\n"
            "/workers · /worker &lt;نام&gt; · /newworker · /deploy [نام]\n"
            "/secrets [نام] · /storage · /metrics [نام]\n"
            "/ai &lt;متن&gt; · /ai_new · /ai_stop · /ai_setup\n"
            "/notifications · /settings · /restart · /help · /cancel\n\n"
            "همه از کیبورد پایین و دکمه‌های شیشه‌ای هم در دسترس‌اند. وقتی CLOUDFLARE_AI تنظیم شده باشد، هر متن ساده به ایجنت می‌رود."
        ),
        "sec": (
            "🔒 <b>امنیت</b>\n\n"
            "• اعتبارهای Cloudflare رمزنگاری می‌شوند (AES-256-GCM با کلید STATE_KEY)؛ کل دیتابیس هم قبل از ذخیره دوباره رمز می‌شود.\n"
            "• پیام‌های حاوی توکن / مقدار Secret بلافاصله پاک می‌شوند؛ مقدار Secret هرگز در دیتابیس ذخیره نمی‌شود.\n"
            "• همهٔ پیام‌ها، لاگ‌ها و خروجی AI از فیلتر حذف اطلاعات حساس عبور می‌کنند.\n"
            "• از قالب‌های با کمترین دسترسی استفاده کنید؛ Global API Key محدودشدنی نیست.\n"
            "• قفل مالک (OWNER_IDS یا اولین کاربر). عملیات مخرب نیاز به تایپ نام یا تأیید دارد."
        ),
    },
}

SECTIONS = ("arch", "workers", "tokens", "ai", "cmds", "sec")


def _docs(lang: str) -> dict:
    return DOCS.get(lang, DOCS["en"])


def _kb(lang: str):
    return rows(
        [ib(t(lang, "btn_help_arch"), "help:arch"), ib(t(lang, "btn_help_workers"), "help:workers")],
        [ib(t(lang, "btn_help_tokens"), "help:tokens"), ib(t(lang, "btn_help_ai"), "help:ai")],
        [ib(t(lang, "btn_help_cmds"), "help:cmds"), ib(t(lang, "btn_help_security"), "help:sec")],
        [ib(t(lang, "btn_menu"), "menu:home")],
    )


@entry("help:home")
async def entry_help(msg: Message, app: AppContext, lang: str, state: FSMContext):
    await msg.answer(_docs(lang)["home"], reply_markup=_kb(lang), parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(msg: Message, lang: str):
    await msg.answer(_docs(lang)["home"], reply_markup=_kb(lang), parse_mode="HTML")


@router.callback_query(F.data.startswith("help:"))
async def cb_help(cb: CallbackQuery, lang: str):
    section = cb.data.split(":")[1]
    await edit_or_send(cb, _docs(lang).get(section, _docs(lang)["home"]), _kb(lang))
