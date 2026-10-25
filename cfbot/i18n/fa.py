STRINGS = {
    # --- شروع / زبان
    "choose_lang": "🌐 <b>Choose your language</b>\nزبان خود را انتخاب کنید",
    "lang_set": "✅ زبان روی <b>{lang}</b> تنظیم شد.",
    "welcome": (
        "👋 <b>به ربات مدیریت Cloudflare خوش آمدید</b>\n\n"
        "اکانت Cloudflare خود را از تلگرام مدیریت کنید — به‌خصوص <b>Workers</b>: ساخت، دیپلوی کد با تحلیل خودکار نیازها، "
        "Secret و Variable، ‏KV / D1 / R2 / Queues، ‏Cron، ‏Route، دامنه، Rollback و آمار — به‌همراه <b>CLOUDFLARE_AI</b> "
        "که همهٔ این کارها را برایتان انجام می‌دهد.\n\n"
        "🔑 برای شروع یک <b>API Token کلودفلر</b> وصل کنید. یکی از گزینه‌های زیر را بزنید: صفحهٔ رسمی Cloudflare با مجوزهای "
        "از پیش انتخاب‌شده باز می‌شود. توکن را آنجا بسازید، کپی کنید و اینجا بفرستید.\n\n"
        "🔒 اعتبار شما قبل از ذخیره با AES-256-GCM رمزنگاری می‌شود و دیگر نمایش داده نمی‌شود."
    ),
    "send_token": "🔑 حالا <b>API Token</b> کلودفلر را بفرستید (یا <b>Global API Key</b> — که بعدش ایمیل اکانت را می‌پرسم).\n<i>پیام بلافاصله پس از خواندن پاک می‌شود.</i>",
    "token_invalid": "❌ این شبیه API Token کلودفلر (۴۰+ کاراکتر) یا Global API Key (۳۷ کاراکتر هگز) نیست. دوباره بفرستید یا یک گزینه انتخاب کنید.",
    "token_checking": "🔍 در حال اعتبارسنجی با Cloudflare و اسکن اکانت…",
    "token_bad": "❌ Cloudflare اعتبار را رد کرد: <code>{error}</code>\n{hint}\nیک اعتبار دیگر بفرستید یا گزینه‌ای انتخاب کنید.",
    "token_saved": "✅ اعتبار (رمزنگاری‌شده) ذخیره شد — نوع: <b>{kind}</b>.",
    "kind_user": "توکن کاربری",
    "kind_account": "توکن اکانت",
    "kind_global_key": "Global API Key (دسترسی کامل)",
    "gk_detected": "🗝 این شبیه <b>Global API Key</b> است. <b>ایمیل</b> ورود به Cloudflare را بفرستید (همراه این کلید الزامی است).",
    "gk_ask_email": "🗝 <b>Global API Key</b>\nمرحلهٔ ۱ از ۲ — <b>ایمیل</b> اکانت Cloudflare را بفرستید:",
    "gk_ask_key": "مرحلهٔ ۲ از ۲ — <b>Global API Key</b> را بفرستید (۳۷ کاراکتر هگز).\n<i>پیام بلافاصله پاک می‌شود.</i>",
    "gk_email_bad": "❌ ایمیل معتبر نیست.",
    "gk_key_bad": "❌ Global API Key دقیقاً ۳۷ کاراکتر هگز کوچک است.",
    "not_owner": "⛔ این ربات خصوصی است. شناسهٔ تلگرام شما <code>{id}</code> مجاز نیست.",

    # --- راهنمای توکن
    "tok_home": (
        "🔑 <b>راهنمای ساخت توکن Cloudflare</b>\n\n"
        "مشخص کنید ربات چه کارهایی مجاز باشد. هر گزینه <b>صفحهٔ رسمی ساخت توکن Cloudflare</b> را با مجوزهای از پیش انتخاب‌شده "
        "باز می‌کند — بررسی کنید، <i>Continue to summary ← Create Token</i> را بزنید، توکن را کپی و اینجا ارسال کنید.\n\n"
        "• <b>کامل</b> — همهٔ قابلیت‌های ربات (اگر همه چیز را می‌خواهید)\n"
        "• <b>دیپلوی Workers</b> — فقط اسکریپت‌های Workers (حداقل برای دیپلوی)\n"
        "• <b>Workers + ذخیره‌سازی</b> — Workers به‌همراه KV، D1، R2، Queues و آمار\n"
        "• <b>Route و دامنه</b> — اتصال Worker به دامنه‌های خودتان\n"
        "• <b>فقط‌خواندنی</b> — مشاهده، بدون تغییر\n"
        "• <b>Global API Key</b> — کلید قدیمی با همهٔ دسترسی‌ها (توصیه نمی‌شود)\n\n"
        "<i>در Cloudflare اعتباری به نام «GID» وجود ندارد؛ نزدیک‌ترین گزینه‌های واقعی، قالب «کامل» یا Global API Key است.</i>"
    ),
    "tok_btn_full": "👑 دسترسی کامل (همهٔ قابلیت‌ها)",
    "tok_btn_workers": "⚡ دیپلوی Workers",
    "tok_btn_storage": "🗄 Workers + ذخیره‌سازی",
    "tok_btn_routes": "🌐 Route و دامنه",
    "tok_btn_readonly": "👁 فقط‌خواندنی",
    "tok_btn_global": "🗝 Global API Key (همهٔ دسترسی‌ها)",
    "tok_btn_matrix": "📋 هر قابلیت چه مجوزی لازم دارد",
    "tok_btn_paste": "📥 توکن دارم — ارسال می‌کنم",
    "tok_preset": (
        "{title}\n\n{desc}\n\n<b>مجوزها</b> (در صفحهٔ Cloudflare از قبل انتخاب شده‌اند):\n{perms}\n\n"
        "<b>ریسک</b>: {risk}\n\n"
        "1️⃣ لینک را باز کنید (توکن کاربری = متعلق به شما؛ توکن اکانت = متعلق به اکانت و مستقل از اعضا)\n"
        "2️⃣ در صورت تمایل اکانت/زون را محدود کنید و IP و تاریخ انقضا بگذارید\n"
        "3️⃣ بسازید ← کپی کنید ← «ارسال می‌کنم» را بزنید و توکن را بفرستید"
    ),
    "tok_full": "همهٔ مجوزهای Workers، ذخیره‌سازی، Pages، ‏Route و DNS که ربات استفاده می‌کند، به‌علاوهٔ خواندن تنظیمات اکانت، آمار و مجوزهای خود توکن (تا ربات دقیقاً بداند چه اجازه‌ای دارد).",
    "tok_workers": "حداقل لازم برای مشاهده، دیپلوی، پیکربندی و حذف Workers (Secret، Variable، Cron، Rollback). بدون ساخت منابع ذخیره‌سازی.",
    "tok_storage": "دیپلوی Workers و ساخت/اتصال خودکار KV، ‏D1، ‏R2 و Queues؛ مشاهدهٔ آمار.",
    "tok_routes": "اتصال Workers به Route و دامنهٔ اختصاصی روی زون‌های شما (برای دامنهٔ اختصاصی ویرایش DNS لازم است).",
    "tok_readonly": "مشاهدهٔ Workers، ذخیره‌سازی، زون‌ها و آمار. هیچ تغییری ممکن نیست — امن‌ترین گزینه برای پایش.",
    "risk_low": "🟢 کم — فقط خواندن",
    "risk_medium": "🟡 متوسط — امکان تغییر منابع فهرست‌شده",
    "risk_high": "🔴 زیاد — امکان تغییر و حذف Workers، ذخیره‌سازی و DNS. در صورت امکان اکانت/زون را محدود و تاریخ انقضا تعیین کنید.",
    "tok_open_user": "🔗 ساخت توکن کاربری (صفحهٔ رسمی)",
    "tok_open_account": "🏢 ساخت توکن اکانت (صفحهٔ رسمی)",
    "tok_matrix": "📋 <b>قابلیت ← مجوز لازم</b>\n\n{list}\n\nمرجع رسمی: {docs}",
    "tok_global": (
        "🗝 <b>Global API Key</b>\n\n"
        "کلید قدیمی کاربر Cloudflare: <b>همهٔ دسترسی‌ها روی همهٔ اکانت‌هایی</b> که عضوشان هستید. قابل محدودسازی، فیلتر IP یا "
        "تاریخ انقضا نیست و باید همراه ایمیل ورود ارسال شود.\n\n"
        "🔴 بیشترین ریسک — قالب توکن <b>دسترسی کامل</b> را ترجیح دهید. فقط اگر ریسک را می‌پذیرید استفاده کنید و در صورت لو رفتن "
        "از همان صفحه آن را عوض کنید.\n\n"
        "محل: My Profile ← API Tokens ← <i>Global API Key</i> ← View.\nمستندات: {docs}"
    ),
    "tok_open_gk": "🔗 باز کردن صفحهٔ API Tokens",
    "tok_gk_use": "🗝 متوجهم — از Global API Key استفاده می‌کنم",

    # --- اسکن
    "scan_step": "⏳ در حال اسکن: <b>{step}</b>…",
    "scan_report": (
        "📊 <b>اسکن اکانت Cloudflare</b>\n\n"
        "👤 {email} · {kind}\n"
        "🏢 اکانت: <b>{account}</b> ({accounts} اکانت قابل مشاهده)\n"
        "⚡ Workers: <b>{workers}</b> · workers.dev: <code>{subdomain}</code>\n"
        "🗂 KV {kv} · 🗄 D1 {d1} · 🪣 R2 {r2} · 📨 Queues {queues} · 🌐 زون‌ها {zones}\n"
        "⏳ انقضای توکن: {expires}\n\n"
        "🔐 <b>سطح دسترسی: {level_emoji} {level}</b>\n<i>{level_desc}</i>\n"
        "🧾 توانایی‌ها ({exact}): {caps}"
    ),
    "scan_perms": "🧾 مجوزهای توکن: <code>{perms}</code>",
    "caps_exact": "دقیق، از سیاست‌های خود توکن",
    "caps_probed": "تخمینی — دسترسی نوشتن در اولین استفاده تأیید می‌شود",
    "scan_errors": "⚠️ اسکن ناقص: {errors}",
    "access_god": "GOD — کنترل کامل: Workers، همهٔ ذخیره‌سازی‌ها، Route و DNS. با احتیاط استفاده کنید.",
    "access_architect": "ARCHITECT — دیپلوی Workers و ساخت/اتصال ذخیره‌سازی (KV / D1 / R2 / Queues).",
    "access_engineer": "ENGINEER — دیپلوی و پیکربندی Workers (کد، Secret، Variable، Cron). بدون ساخت ذخیره‌سازی.",
    "access_observer": "OBSERVER — فقط خواندن.",
    "access_ghost": "GHOST — اعتبار کار می‌کند اما هیچ مجوزی برای Workers یا ذخیره‌سازی ندارد.",
    "access_level": "سطح دسترسی",

    # --- منوی اصلی
    "menu_title": "🏠 <b>منوی اصلی</b> — {account} {level_emoji}\nیک گزینه انتخاب کنید:",
    "btn_workers": "⚡ ورکرها",
    "btn_new_worker": "➕ ورکر جدید",
    "btn_deploy": "🚀 دیپلوی کد",
    "btn_storage": "🗄 ذخیره‌سازی",
    "btn_secrets": "🔐 سکرت‌ها",
    "btn_ai": "🤖 CLOUDFLARE_AI",
    "btn_analytics": "📈 آمار",
    "btn_scan": "📊 اسکن مجدد",
    "btn_notifs": "🔔 اعلان‌ها",
    "btn_tokens": "🔑 راهنمای توکن",
    "btn_help": "📖 راهنما",
    "btn_settings": "⚙️ تنظیمات",
    "btn_back": "⬅️ بازگشت",
    "btn_cancel": "✖️ لغو",
    "btn_yes": "✅ بله",
    "btn_no": "❌ خیر",
    "btn_menu": "🏠 منو",
    "btn_refresh": "🔄 به‌روزرسانی",
    "btn_more": "➡️ بیشتر",
    "btn_prev": "⬅️ قبلی",
    "btn_open": "📂 باز کردن",
    "cancelled": "✖️ لغو شد.",
    "need_token": "🔑 ابتدا یک توکن Cloudflare وصل کنید — /token",

    # --- ورکرها
    "workers_title": "⚡ <b>ورکرهای شما</b> ({n}) — صفحهٔ {page}/{pages}\nبرای مدیریت روی یکی بزنید:",
    "workers_empty": "📭 هنوز Workerی در این اکانت نیست. با ➕ ورکر جدید یا 🚀 دیپلوی کد بسازید.",
    "worker_card": (
        "⚡ <b>{name}</b>\n🔗 {url}\n\n"
        "هندلرها: <code>{handlers}</code>\nسازگاری: <code>{compat}</code> · فلگ‌ها: <code>{flags}</code>\n"
        "مدل مصرف: {usage} · Logpush: {logpush}\nCron: <code>{crons}</code>\n"
        "🕒 تغییر {modified} · ساخت {created}\n\n<b>Bindingها ({nb})</b>\n{bindings}"
    ),
    "btn_w_deploy": "🚀 دیپلوی کد جدید",
    "btn_w_code": "📄 کد",
    "btn_w_secrets": "🔐 سکرت و متغیر",
    "btn_w_bindings": "🧩 Bindingها",
    "btn_w_deployments": "🕘 نسخه‌ها",
    "btn_w_cron": "⏰ Cron",
    "btn_w_routes": "🌐 Route و دامنه",
    "btn_w_metrics": "📈 آمار",
    "btn_w_test": "🧪 تست درخواست",
    "btn_w_settings": "🛠 تنظیمات",
    "btn_w_watch": "🔔 پیگیری دیپلوی‌ها",
    "btn_w_unwatch": "🔕 توقف پیگیری",
    "btn_w_ai": "🤖 پرسش از AI",
    "btn_w_delete": "🗑 حذف ورکر",
    "worker_code": "📄 <b>{name}</b> — ماژول‌ها:\n{files}\n\n<b>{main}</b> (پیش‌نمایش):\n<pre>{code}</pre>",
    "worker_code_zip": "📦 سورس کامل <b>{name}</b> — ویرایش کنید و از 🚀 دیپلوی دوباره بفرستید.",
    "bindings_title": "🧩 <b>Bindingهای {name}</b>\n{list}\n\nبرای حذف ✖️ را بزنید (سکرت‌ها در بخش 🔐 مدیریت می‌شوند).",
    "btn_bind_add": "➕ اتصال KV / D1 / R2 / Queue",
    "binding_removed": "✖️ ‏Binding <code>{binding}</code> از <b>{name}</b> حذف شد.",
    "watch_on": "🔔 دیپلوی‌های جدید <b>{name}</b> به شما اطلاع داده می‌شود.",
    "watch_off": "🔕 پیگیری <b>{name}</b> متوقف شد.",
    "watch_event": "🔔 <b>{worker}</b> — دیپلوی جدید\nمنبع: {source} · توسط {author}\nنسخه‌ها: <code>{versions}</code>\nپیام: {message}\n🕒 {when}",
    "worker_edit_title": "🛠 <b>تنظیمات {name}</b>",
    "btn_wdev_on": "🌍 روشن کردن workers.dev",
    "btn_wdev_off": "🚫 خاموش کردن workers.dev",
    "btn_logpush": "📤 تغییر logpush",
    "btn_observability": "👁 تغییر Workers Logs",
    "btn_compat": "📅 تاریخ سازگاری",
    "btn_nodecompat": "🟩 تغییر nodejs_compat",
    "ask_compat": "📅 تاریخ سازگاری جدید را بفرستید (YYYY-MM-DD):",
    "compat_bad": "❌ قالب YYYY-MM-DD را رعایت کنید.",
    "worker_updated": "✅ <b>{name}</b> به‌روز شد: {what}",
    "worker_delete_confirm": "🗑 <b>{name} حذف شود؟</b>\nکد، Bindingها، سکرت‌ها، Cron و Routeهای این Worker حذف می‌شوند. منابع ذخیره‌سازی (KV/D1/R2) حذف نمی‌شوند.\nبرای تأیید <code>{name}</code> را تایپ کنید.",
    "worker_delete_mismatch": "❌ نام مطابقت ندارد — چیزی حذف نشد.",
    "worker_deleted": "🗑 ورکر <b>{name}</b> حذف شد.",
    "worker_name_bad": "❌ نام نامعتبر: حروف کوچک انگلیسی، عدد و خط تیره، ۱ تا ۶۳ کاراکتر، بدون خط تیره در ابتدا/انتها.",

    # --- ورکر جدید
    "nw_name": "➕ <b>ورکر جدید</b>\n\nمرحلهٔ ۱ از ۲ — <b>نام</b> Worker را بفرستید (حروف کوچک، عدد، خط تیره):",
    "nw_exists": "⚠️ Workerی با نام <b>{name}</b> وجود دارد. نام دیگری بفرستید یا با 🚀 دیپلوی آن را به‌روز کنید.",
    "nw_template": "مرحلهٔ ۲ از ۲ — <b>{name}</b> را از یک قالب شروع کنید یا کد خودتان را بفرستید:",
    "btn_nw_own": "📤 آپلود / پیست کد خودم",
    "nw_tpl_chosen": "🧩 قالب <b>{title}</b> ← <b>{name}</b>. در حال تحلیل…",

    # --- دیپلوی
    "dp_pick": "🚀 <b>دیپلوی کد</b>\nWorker موردنظر برای به‌روزرسانی را انتخاب کنید یا یکی بسازید:",
    "btn_dp_new": "➕ ورکر جدید",
    "dp_ask_name": "<b>نام</b> Worker جدید را بفرستید (حروف کوچک، عدد، خط تیره):",
    "dp_send_code": (
        "📤 کد <b>{name}</b> را بفرستید:\n"
        "• فایل <code>.js</code> / <code>.mjs</code> / <code>.py</code>\n"
        "• پروژهٔ <code>.zip</code> (فایل wrangler.toml / wrangler.json خوانده می‌شود: vars، KV، D1، R2، queues، crons…)\n"
        "• یا کد را به‌صورت پیام پیست کنید\n\n"
        "قبل از هر دیپلوی، تحلیل می‌کنم و دقیقاً می‌گویم کد به چه چیزهایی نیاز دارد."
    ),
    "dp_too_big": "❌ فایل خیلی بزرگ است (حداکثر ۲۰ مگابایت از طریق تلگرام).",
    "dp_not_code": "❌ این شبیه کد Worker نیست (انتظار <code>export default {…}</code>، <code>addEventListener('fetch')</code> یا Worker پایتون).",
    "dp_bad_bundle": "❌ این فایل قابل استفاده نیست: {error}",
    "dp_analysis": (
        "🔎 <b>تحلیل کد</b>\n"
        "ورودی: <code>{main}</code> ({fmt}) · {modules} ماژول · {size}\n"
        "هندلرها: <code>{handlers}</code>\n"
        "سازگاری: <code>{compat}</code> · فلگ‌ها: <code>{flags}</code>\n"
        "Cron در پیکربندی: <code>{crons}</code> · فایل پیکربندی: <code>{config}</code>\n\n"
        "<b>نیازهای کد</b>\n{needs}"
    ),
    "dp_routes_note": "Routeهای پیکربندی ({routes}) — بعداً از 🌐 Route و دامنه اضافه کنید.",
    "dp_skipped": "⚠️ {n} فایل نادیده گرفته شد (مسیر ناامن، node_modules، حجم زیاد).",
    "plan_title": (
        "📋 <b>برنامهٔ دیپلوی — {name}</b> ({mode})\n\n{items}\n\n"
        "⏰ Cron: <code>{crons}</code> · 🌍 workers.dev: {wdev}\n\n{state}"
    ),
    "plan_new": "Worker جدید",
    "plan_update": "به‌روزرسانی — Bindingها و سکرت‌های فعلی حفظ می‌شوند",
    "plan_create": "← ساخت <code>{name}</code>",
    "plan_value_set": "← مقدار تنظیم شد",
    "plan_keep": "← حفظ مقدار فعلی",
    "plan_skip": "← رد شد (ممکن است در اجرا خطا دهد)",
    "plan_pending": "← <b>نیاز به ورودی شما</b>",
    "plan_pending_n": "❓ {n} مورد نیاز به ورودی دارد — روی آن‌ها بزنید.",
    "plan_ready": "✅ آماده است. برای ساخت منابع و آپلود <b>دیپلوی</b> را بزنید.",
    "plan_blocked": "⛔ مسدود — مشکلات فهرست‌شده در تحلیل را برطرف و کد را دوباره ارسال کنید.",
    "plan_item": "🧩 <b>{name}</b> — تشخیص داده شده: <b>{kind}</b>\n<i>{note}</i>\n{advice}\n\nچه کنم؟ (اگر تشخیص اشتباه است با ⇄ نوع را عوض کنید)",
    "btn_it_create": "🆕 ساخت جدید (خودکار)",
    "btn_it_link": "🔗 استفاده از موجود",
    "btn_it_value": "✏️ وارد کردن مقدار",
    "btn_it_as_secret": "🔐 به‌عنوان سکرت",
    "btn_it_as_var": "📝 به‌عنوان متغیر ساده",
    "btn_it_target": "⌨️ تایپ شناسه / نام",
    "btn_it_skip": "⏭ رد کردن",
    "btn_plan_cron": "⏰ تنظیم Cron",
    "btn_plan_wdev": "🌍 تغییر workers.dev",
    "btn_plan_deploy": "🚀 دیپلوی",
    "dp_ask_secret": "🔐 مقدار سکرت <code>{name}</code> را بفرستید.\n<i>پیام بلافاصله پاک می‌شود و مقدار فقط تا زمان آپلود در حافظه می‌ماند.</i>",
    "dp_ask_var": "📝 مقدار متغیر <code>{name}</code> را بفرستید:",
    "dp_ask_target": "⌨️ مقصد <code>{name}</code> ({kind}) را بفرستید: شناسهٔ KV، شناسهٔ دیتابیس D1، نام باکت R2، نام صف، نام Worker سرویس یا کلاس Durable Object:",
    "dp_pick_existing": "🔗 {kind}های موجود ({n}) — یکی را انتخاب کنید:",
    "dp_ask_cron": "⏰ عبارت‌های Cron را هر کدام در یک خط بفرستید (مثلاً <code>*/15 * * * *</code>) یا <code>-</code> برای هیچ:",
    "dp_starting": "🚀 در حال دیپلوی <b>{name}</b>…",
    "dp_progress": "🚀 {msg}",
    "dp_done": (
        "🎉 <b>{name}</b> دیپلوی شد!\n🔗 {url}\n\n<b>ساخته‌شده‌ها</b>\n{created}\n\n"
        "<b>Bindingها</b>: {bindings}\n⏰ Cron: {crons}"
    ),
    "dp_fail": "❌ دیپلوی ناموفق: <code>{error}</code>",
    "btn_open_card": "⚡ باز کردن ورکر",

    # --- سکرت‌ها
    "sec_pick": "🔐 <b>سکرت‌ها و متغیرها</b>\nیک Worker انتخاب کنید:",
    "sec_title": "🔐 <b>سکرت‌های {name}</b> ({n})\n{list}\n\nمقادیر هرگز نمایش داده نمی‌شوند (Cloudflare آن‌ها را برنمی‌گرداند).",
    "sec_item": "• <code>{name}</code>",
    "sec_none": "<i>هنوز سکرتی نیست</i>",
    "btn_sec_add": "➕ سکرت جدید",
    "btn_sec_scan": "🔎 تشخیص از روی کد",
    "btn_sec_vars": "📝 متغیرها",
    "sec_ask_name": "🔐 <b>نام سکرت</b> را بفرستید (حروف، عدد، _):",
    "sec_name_bad": "❌ نام نامعتبر. از حروف، عدد و زیرخط استفاده کنید و با حرف یا _ شروع کنید.",
    "sec_ask_value": "🔑 <b>مقدار</b> <code>{key}</code> را بفرستید.\n<i>پیام شما بلافاصله پس از خواندن پاک می‌شود.</i>",
    "sec_saved": "✅ سکرت <code>{key}</code> روی <b>{name}</b> ذخیره شد (یک دیپلوی جدید ایجاد شد).",
    "sec_deleted": "🗑 سکرت <code>{key}</code> حذف شد.",
    "sec_actions": "🔐 <code>{key}</code> روی <b>{name}</b>",
    "btn_sec_update": "✏️ تغییر مقدار",
    "btn_sec_delete": "🗑 حذف",
    "sec_detect_result": "🔎 کد دیپلوی‌شده از این‌ها استفاده می‌کند: {all}\nهنوز متصل نشده: <b>{missing}</b>\nبرای تنظیم روی هر کدام بزنید.",
    "sec_detect_none": "🔎 ماژول جاوااسکریپت/پایتونی در Worker دیپلوی‌شده پیدا نشد.",
    "vars_title": "📝 <b>متغیرهای {name}</b>\n{list}",
    "vars_item": "• <code>{key}</code> = <code>{value}</code>",
    "btn_var_add": "➕ متغیر جدید",
    "var_ask_name": "📝 <b>نام متغیر</b> را بفرستید:",
    "var_ask_value": "📝 <b>مقدار</b> <code>{key}</code> را بفرستید (در داشبورد قابل مشاهده است — برای اطلاعات محرمانه از سکرت استفاده کنید):",
    "var_saved": "✅ متغیر <code>{key}</code> ذخیره شد.",

    # --- عملیات
    "deps_title": "🕘 <b>دیپلوی‌های {name}</b>\n{deps}\n\n<b>نسخه‌ها</b> (🟢 = فعال)\n{versions}",
    "dep_item": "• {when} · {source} · {author}\n  <code>{versions}</code>",
    "ver_item": "{active} <code>{id}</code> #{n} · {when} · {source} {msg}",
    "btn_rollback": "↩️ بازگشت به {id}",
    "rollback_confirm": "↩️ نسخهٔ <code>{id}</code> از <b>{name}</b> فعال شود (۱۰۰٪ ترافیک)؟",
    "rollback_done": "↩️ <b>{name}</b> اکنون نسخهٔ <code>{id}</code> را سرویس می‌دهد.",
    "cron_title": "⏰ <b>Cronهای {name}</b>\n<code>{crons}</code>\n\nبرای جایگزینی، عبارت‌های جدید را بفرستید (هر خط یکی، به وقت UTC)، مثلاً <code>0 */6 * * *</code>.",
    "btn_cron_clear": "🧹 حذف همه",
    "cron_bad": "❌ عبارت Cron نامعتبر: <code>{bad}</code> — ۵ بخش: دقیقه ساعت روز ماه روزهفته.",
    "cron_saved": "⏰ Cron برای <b>{name}</b>: <code>{crons}</code>",
    "routes_title": "🌐 <b>Route و دامنه‌های {name}</b>\nworkers.dev: {wdev}\n\n<b>Routeها</b>\n{routes}\n\n<b>دامنه‌های اختصاصی</b>\n{domains}",
    "btn_route_add": "➕ افزودن Route",
    "btn_domain_add": "➕ افزودن دامنهٔ اختصاصی",
    "route_ask": "🛣 الگوی Route را بفرستید، مثلاً <code>example.com/api/*</code> یا <code>*.example.com/*</code> (زون باید در همین اکانت باشد):",
    "domain_ask": "🌐 نام میزبان را بفرستید، مثلاً <code>api.example.com</code> — رکورد DNS و گواهی را Cloudflare می‌سازد:",
    "zone_not_found": "❌ هیچ زونی در این اکانت با <code>{host}</code> مطابقت ندارد (یا توکن مجوز Zone Read ندارد).",
    "route_added": "✅ ‏Route <code>{pattern}</code> روی زون {zone} اضافه شد.",
    "domain_added": "✅ دامنهٔ اختصاصی <code>{host}</code> متصل شد (صدور گواهی ممکن است چند دقیقه طول بکشد).",
    "route_deleted": "🗑 ‏Route حذف شد.",
    "domain_deleted": "🗑 دامنهٔ اختصاصی جدا شد.",
    "test_ask": "🧪 مسیری برای درخواست روی workers.dev بفرستید، مثلاً <code>/</code>، <code>/api/health</code> یا <code>POST /items</code>:",
    "btn_test_root": "🧪 GET /",
    "test_result": "🧪 <b>{method}</b> {url}\nوضعیت <b>{status}</b> · {ms} میلی‌ثانیه · {ctype} · cf-ray {ray}\n<pre>{body}</pre>",
    "test_fail": "❌ درخواست به {url} ناموفق بود: <code>{error}</code>",
    "test_no_subdomain": "⚠️ این اکانت هنوز زیردامنهٔ workers.dev ندارد — از داشبورد (Workers & Pages) ثبت کنید.",
    "metrics_title": "📈 <b>آمار — {scope}</b> ({hours} ساعت اخیر)\n{list}",
    "metrics_item": "⚡ <b>{name}</b>: {req} درخواست · {err} خطا ({rate}٪) · {sub} زیردرخواست · CPU p50 {p50}ms / p99 {p99}ms",
    "metrics_none": "<i>در این بازه اجرایی ثبت نشده</i>",
    "metrics_perm": "💡 آمار به مجوز <b>Account Analytics Read</b> نیاز دارد.",
    "all_workers": "همهٔ ورکرها",

    # --- ذخیره‌سازی
    "st_home": "🗄 <b>ذخیره‌سازی</b>\nKV (کلید-مقدار) · D1 (SQL) · R2 (فایل) · Queues (صف کار)",
    "btn_zones": "🌐 زون‌ها",
    "st_list": "{kind} — {n} مورد:",
    "btn_st_create": "➕ ساخت",
    "st_ask_name": "یک نام برای {kind} جدید بفرستید:",
    "st_created": "✅ {kind} <b>{name}</b> ساخته شد (<code>{id}</code>).",
    "st_item": "{kind} <b>{ref}</b>\n\n{detail}",
    "btn_kv_get": "🔍 خواندن کلید",
    "btn_kv_put": "✏️ نوشتن کلید",
    "kv_ask_key": "🔑 نام کلید را بفرستید:",
    "kv_ask_value": "✏️ مقدار را بفرستید:",
    "kv_value": "🔑 <code>{key}</code>\n<pre>{value}</pre>",
    "kv_saved": "✅ کلید <code>{key}</code> ذخیره شد.",
    "btn_d1_sql": "🧮 اجرای SQL",
    "btn_d1_more": "🧮 کوئری دیگر",
    "d1_ask_sql": "🧮 یک دستور SQL بفرستید (نحو SQLite). دستورهای مخرب بلافاصله اجرا می‌شوند — مراقب باشید.",
    "d1_result": "🧮 <code>{sql}</code>\n<pre>{out}</pre>",
    "btn_bind_worker": "🧩 اتصال به یک ورکر",
    "btn_st_delete": "🗑 حذف",
    "st_delete_confirm": "🗑 {kind} <b>{name}</b> و همهٔ داده‌هایش حذف شود؟ برای تأیید <code>{name}</code> را تایپ کنید.",
    "st_deleted": "🗑 <b>{name}</b> حذف شد.",
    "st_pick_worker": "🧩 به کدام Worker متصل شود؟",
    "st_pick_kind": "🧩 چه چیزی را متصل می‌کنید؟",
    "st_ask_binding": "🧩 نام Bindingی که کد استفاده می‌کند را بفرستید (مثلاً <code>DB</code>، <code>CACHE</code>، <code>BUCKET</code>):",
    "st_bound": "✅ <code>{binding}</code> به <b>{worker}</b> متصل شد (یک دیپلوی جدید ایجاد شد).",
    "zones_title": "🌐 <b>زون‌ها</b> ({n})\n{list}",

    # --- اعلان‌ها
    "notif_title": "🔔 <b>اعلان‌های اخیر</b>\n{list}",
    "notif_none": "<i>هنوز اعلانی نیست</i>",
    "notif_item": "<code>{time}</code> {text}",
    "jobs_title": "🧾 <b>کارهای اخیر</b>\n{list}",
    "job_item": "{icon} <b>{title}</b> — {status} ({steps} مرحله)",

    # --- تنظیمات
    "settings_title": (
        "⚙️ <b>تنظیمات</b>\n"
        "زبان: {lang}\nCloudflare: {email} · اکانت <b>{account}</b> ({level})\nAI: {ai}\nورکرهای تحت پیگیری: {watches}\n"
        "محیط اجرا: {runtime}"
    ),
    "btn_change_lang": "🌐 زبان",
    "btn_change_token": "🔑 تغییر توکن Cloudflare",
    "btn_switch_account": "🏢 تغییر اکانت / اسکن مجدد",
    "btn_forget_token": "🧹 حذف اعتبار من",
    "forget_confirm": "🧹 اعتبار Cloudflare ذخیره‌شده از ربات حذف شود؟ (در خود Cloudflare معتبر می‌ماند — در صورت نیاز از داشبورد لغوش کنید.)",
    "forget_done": "🧹 اعتبار حذف شد. برای اتصال دوباره /token را بزنید.",
    "btn_ai_reset": "🤖 پیکربندی مجدد AI",
    "btn_export": "💾 ذخیرهٔ وضعیت",
    "btn_restart": "♻️ ری‌استارت ربات (اجرای جدید)",
    "export_done": "💾 نقطهٔ بازیابی ذخیره شد.",
    "export_fail": "❌ ذخیرهٔ وضعیت ناموفق: {error}",
    "restart_confirm": "♻️ الان به یک اجرای جدید منتقل شوم؟ چیزی از دست نمی‌رود — اول وضعیت ذخیره می‌شود.",
    "restart_go": "♻️ در حال انتقال… حدود ۳۰ تا ۶۰ ثانیه دیگر از اجرای جدید پیام می‌دهم.",
    "restart_not_actions": "ℹ️ ربات روی میزبانی GitHub Actions اجرا نمی‌شود — ری‌استارت یعنی اجرای مجدد پروسه محلی.",

    # --- چرخهٔ حیات
    "lifecycle_hello": "🟢 <b>ربات آنلاین شد</b> — اجرای <code>#{run}</code> (تلاش {attempt}).\nبازیابی وضعیت: {restored}. سقف زمان اجرا: {minutes} دقیقه.",
    "lifecycle_bye": "🟠 به سقف زمان اجرا رسیدم. ذخیرهٔ وضعیت و شروع اجرای جدید… حدود ۱ دقیقه دیگر برمی‌گردم.",
    "lifecycle_resume_ai": "♻️ ادامهٔ کار نیمه‌تمام CLOUDFLARE_AI از همان نقطه…",
    "lifecycle_no_pat": "⚠️ سکرت <code>HOST_PAT</code> تنظیم نشده — نمی‌توانم وضعیت را ذخیره یا خودم را روی میزبان ری‌استارت کنم. آن را در سکرت‌های ریپوی میزبان تنظیم کنید.",

    # --- AI
    "ai_setup_base": (
        "🤖 <b>راه‌اندازی CLOUDFLARE_AI</b>\n\nمرحلهٔ ۱ از ۳ — <b>BASE_URL</b> یک API سازگار با OpenAI را بفرستید "
        "(مثلاً <code>https://api.openai.com/v1</code>، <code>https://openrouter.ai/api/v1</code>):"
    ),
    "ai_setup_key": "مرحلهٔ ۲ از ۳ — <b>API_KEY</b> را بفرستید.\n<i>پیام پس از خواندن پاک می‌شود.</i>",
    "ai_fetching_models": "🔎 دریافت فهرست مدل‌ها از <code>{base}</code>…",
    "ai_models_fail": "❌ فهرست مدل‌ها دریافت نشد: <code>{error}</code>\nنام مدل را دستی بفرستید یا /cancel.",
    "ai_pick_model": "مرحلهٔ ۳ از ۳ — یک <b>مدل</b> انتخاب کنید ({n} مدل، صفحهٔ {page}/{pages}) یا نامش را بفرستید:",
    "ai_ready": "✅ CLOUDFLARE_AI آماده است.\nBase: <code>{base}</code>\nمدل: <code>{model}</code>\n\nهر سؤالی دربارهٔ Workers دارید بپرسید — می‌توانم تحلیل، دیپلوی و پیکربندی کنم.",
    "ai_home": (
        "🤖 <b>CLOUDFLARE_AI</b> — مدل <code>{model}</code>\n"
        "نشست: <code>{session}</code> · {msgs} پیام · {compressions} فشرده‌سازی\n"
        "حافظه: {mem} مورد · مهارت‌ها: {skills}\n\n"
        "درخواستتان را بنویسید. ابزارها: Cloudflare API، مستندات رسمی، ترمینال، فایل‌ها، جست‌وجوی وب{search}، حافظه، مهارت‌ها، todo."
    ),
    "btn_ai_new": "🆕 نشست جدید",
    "btn_ai_sessions": "🗂 نشست‌ها",
    "btn_ai_memory": "🧠 حافظه",
    "btn_ai_skills": "🧩 مهارت‌ها",
    "btn_ai_model": "🔄 تغییر مدل",
    "btn_ai_stop": "⏹ توقف",
    "ai_new_session": "🆕 نشست جدید <code>{id}</code> شروع شد.",
    "ai_thinking": "🤖 در حال فکر کردن…",
    "ai_tool_call": "🔧 <code>{tool}</code> {args}",
    "ai_tool_result": "↩️ {tool}: {summary}",
    "ai_rate_limited": "⏳ محدودیت نرخ مدل — {secs} ثانیه صبر و سپس ادامهٔ همان مرحله (تلاش {n}).",
    "ai_api_error": "⚠️ خطای API: <code>{error}</code> — تلاش مجدد پس از {secs} ثانیه.",
    "ai_compressing": "🗜 کانتکست بزرگ شده — فشرده‌سازی نوبت‌های قدیمی (چیزی از دست نمی‌رود؛ خلاصه جایگزین می‌شود).",
    "ai_done": "✅ انجام شد ({iters} مرحله، {tools} فراخوانی ابزار).",
    "ai_stopped": "⏹ متوقف شد.",
    "ai_busy": "⏳ CLOUDFLARE_AI هنوز روی درخواست قبلی کار می‌کند. برای قطع، توقف را بزنید.",
    "ai_not_configured": "🤖 CLOUDFLARE_AI هنوز پیکربندی نشده. روی 🤖 CLOUDFLARE_AI بزنید تا BASE_URL، API_KEY و مدل را تنظیم کنید.",
    "ai_sessions_title": "🗂 <b>نشست‌ها</b>\n{list}",
    "ai_session_item": "{active} <code>{id}</code> {title} — {msgs} پیام",
    "ai_memory_title": "🧠 <b>حافظه</b>\n<b>MEMORY</b>\n{memory}\n\n<b>USER</b>\n{user}",
    "ai_memory_empty": "<i>خالی</i>",
    "ai_skills_title": "🧩 <b>مهارت‌ها</b>\n{list}",
    "ai_skill_item": "• <code>{name}</code> — {desc}",
    "ai_max_iter": "⚠️ به سقف مراحل ({n}) رسیدم. برای ادامه «ادامه» را بفرستید.",
    "ai_file_received": "📎 <b>{name}</b> دریافت شد — بگویید با آن چه کنم (مثلاً «تحلیل و دیپلوی با نام my-api») یا از 🚀 دیپلوی استفاده کنید.",

    # --- راهنما
    "btn_help_arch": "🏗 معماری",
    "btn_help_workers": "⚡ ورکرها",
    "btn_help_tokens": "🔑 توکن‌ها",
    "btn_help_ai": "🤖 CLOUDFLARE_AI",
    "btn_help_cmds": "⌨️ دستورات",
    "btn_help_security": "🔒 امنیت",

    # --- عمومی
    "error_generic": "❌ خطا: <code>{error}</code>",
    "cf_wait": "⏳ محدودیت نرخ Cloudflare — {secs} ثانیه صبر قبل از ادامه…",
    "unknown": "🤔 متوجه نشدم. از منو یا /help استفاده کنید.",
    "yes": "بله",
    "no": "خیر",
    "none": "هیچ",
}
