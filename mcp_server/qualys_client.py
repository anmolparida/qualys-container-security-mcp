"""Async Qualys Container Security API client used by the MCP server.

Credentials are passed in explicitly on every call (see ``shared/qualys_auth.py``)
so one hosted server can serve many users, each seeing only their own data.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import httpx

from shared.qualys_auth import (  # noqa: E402  (re-exported for server.py)
    Credentials,
    QualysAuthError,
    TokenCache,
    auth_form,
    normalize_base_url,
    raise_for_auth_status,
)

API_PREFIX = "/csapi/v1.3"

_cache = TokenCache()
_locks: dict[str, asyncio.Lock] = {}
_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=60)
    return _client


async def _bearer(creds: Credentials) -> str:
    token = _cache.get(creds)
    if token:
        return token
    lock = _locks.setdefault(creds.cache_key, asyncio.Lock())
    async with lock:
        token = _cache.get(creds)
        if token:
            return token
        resp = await _http().post(
            f"{creds.base_url}/auth",
            data=auth_form(creds),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        if resp.status_code == 400:
            raise QualysAuthError("Qualys rejected the supplied credentials")
        raise_for_auth_status(resp.status_code, using_token=False)
        resp.raise_for_status()
        token = resp.text.strip()
        _cache.put(creds, token)
        return token


async def request(
    creds: Credentials,
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> Any:
    """Call the Qualys CS API, re-authenticating once if a cached JWT was revoked."""
    for attempt in (1, 2):
        token = await _bearer(creds)
        resp = await _http().request(
            method,
            f"{creds.base_url}{API_PREFIX}{path}",
            params=params or None,
            json=body if method != "GET" else None,
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 401:
            if creds.token:
                raise_for_auth_status(401, using_token=True)
            if attempt == 1:
                _cache.drop(creds)
                continue
            raise_for_auth_status(401, using_token=False)
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            return {"result": resp.text}
