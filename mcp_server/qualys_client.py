import os
import time
import httpx
from typing import Optional

_token: Optional[str] = None
_token_expiry: float = 0


def _base_url() -> str:
    return os.environ["QUALYS_URL"]


def get_token() -> str:
    global _token, _token_expiry
    if _token and time.time() < _token_expiry:
        return _token

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
    _token_expiry = time.time() + 3300  # refresh before 55-min expiry
    return _token


def get(path: str, params: dict = None) -> dict:
    token = get_token()
    url = f"{_base_url()}/csapi/v1.3{path}"
    resp = httpx.get(
        url,
        params=params or {},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()
