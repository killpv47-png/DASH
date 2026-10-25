"""Starter Worker templates for the "New Worker" wizard (ES module syntax, deployable as-is)."""

TEMPLATES: dict[str, dict] = {
    "hello": {
        "title": "👋 Hello World (fetch)",
        "code": """export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    return Response.json({ hello: "world", path: url.pathname, greeting: env.GREETING ?? "hi" });
  },
};
""",
    },
    "kv": {
        "title": "🗂 KV counter / cache",
        "code": """export default {
  async fetch(request, env) {
    const n = parseInt((await env.CACHE.get("hits")) ?? "0") + 1;
    await env.CACHE.put("hits", String(n), { expirationTtl: 86400 });
    return Response.json({ hits: n });
  },
};
""",
    },
    "d1": {
        "title": "🗄 D1 REST API",
        "code": """export default {
  async fetch(request, env) {
    await env.DB.exec("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)");
    if (request.method === "POST") {
      const { body } = await request.json();
      const r = await env.DB.prepare("INSERT INTO notes (body) VALUES (?)").bind(body).run();
      return Response.json({ id: r.meta.last_row_id }, { status: 201 });
    }
    const { results } = await env.DB.prepare("SELECT * FROM notes ORDER BY id DESC LIMIT 50").all();
    return Response.json(results);
  },
};
""",
    },
    "r2": {
        "title": "🪣 R2 file store",
        "code": """export default {
  async fetch(request, env) {
    const key = new URL(request.url).pathname.slice(1) || "index.txt";
    if (request.method === "PUT") {
      await env.BUCKET.put(key, request.body, { httpMetadata: { contentType: request.headers.get("content-type") ?? "application/octet-stream" } });
      return new Response("stored " + key, { status: 201 });
    }
    const obj = await env.BUCKET.get(key);
    if (!obj) return new Response("not found", { status: 404 });
    const headers = new Headers();
    obj.writeHttpMetadata(headers);
    return new Response(obj.body, { headers });
  },
};
""",
    },
    "cron": {
        "title": "⏰ Cron job",
        "code": """export default {
  async scheduled(controller, env, ctx) {
    ctx.waitUntil(fetch(env.PING_URL ?? "https://example.com"));
    console.log("cron fired", controller.cron, new Date(controller.scheduledTime).toISOString());
  },
  async fetch() {
    return new Response("cron worker alive");
  },
};
""",
        "crons": ["*/30 * * * *"],
    },
    "proxy": {
        "title": "🔁 Reverse proxy with secret header",
        "code": """export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const target = new URL(url.pathname + url.search, env.UPSTREAM_URL);
    const headers = new Headers(request.headers);
    headers.set("Authorization", "Bearer " + env.API_TOKEN);
    return fetch(target, { method: request.method, headers, body: request.body });
  },
};
""",
    },
}
