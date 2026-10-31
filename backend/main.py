import asyncio
import os
import logging
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-10s  %(message)s",
    datefmt="%H:%M:%S",
)
# Quieten noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

import json

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from routes.dashboard import router as dashboard_router
from routes.chat import router as chat_router
from agent import prewarm_docs_cache, refresh_docs_cache
import qualys_client
from qualys_client import Credentials, QualysAuthError, auth_mode, current_credentials
from llm import LlmAuthError, LlmCredentials, billing_mode, client_and_model, current_llm, describe_error

app = FastAPI(title="Qualys CS Intelligence", version="1.0.0")


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(prewarm_docs_cache())

# Comma-separated list of browser origins allowed to call the API. Not needed when
# the built frontend is served by this app (same origin), e.g. in the container.
_cors_origins = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------- #
# Qualys sign-in (QUALYS_AUTH_MODE=user): every /api request carries the
# signed-in user's own Qualys URL + API token as X-Qualys-* headers. They are
# held in a context variable for that request only - never stored or logged -
# so each user sees only their own Qualys data.
# --------------------------------------------------------------------------- #
_PUBLIC_API_PATHS = {"/api/config"}
# Paths that call the AI model; with LLM_BILLING=user they need the caller's own key.
_LLM_PATHS = ("/api/chat", "/api/llm/check")
# Paths that call Qualys; /api/llm/check only needs the AI key.
_QUALYS_EXEMPT = {"/api/llm/check"}


def _auth_error_body(error: str, message: str) -> bytes:
    return json.dumps({"error": error, "message": message}).encode()


class QualysAuthMiddleware:
    """Per-request credentials: the user's Qualys URL + token (QUALYS_AUTH_MODE=user)
    and the user's own AI key (LLM_BILLING=user). Held in context variables for the
    request only - never stored or logged."""

    def __init__(self, app):
        self.app = app

    @staticmethod
    async def _reject(send, error: str, message: str):
        await send({"type": "http.response.start", "status": 401,
                    "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": _auth_error_body(error, message)})

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if (
            scope["type"] != "http"
            or not path.startswith("/api/")
            or path in _PUBLIC_API_PATHS
            or scope.get("method") == "OPTIONS"
        ):
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}

        q_creds = None
        if auth_mode() == "user" and path not in _QUALYS_EXEMPT:
            try:
                q_creds = Credentials.from_headers(headers)
            except QualysAuthError as e:
                await self._reject(send, "qualys_auth_required", str(e))
                return

        l_creds = None
        if billing_mode() == "user" and path.startswith(_LLM_PATHS):
            try:
                l_creds = LlmCredentials.from_headers(headers)
            except LlmAuthError as e:
                await self._reject(send, "llm_auth_required", str(e))
                return

        q_tok = current_credentials.set(q_creds)
        l_tok = current_llm.set(l_creds)
        try:
            await self.app(scope, receive, send)
        finally:
            current_llm.reset(l_tok)
            current_credentials.reset(q_tok)


app.add_middleware(QualysAuthMiddleware)


@app.exception_handler(QualysAuthError)
async def _qualys_auth_error(_: Request, exc: QualysAuthError):
    return JSONResponse(status_code=401, content={"error": "qualys_auth_required", "message": str(exc)})


@app.exception_handler(LlmAuthError)
async def _llm_auth_error(_: Request, exc: LlmAuthError):
    return JSONResponse(status_code=401, content={"error": "llm_auth_required", "message": str(exc)})


@app.get("/api/config")
def config():
    """Tells the UI what each user must supply: their own Qualys token and/or AI key."""
    return {"auth_mode": auth_mode(), "llm_billing": billing_mode()}


@app.post("/api/llm/check")
async def llm_check():
    """Validate the caller's own AI key with a tiny request (a few tokens on their account)."""
    if billing_mode() != "user":
        return {"ok": True, "llm_billing": "host"}
    client, model = client_and_model()
    try:
        await asyncio.to_thread(
            client.messages.create, model=model, max_tokens=16,
            messages=[{"role": "user", "content": "Reply with OK."}],
        )
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=401, content={"error": "llm_auth_required", "message": describe_error(e)})
    return {"ok": True, "llm_billing": "user", "model": model}


@app.get("/api/session")
async def session():
    """Validate the caller's Qualys credentials with a minimal API call."""
    await qualys_client.get_async("/containers", {"pageSize": 1})
    creds = current_credentials.get() if auth_mode() == "user" else None
    return {"ok": True, "auth_mode": auth_mode(), "qualys_url": creds.base_url if creds else None}


app.include_router(dashboard_router)
app.include_router(chat_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/docs/refresh")
async def refresh_docs(background_tasks: BackgroundTasks):
    """Trigger a background refresh of the docs cache."""
    background_tasks.add_task(refresh_docs_cache)
    return {"message": "Docs cache refresh started"}


# --------------------------------------------------------------------------- #
# Serve the built React app (frontend/dist) when present, e.g. in the Docker
# image. In local dev Vite serves the UI on :5173 and proxies /api here instead.
# --------------------------------------------------------------------------- #
_STATIC_DIR = os.path.abspath(
    os.environ.get("STATIC_DIR", os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
)

if os.path.isfile(os.path.join(_STATIC_DIR, "index.html")):

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = os.path.abspath(os.path.join(_STATIC_DIR, full_path))
        if full_path and candidate.startswith(_STATIC_DIR + os.sep) and os.path.isfile(candidate):
            return FileResponse(candidate)
        # Client-side routes fall back to the SPA shell.
        return FileResponse(os.path.join(_STATIC_DIR, "index.html"))
