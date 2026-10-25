"""cloudflare_docs — read the OFFICIAL Cloudflare documentation as Markdown.

developers.cloudflare.com serves every page as Markdown at ``<page>/index.md`` and a per-product
index at ``/<product>/llms.txt``.  This lets CLOUDFLARE_AI base decisions on current docs
(API endpoints, binding formats, limits, permissions) without a search API key.
Only developers.cloudflare.com is allowed.
"""

from __future__ import annotations

import json
import re

import httpx

from .context import ToolContext

BASE = "https://developers.cloudflare.com"
SCHEMA = {
    "name": "cloudflare_docs",
    "description": (
        "Fetch official Cloudflare docs as Markdown. path examples: '/workers/platform/limits/', "
        "'/api/resources/workers/subresources/scripts/methods/update/', '/d1/llms.txt' (product index), "
        "'/fundamentals/api/reference/permissions/'. Optional `find` returns only lines matching a regex (with context). "
        "Use before answering questions about limits, permissions, API shapes or binding formats."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "find": {"type": "string", "description": "regex to filter lines"},
            "max_chars": {"type": "integer"},
        },
        "required": ["path"],
    },
}


async def handle(ctx: ToolContext, args: dict) -> str:
    path = (args.get("path") or "").strip()
    if path.startswith("http"):
        if not path.startswith(BASE):
            return json.dumps({"error": "only developers.cloudflare.com is allowed"})
        path = path[len(BASE):]
    if not path.startswith("/"):
        path = "/" + path
    if not path.endswith((".md", ".txt")):
        path = path.rstrip("/") + "/index.md"
    url = BASE + path
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
            r = await c.get(url, headers={"Accept": "text/markdown"})
    except httpx.HTTPError as e:
        return json.dumps({"error": f"fetch failed: {e}"})
    if r.status_code != 200:
        return json.dumps({"error": f"HTTP {r.status_code}", "url": url})
    text = r.text
    if args.get("find"):
        try:
            rx = re.compile(args["find"], re.I)
        except re.error as e:
            return json.dumps({"error": f"bad regex: {e}"})
        lines = text.splitlines()
        keep: list[str] = []
        for i, ln in enumerate(lines):
            if rx.search(ln):
                keep.extend(lines[max(0, i - 2): i + 4])
                keep.append("…")
        text = "\n".join(keep) or "(no match)"
    limit = min(int(args.get("max_chars") or 15000), 30000)
    return json.dumps({"url": url, "content": text[:limit], "truncated": len(text) > limit}, ensure_ascii=False)
