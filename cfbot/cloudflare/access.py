"""Credential access-level classification for Cloudflare.

Cloudflare does not send scopes in a header (GitHub did).  We determine what the
credential can do in two ways:
  1. If the token may read itself (``API Tokens Read``) its policies list the
     permission-group *names* ("Workers Scripts Write", "D1 Read", …) → exact.
  2. Otherwise we probe cheap read endpoints (list Workers, KV, D1, R2, zones,
     analytics) → read capability is exact, write capability is inferred:
     a readable resource on a token that is not provably read-only is treated as
     possibly writable and the real answer comes from the API at action time.

Levels (highest first):
  GOD        Global API Key, or token with Workers Scripts Edit + storage edit + routes/DNS edit
  ARCHITECT  Workers edit + storage edit (KV/D1/R2/Queues)
  ENGINEER   Workers edit (deploy code, secrets, vars, crons)
  OBSERVER   read-only
  GHOST      valid credential, no Workers/storage permission
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AccessLevel:
    name: str
    emoji: str
    rank: int
    description_key: str


LEVELS = {
    "GOD": AccessLevel("GOD", "👑", 5, "access_god"),
    "ARCHITECT": AccessLevel("ARCHITECT", "🏛", 4, "access_architect"),
    "ENGINEER": AccessLevel("ENGINEER", "🛠", 3, "access_engineer"),
    "OBSERVER": AccessLevel("OBSERVER", "👁", 2, "access_observer"),
    "GHOST": AccessLevel("GHOST", "👻", 1, "access_ghost"),
}

CAPS = ("workers_read", "workers_write", "kv", "d1", "r2", "queues", "zones", "routes_write", "dns_write", "analytics")


@dataclass
class Capabilities:
    workers_read: bool = False
    workers_write: bool = False
    kv: bool = False
    d1: bool = False
    r2: bool = False
    queues: bool = False
    zones: bool = False
    routes_write: bool = False
    dns_write: bool = False
    analytics: bool = False
    exact: bool = False          # True when derived from the token's own policies
    perm_names: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in CAPS} | {"exact": self.exact}


def caps_from_policies(policies: list[dict]) -> Capabilities:
    names: list[str] = []
    for p in policies or []:
        if p.get("effect", "allow") != "allow":
            continue
        for g in p.get("permission_groups") or []:
            if g.get("name"):
                names.append(g["name"])
    low = [n.lower() for n in names]

    def has(sub: str, write: bool | None = None) -> bool:
        for n in low:
            if sub in n and (write is None or (write and ("edit" in n or "write" in n)) or (write is False)):
                return True
        return False

    c = Capabilities(exact=True, perm_names=sorted(set(names)))
    c.workers_write = has("workers scripts", True)
    c.workers_read = c.workers_write or has("workers scripts")
    c.kv = has("workers kv storage")
    c.d1 = any(n.startswith("d1 ") for n in low)
    c.r2 = has("workers r2 storage")
    c.queues = has("queues")
    c.zones = any(n.startswith("zone ") or n == "zone read" for n in low)
    c.routes_write = has("workers routes", True)
    c.dns_write = any(n.startswith("dns ") and ("edit" in n or "write" in n) for n in low)
    c.analytics = has("analytics")
    return c


def classify_access(caps: Capabilities | None, *, global_key: bool = False) -> AccessLevel:
    if global_key:
        return LEVELS["GOD"]
    if caps is None:
        return LEVELS["GHOST"]
    storage = caps.kv and caps.d1 and caps.r2
    if caps.workers_write and storage and caps.routes_write and caps.dns_write:
        return LEVELS["GOD"]
    if caps.workers_write and (storage or caps.kv or caps.d1):
        return LEVELS["ARCHITECT"]
    if caps.workers_write:
        return LEVELS["ENGINEER"]
    if caps.workers_read or caps.kv or caps.d1 or caps.r2 or caps.zones:
        return LEVELS["OBSERVER"]
    return LEVELS["GHOST"]
