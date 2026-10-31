"""Qualys credential handling shared by the web backend and the MCP server.

A caller authenticates to Qualys in one of two ways:

* **API token** - a Qualys gateway URL + a bearer token (JWT) the user already has.
  Sent straight to the API; no /auth round-trip.
* **Username / password** - a gateway URL + login, exchanged at ``<url>/auth`` for a
  JWT that is cached per user for 55 minutes.

Per-request credentials arrive as HTTP headers:

    X-Qualys-Url:      https://gateway.qg2.apps.qualys.com
    X-Qualys-Token:    <api token / JWT>          (or Authorization: Bearer <token>)
  or
    X-Qualys-Username: <user>                      (or Authorization: Basic ...)
    X-Qualys-Password: <password>

Credentials are never logged; ``Credentials.__repr__`` masks secrets.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import time
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse

TOKEN_TTL_SECONDS = 3300  # Qualys JWTs from /auth live 60 min; refresh at 55.
MAX_CACHED_TOKENS = 1000

# Qualys platform gateways live under these domains. Restricting the target host
# stops a hosted server from being used to send credentials (or requests) to an
# arbitrary URL. Override with QUALYS_ALLOWED_HOST_SUFFIXES (comma-separated).
DEFAULT_ALLOWED_SUFFIXES = (
    ".qualys.com",
    ".qualys.eu",
    ".qualys.in",
    ".qualys.ca",
    ".qualys.ae",
    ".qualys.co.uk",
    ".qualys.com.au",
    ".qualysksa.com",
)


class QualysAuthError(Exception):
    """Credentials are missing, malformed or were rejected."""


def _allowed_suffixes() -> tuple[str, ...]:
    raw = os.environ.get("QUALYS_ALLOWED_HOST_SUFFIXES", "")
    items = tuple(s.strip().lower() for s in raw.split(",") if s.strip())
    return items or DEFAULT_ALLOWED_SUFFIXES


def normalize_base_url(url: str) -> str:
    """Validate a user-supplied Qualys gateway URL; return it without a trailing slash."""
    url = (url or "").strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise QualysAuthError("Qualys URL must be an https:// gateway URL")
    host = parsed.hostname.lower()
    if not any(host.endswith(sfx) for sfx in _allowed_suffixes()):
        raise QualysAuthError(f"Qualys URL host '{host}' is not an allowed Qualys gateway")
    if parsed.path not in ("", "/") or parsed.query:
        raise QualysAuthError("Qualys URL must be just the gateway, e.g. https://gateway.qg2.apps.qualys.com")
    return f"https://{parsed.netloc}"


@dataclass(frozen=True)
class Credentials:
    base_url: str
    token: str | None = None
    username: str | None = None
    password: str | None = None

    def __repr__(self) -> str:  # never leak secrets into logs or tracebacks
        who = f"username={self.username!r}" if self.username else "token='***'"
        return f"Credentials(base_url={self.base_url!r}, {who})"

    @property
    def cache_key(self) -> str:
        raw = "\x00".join([self.base_url, self.token or "", self.username or "", self.password or ""])
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def from_env(cls) -> "Credentials":
        """Single-account mode: QUALYS_URL + QUALYS_TOKEN, or QUALYS_USERNAME/PASSWORD."""
        url = os.environ.get("QUALYS_URL") or os.environ.get("QUALYS_PLATFORM_URL")
        token = os.environ.get("QUALYS_TOKEN")
        user = os.environ.get("QUALYS_USERNAME")
        pwd = os.environ.get("QUALYS_PASSWORD")
        if not url or not (token or (user and pwd)):
            raise QualysAuthError(
                "Set QUALYS_URL plus either QUALYS_TOKEN or QUALYS_USERNAME and QUALYS_PASSWORD"
            )
        # The operator's own environment is trusted, so the host allowlist is skipped.
        url = url.strip().rstrip("/")
        if token:
            return cls(url, token=token.strip())
        return cls(url, username=user, password=pwd)

    @classmethod
    def from_headers(cls, headers: Mapping[str, str], default_url: str | None = None) -> "Credentials":
        """Per-user mode: build credentials from request headers (case-insensitive mapping)."""
        token = (headers.get("x-qualys-token") or "").strip() or None
        username = headers.get("x-qualys-username") or None
        password = headers.get("x-qualys-password") or None

        auth = headers.get("authorization", "") or ""
        scheme, _, value = auth.partition(" ")
        if not token and scheme.lower() == "bearer" and value.strip():
            token = value.strip()
        elif not (username and password) and scheme.lower() == "basic" and value.strip():
            try:
                username, _, password = base64.b64decode(value.strip(), validate=True).decode().partition(":")
            except (binascii.Error, UnicodeDecodeError):
                raise QualysAuthError("Malformed Authorization: Basic header") from None

        if not token and not (username and password):
            raise QualysAuthError(
                "Missing Qualys credentials. Send X-Qualys-Url with X-Qualys-Token "
                "(or X-Qualys-Username and X-Qualys-Password)."
            )
        url = headers.get("x-qualys-url") or default_url or ""
        if not url:
            raise QualysAuthError("Missing X-Qualys-Url header")
        base = normalize_base_url(url)
        if token:
            return cls(base, token=token)
        return cls(base, username=username, password=password)


class TokenCache:
    """Per-credential cache of JWTs obtained from /auth (bounded, expiry-aware)."""

    def __init__(self) -> None:
        self._tokens: dict[str, tuple[str, float]] = {}

    def get(self, creds: Credentials) -> str | None:
        if creds.token:
            return creds.token
        hit = self._tokens.get(creds.cache_key)
        if hit and time.time() < hit[1]:
            return hit[0]
        return None

    def put(self, creds: Credentials, token: str) -> None:
        if len(self._tokens) >= MAX_CACHED_TOKENS:
            now = time.time()
            for k in [k for k, (_, exp) in self._tokens.items() if exp <= now]:
                self._tokens.pop(k, None)
            if len(self._tokens) >= MAX_CACHED_TOKENS:
                self._tokens.pop(min(self._tokens, key=lambda k: self._tokens[k][1]), None)
        self._tokens[creds.cache_key] = (token, time.time() + TOKEN_TTL_SECONDS)

    def drop(self, creds: Credentials) -> None:
        self._tokens.pop(creds.cache_key, None)


def auth_form(creds: Credentials) -> dict[str, str]:
    return {"username": creds.username or "", "password": creds.password or "", "token": "true"}


def raise_for_auth_status(status_code: int, using_token: bool) -> None:
    if status_code in (401, 403):
        raise QualysAuthError(
            "Qualys rejected the API token (expired or invalid)" if using_token
            else "Qualys rejected the supplied credentials"
        )
