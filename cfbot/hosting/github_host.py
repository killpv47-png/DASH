"""Minimal client for the *host* repository that runs this bot on GitHub Actions.

This is NOT a user-facing GitHub feature.  The bot manages Cloudflare; it is merely
*hosted* as a long-running GitHub Actions job.  The lifecycle module needs exactly
four operations on the host repo, all with ``HOST_PAT``:

  * read / write ``state/state.enc`` on branch ``cfbot-state``  (encrypted checkpoint)
  * create that branch if missing
  * ``workflow_dispatch`` the bot workflow again (self-restart before the 6h limit)

Nothing else from the GitHub API is used anywhere in the project.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

API = "https://api.github.com"


class HostError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"host repo {status}: {message}")
        self.status = status
        self.message = message


class HostRepoClient:
    def __init__(self, token: str, *, timeout: float = 40.0):
        self._client = httpx.AsyncClient(
            base_url=API, timeout=timeout, follow_redirects=True,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "cfbot-host/2.0"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "HostRepoClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    async def _json(self, method: str, path: str, *, json: Any = None, params: dict | None = None) -> Any:
        last: Exception | None = None
        for attempt in range(5):
            try:
                resp = await self._client.request(method, path, json=json, params=params)
            except (httpx.TransportError, httpx.TimeoutException) as e:
                last = e
                await asyncio.sleep(min(1.5 ** attempt, 15))
                continue
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < 4:
                ra = resp.headers.get("retry-after")
                await asyncio.sleep(min(float(ra), 60) if ra and ra.isdigit() else min(2 ** attempt, 20))
                continue
            if resp.status_code >= 300:
                try:
                    msg = resp.json().get("message", resp.text)
                except Exception:
                    msg = resp.text
                raise HostError(resp.status_code, str(msg)[:300])
            if resp.status_code == 204 or not resp.content:
                return None
            return resp.json()
        raise HostError(0, f"network error: {last}")

    async def default_branch(self, repo: str) -> str:
        return (await self._json("GET", f"/repos/{repo}"))["default_branch"]

    async def branch_exists(self, repo: str, branch: str) -> bool:
        try:
            await self._json("GET", f"/repos/{repo}/git/ref/heads/{branch}")
            return True
        except HostError as e:
            if e.status == 404:
                return False
            raise

    async def create_branch(self, repo: str, branch: str) -> None:
        base = await self.default_branch(repo)
        ref = await self._json("GET", f"/repos/{repo}/git/ref/heads/{base}")
        await self._json("POST", f"/repos/{repo}/git/refs", json={"ref": f"refs/heads/{branch}", "sha": ref["object"]["sha"]})

    async def read_file(self, repo: str, path: str, branch: str) -> bytes | None:
        try:
            data = await self._json("GET", f"/repos/{repo}/contents/{path}", params={"ref": branch})
        except HostError as e:
            if e.status == 404:
                return None
            raise
        if isinstance(data, dict) and data.get("encoding") == "base64" and data.get("content"):
            return base64.b64decode(data["content"])
        blob = await self._json("GET", f"/repos/{repo}/git/blobs/{data['sha']}")  # files > 1 MB
        return base64.b64decode(blob["content"])

    async def write_file(self, repo: str, path: str, content: bytes, message: str, branch: str) -> None:
        sha = None
        try:
            existing = await self._json("GET", f"/repos/{repo}/contents/{path}", params={"ref": branch})
            if isinstance(existing, dict):
                sha = existing.get("sha")
        except HostError as e:
            if e.status != 404:
                raise
        body: dict[str, Any] = {"message": message, "content": base64.b64encode(content).decode(), "branch": branch}
        if sha:
            body["sha"] = sha
        await self._json("PUT", f"/repos/{repo}/contents/{path}", json=body)

    async def dispatch(self, repo: str, workflow: str, ref: str, inputs: dict | None = None) -> None:
        await self._json("POST", f"/repos/{repo}/actions/workflows/{workflow}/dispatches",
                         json={"ref": ref, "inputs": inputs or {}})
