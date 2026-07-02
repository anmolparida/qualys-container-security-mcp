import os
import time
import logging
import httpx
from typing import Optional

logger = logging.getLogger("qualys")

_token: Optional[str] = None
_token_expiry: float = 0

# Shared async HTTP client (reusing a single session is more efficient than creating one per call)
_async_client: Optional[httpx.AsyncClient] = None


def _base_url() -> str:
    return os.environ["QUALYS_URL"]


def _get_async_client() -> httpx.AsyncClient:
    global _async_client
    if _async_client is None or _async_client.is_closed:
        _async_client = httpx.AsyncClient(timeout=60)
    return _async_client


def get_token() -> str:
    global _token, _token_expiry
    if _token and time.time() < _token_expiry:
        return _token

    logger.info("AUTH  POST /auth  (fetching new JWT)")
    url = f"{_base_url()}/auth"
    resp = httpx.post(
        url,
        data={
            "username": os.environ["QUALYS_USERNAME"],
            "password": os.environ["QUALYS_PASSWORD"],
            "token": "true",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    _token = resp.text.strip()
    _token_expiry = time.time() + 3300
    logger.info("AUTH  token cached for 55 min")
    return _token


async def get_token_async() -> str:
    global _token, _token_expiry
    if _token and time.time() < _token_expiry:
        return _token

    logger.info("AUTH  POST /auth  (fetching new JWT async)")
    url = f"{_base_url()}/auth"
    client = _get_async_client()
    resp = await client.post(
        url,
        data={
            "username": os.environ["QUALYS_USERNAME"],
            "password": os.environ["QUALYS_PASSWORD"],
            "token": "true",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    _token = resp.text.strip()
    _token_expiry = time.time() + 3300
    logger.info("AUTH  token cached for 55 min")
    return _token


def get(path: str, params: dict = None) -> dict:
    token = get_token()
    url = f"{_base_url()}/csapi/v1.3{path}"
    clean_params = {k: v for k, v in (params or {}).items() if v not in (None, "", 0)}
    param_str = f"  params={clean_params}" if clean_params else ""
    logger.info(f"QUALYS GET /csapi/v1.3{path}{param_str}")
    t0 = time.time()
    resp = httpx.get(
        url,
        params=params or {},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    elapsed = int((time.time() - t0) * 1000)
    resp.raise_for_status()
    data = resp.json()
    count = len(data) if isinstance(data, list) else (len(data.get("list", data.get("data", []))) if isinstance(data, dict) else "?")
    logger.info(f"QUALYS GET /csapi/v1.3{path}  → {resp.status_code}  {elapsed}ms  ({count} items)")
    return data


async def post_async(path: str, body: dict = None) -> dict:
    token = await get_token_async()
    url = f"{_base_url()}/csapi/v1.3{path}"
    logger.info(f"QUALYS POST /csapi/v1.3{path}")
    t0 = time.time()
    client = _get_async_client()
    resp = await client.post(
        url,
        json=body or {},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=60,
    )
    elapsed = int((time.time() - t0) * 1000)
    resp.raise_for_status()
    try:
        data = resp.json()
    except Exception:
        data = {"result": resp.text}
    logger.info(f"QUALYS POST /csapi/v1.3{path}  → {resp.status_code}  {elapsed}ms")
    return data


async def get_async(path: str, params: dict = None) -> dict:
    token = await get_token_async()
    url = f"{_base_url()}/csapi/v1.3{path}"
    clean_params = {k: v for k, v in (params or {}).items() if v not in (None, "", 0)}
    param_str = f"  params={clean_params}" if clean_params else ""
    logger.info(f"QUALYS GET /csapi/v1.3{path}{param_str}")
    t0 = time.time()
    client = _get_async_client()
    resp = await client.get(
        url,
        params=params or {},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    elapsed = int((time.time() - t0) * 1000)
    resp.raise_for_status()
    data = resp.json()
    count = len(data) if isinstance(data, list) else (len(data.get("list", data.get("data", []))) if isinstance(data, dict) else "?")
    logger.info(f"QUALYS GET /csapi/v1.3{path}  → {resp.status_code}  {elapsed}ms  ({count} items)")
    return data
