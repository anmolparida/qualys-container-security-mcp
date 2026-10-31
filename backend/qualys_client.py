"""Qualys CS API client for the web backend.

Which Qualys account a call uses depends on ``QUALYS_AUTH_MODE``:

* ``service`` (default) - one shared account from the environment
  (QUALYS_URL + QUALYS_TOKEN, or QUALYS_USERNAME + QUALYS_PASSWORD).
* ``user`` - every browser user signs in with their own Qualys URL + API token.
  The UI sends them as X-Qualys-* headers, ``auth_middleware`` in main.py puts
  them in ``current_credentials`` for the duration of that request, and each user
  only ever sees their own data.
"""

import asyncio
import contextvars
import json
import logging
import os
import sys
import time
from typing import Optional

import httpx

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.qualys_auth import (  # noqa: E402
    Credentials,
    QualysAuthError,
    TokenCache,
    auth_form,
    raise_for_auth_status,
)

logger = logging.getLogger("qualys")

API_PREFIX = "/csapi/v1.3"


def _load_secret_json() -> None:
    """On ECS (service mode) the Qualys secret arrives as one JSON env var; unpack it."""
    raw = os.environ.get("QUALYS_SECRET_JSON")
    if not raw:
        return
    try:
        values = json.loads(raw)
    except ValueError:
        raise RuntimeError("QUALYS_SECRET_JSON is not valid JSON") from None
    for key in ("QUALYS_URL", "QUALYS_TOKEN", "QUALYS_USERNAME", "QUALYS_PASSWORD"):
        if values.get(key) and not os.environ.get(key):
            os.environ[key] = str(values[key])


_load_secret_json()


def auth_mode() -> str:
    mode = os.environ.get("QUALYS_AUTH_MODE", "service").strip().lower()
    if mode not in ("service", "user"):
        raise RuntimeError("QUALYS_AUTH_MODE must be 'service' or 'user'")
    return mode


# Per-request credentials (user mode). Set by the auth middleware in main.py.
current_credentials: contextvars.ContextVar[Optional[Credentials]] = contextvars.ContextVar(
    "qualys_credentials", default=None
)

_cache = TokenCache()
_locks: dict[str, asyncio.Lock] = {}
_async_client: Optional[httpx.AsyncClient] = None


def _get_async_client() -> httpx.AsyncClient:
    global _async_client
    if _async_client is None or _async_client.is_closed:
        _async_client = httpx.AsyncClient(timeout=60)
    return _async_client


def _creds() -> Credentials:
    if auth_mode() == "user":
        creds = current_credentials.get()
        if creds is None:
            raise QualysAuthError("Not signed in to Qualys")
        return creds
    return Credentials.from_env()


def _count(data) -> object:
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        return len(data.get("list", data.get("data", [])))
    return "?"


# ----------------------------------------------------------------- tokens

def _fetch_token_sync(creds: Credentials) -> str:
    token = _cache.get(creds)
    if token:
        return token
    logger.info("AUTH  POST /auth  (fetching new JWT)")
    resp = httpx.post(
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


async def _fetch_token_async(creds: Credentials) -> str:
    token = _cache.get(creds)
    if token:
        return token
    lock = _locks.setdefault(creds.cache_key, asyncio.Lock())
    async with lock:
        token = _cache.get(creds)
        if token:
            return token
        logger.info("AUTH  POST /auth  (fetching new JWT async)")
        resp = await _get_async_client().post(
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


def _handle_401(creds: Credentials, attempt: int) -> bool:
    """Return True to retry once with a fresh JWT; raise when the login itself is bad."""
    if creds.token:
        raise_for_auth_status(401, using_token=True)
    if attempt == 1:
        _cache.drop(creds)
        return True
    raise_for_auth_status(401, using_token=False)
    return False


# ----------------------------------------------------------------- API calls

def get(path: str, params: dict = None) -> dict:
    creds = _creds()
    clean_params = {k: v for k, v in (params or {}).items() if v not in (None, "", 0)}
    logger.info(f"QUALYS GET {API_PREFIX}{path}" + (f"  params={clean_params}" if clean_params else ""))
    for attempt in (1, 2):
        t0 = time.time()
        resp = httpx.get(
            f"{creds.base_url}{API_PREFIX}{path}",
            params=params or {},
            headers={"Authorization": f"Bearer {_fetch_token_sync(creds)}"},
            timeout=60,
        )
        if resp.status_code == 401 and _handle_401(creds, attempt):
            continue
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"QUALYS GET {API_PREFIX}{path}  → {resp.status_code}  {int((time.time() - t0) * 1000)}ms  ({_count(data)} items)")
        return data


async def get_async(path: str, params: dict = None) -> dict:
    creds = _creds()
    clean_params = {k: v for k, v in (params or {}).items() if v not in (None, "", 0)}
    logger.info(f"QUALYS GET {API_PREFIX}{path}" + (f"  params={clean_params}" if clean_params else ""))
    for attempt in (1, 2):
        t0 = time.time()
        resp = await _get_async_client().get(
            f"{creds.base_url}{API_PREFIX}{path}",
            params=params or {},
            headers={"Authorization": f"Bearer {await _fetch_token_async(creds)}"},
            timeout=60,
        )
        if resp.status_code == 401 and _handle_401(creds, attempt):
            continue
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"QUALYS GET {API_PREFIX}{path}  → {resp.status_code}  {int((time.time() - t0) * 1000)}ms  ({_count(data)} items)")
        return data


async def post_async(path: str, body: dict = None) -> dict:
    creds = _creds()
    logger.info(f"QUALYS POST {API_PREFIX}{path}")
    for attempt in (1, 2):
        t0 = time.time()
        resp = await _get_async_client().post(
            f"{creds.base_url}{API_PREFIX}{path}",
            json=body or {},
            headers={"Authorization": f"Bearer {await _fetch_token_async(creds)}",
                     "Content-Type": "application/json"},
            timeout=60,
        )
        if resp.status_code == 401 and _handle_401(creds, attempt):
            continue
        resp.raise_for_status()
        try:
            data = resp.json()
        except Exception:
            data = {"result": resp.text}
        logger.info(f"QUALYS POST {API_PREFIX}{path}  → {resp.status_code}  {int((time.time() - t0) * 1000)}ms")
        return data


def cache_scope() -> str:
    """Key that separates cached data per Qualys account (never shared across users)."""
    if auth_mode() == "user":
        creds = current_credentials.get()
        return creds.cache_key if creds else "anonymous"
    return "service"
