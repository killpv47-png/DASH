"""Cloudflare credential presets → official dashboard template links.

Source: https://developers.cloudflare.com/fundamentals/api/how-to/account-owned-token-template/
  user token    https://dash.cloudflare.com/profile/api-tokens?permissionGroupKeys=<enc>&accountId=*&zoneId=all&name=<n>
  account token https://dash.cloudflare.com/?to=/:account/api-tokens&permissionGroupKeys=<enc>&name=<n>
Permission keys used below are the ones listed in that official reference table
(workers_scripts, workers_kv_storage, workers_r2, d1, queues, workers_routes, zone, dns,
account_settings, account_analytics, account_api_tokens, page).

About "GID token with all permissions"
--------------------------------------
Cloudflare has no credential, token type or permission called "GID".  The two real
ways to get "everything" are:
  1. a custom API token that includes every permission group this bot uses (preset
     ``full``) — scoped, revocable, recommended;
  2. the legacy **Global API Key** (email + key) — every permission of the user on every
     account, cannot be scoped or given an expiry; Cloudflare recommends API tokens instead.
Both are implemented; the UI explains the difference and the risk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import quote

USER_BASE = "https://dash.cloudflare.com/profile/api-tokens"
ACCOUNT_BASE = "https://dash.cloudflare.com/?to=/:account/api-tokens"
GLOBAL_KEY_URL = "https://dash.cloudflare.com/profile/api-tokens"  # "Global API Key" → View
DOCS_CREATE = "https://developers.cloudflare.com/fundamentals/api/get-started/create-token/"
DOCS_PERMISSIONS = "https://developers.cloudflare.com/fundamentals/api/reference/permissions/"
DOCS_GLOBAL_KEY = "https://developers.cloudflare.com/fundamentals/api/get-started/keys/"


@dataclass(frozen=True)
class Preset:
    key: str
    name: str            # pre-filled token name
    perms: tuple[tuple[str, str], ...]  # (permission key, read|edit)
    i18n: str            # description key
    risk: str            # low | medium | high

    def encoded(self) -> str:
        return quote(json.dumps([{"key": k, "type": t} for k, t in self.perms], separators=(",", ":")), safe="")

    def user_url(self) -> str:
        return f"{USER_BASE}?permissionGroupKeys={self.encoded()}&accountId=*&zoneId=all&name={quote(self.name)}"

    def account_url(self) -> str:
        return f"{ACCOUNT_BASE}&permissionGroupKeys={self.encoded()}&name={quote(self.name)}"

    def human_perms(self) -> list[str]:
        return [f"{PERM_LABELS.get(k, k)} — {'Edit' if t == 'edit' else 'Read'}" for k, t in self.perms]


PERM_LABELS = {
    "workers_scripts": "Account · Workers Scripts",
    "workers_kv_storage": "Account · Workers KV Storage",
    "workers_r2": "Account · Workers R2 Storage",
    "d1": "Account · D1",
    "queues": "Account · Queues",
    "account_settings": "Account · Account Settings",
    "account_analytics": "Account · Account Analytics",
    "account_api_tokens": "Account · API Tokens",
    "page": "Account · Cloudflare Pages",
    "workers_routes": "Zone · Workers Routes",
    "zone": "Zone · Zone",
    "dns": "Zone · DNS",
}

PRESETS: dict[str, Preset] = {p.key: p for p in [
    Preset("full", "Cloudflare Control Bot - Full", (
        ("workers_scripts", "edit"), ("workers_kv_storage", "edit"), ("workers_r2", "edit"), ("d1", "edit"),
        ("queues", "edit"), ("page", "edit"), ("account_settings", "read"), ("account_analytics", "read"),
        ("account_api_tokens", "read"), ("workers_routes", "edit"), ("zone", "read"), ("dns", "edit"),
    ), "tok_full", "high"),
    Preset("workers", "Cloudflare Control Bot - Workers deploy", (
        ("workers_scripts", "edit"), ("account_settings", "read"),
    ), "tok_workers", "medium"),
    Preset("storage", "Cloudflare Control Bot - Workers + Storage", (
        ("workers_scripts", "edit"), ("workers_kv_storage", "edit"), ("d1", "edit"), ("workers_r2", "edit"),
        ("queues", "edit"), ("account_settings", "read"), ("account_analytics", "read"),
    ), "tok_storage", "medium"),
    Preset("routes", "Cloudflare Control Bot - Routes & Domains", (
        ("workers_scripts", "read"), ("workers_routes", "edit"), ("zone", "read"), ("dns", "edit"),
    ), "tok_routes", "medium"),
    Preset("readonly", "Cloudflare Control Bot - Read only", (
        ("workers_scripts", "read"), ("workers_kv_storage", "read"), ("d1", "read"), ("workers_r2", "read"),
        ("queues", "read"), ("account_settings", "read"), ("account_analytics", "read"), ("zone", "read"),
    ), "tok_readonly", "low"),
]}

# Which bot feature needs which permission (shown in the token guide and used for error hints).
FEATURE_PERMS = {
    "Workers: list / view code / deploy / delete / secrets / vars / crons / rollback": "Workers Scripts (Read for viewing, Edit for changes)",
    "KV namespaces & keys": "Workers KV Storage",
    "D1 databases & SQL console": "D1",
    "R2 buckets": "Workers R2 Storage",
    "Queues": "Queues",
    "Metrics (requests, errors, CPU)": "Account Analytics Read",
    "Routes on your zones": "Workers Routes Edit + Zone Read",
    "Custom domains for Workers": "Workers Routes Edit + Zone Read + DNS Edit",
    "Show the token's own permissions": "API Tokens Read (optional)",
}

ERROR_HINTS = {
    10000: "Authentication error — the token lacks the permission for this call. Add it in the dashboard (Edit token) or create a new token from a preset.",
    9109: "Invalid access token.",
    6003: "Invalid request headers — the token is malformed.",
    10007: "Worker not found.",
    10021: "Worker code failed validation — check the syntax / main module.",
    10057: "Inherited binding could not be resolved.",
    7003: "Could not route to this URL — wrong account or zone id.",
}


def hint_for(codes: set[int]) -> str:
    for c in codes:
        if c in ERROR_HINTS:
            return ERROR_HINTS[c]
    return ""
