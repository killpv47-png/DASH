from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from ...core.db import Database
from ...core.redact import redact
from ...cloudflare.client import CloudflareClient
from ..memory import MemoryStore


@dataclass
class ToolContext:
    db: Database
    tg_id: int
    session_id: str
    workspace: Path
    memory: MemoryStore
    cf: Optional[CloudflareClient]
    tavily_key: str = ""
    host_repo: str = ""
    bot_token: str = ""
    incoming_file: Optional[dict] = None
    notify: Optional[Callable[[str], Awaitable[None]]] = None
    todos: list[dict] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def redact(self, text: str) -> str:
        return redact(text)

    def resolve(self, path: str) -> Path:
        """Resolve a user-supplied path; relative paths are inside the workspace.
        Absolute paths are allowed (the agent may read the bot's own source) but the
        secret stores are blocked."""
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = self.workspace / p
        p = p.resolve()
        blocked = (".env", ".dev.vars", "cfbot.db", "state.enc")
        if p.name in blocked or any(part == "data" and p.suffix in (".db", ".enc", ".db-wal") for part in p.parts):
            raise PermissionError(f"access to {p.name} is blocked (contains secrets)")
        return p
