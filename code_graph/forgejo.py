"""Minimal async Forgejo REST client — enough to list PRs and their files.

Scoped deliberately: this is not a general Forgejo SDK, just the two paginated
reads the PR indexer needs. Used as an async context manager so the underlying
httpx client is always closed.
"""

from __future__ import annotations

from typing import AsyncIterator

import httpx

PAGE_SIZE = 50


class ForgejoError(RuntimeError):
    """A Forgejo request failed in a way worth reporting to the operator."""


class ForgejoClient:
    def __init__(self, base_url: str, token: str):
        self._base = base_url.rstrip("/")
        # Forgejo expects "Authorization: token <TOKEN>". A "Bearer" header is
        # silently rejected with 401 — a trap worth naming here.
        self._client = httpx.AsyncClient(
            base_url=self._base,
            headers={"Authorization": f"token {token}"},
            timeout=30.0,
        )

    async def __aenter__(self) -> "ForgejoClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict) -> httpx.Response:
        # httpx does not raise on non-2xx by default, so every response is
        # checked here and the common auth/not-found cases get actionable text.
        try:
            resp = await self._client.get(path, params=params)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code == 401:
                raise ForgejoError("bad token — Forgejo rejected the credential (401)") from None
            if code == 403:
                raise ForgejoError("forbidden — token lacks read access (403)") from None
            if code == 404:
                raise ForgejoError(f"not found: {path} (404)") from None
            raise ForgejoError(f"GET {path} -> HTTP {code}") from None
        except httpx.HTTPError as exc:
            raise ForgejoError(f"GET {path} failed: {exc}") from None

    async def _paginate(self, path: str, params: dict) -> AsyncIterator[dict]:
        """Yield every item across all pages. Forgejo pages are 1-indexed and a
        short page (fewer than PAGE_SIZE) is the last one."""
        page = 1
        while True:
            resp = await self._get(path, {**params, "page": page, "limit": PAGE_SIZE})
            batch = resp.json()
            if not isinstance(batch, list):
                return
            for item in batch:
                yield item
            if len(batch) < PAGE_SIZE:
                return
            page += 1

    def list_pulls(self, owner: str, name: str, state: str) -> AsyncIterator[dict]:
        """All pull requests for a repo in the given state (all|open|closed)."""
        return self._paginate(
            f"/api/v1/repos/{owner}/{name}/pulls", {"state": state}
        )

    def list_pr_files(self, owner: str, name: str, number: int) -> AsyncIterator[dict]:
        """Every changed file of a PR. Paginated on purpose — a PR with more
        than PAGE_SIZE files would otherwise truncate silently."""
        return self._paginate(
            f"/api/v1/repos/{owner}/{name}/pulls/{number}/files", {}
        )
