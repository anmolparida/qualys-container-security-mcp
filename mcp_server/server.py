"""Qualys Container Security MCP server.

This server exposes the Qualys CS API as MCP tools. The tool surface is defined in
``shared/tool_registry.py`` so the backend agent and the MCP server stay in sync.

Two ways to run it:

* **stdio** (default) - launched locally by an MCP client; Qualys credentials come
  from ``.env`` / environment variables.
* **http** - hosted over the network (e.g. on AWS ECS behind an ALB) at ``/mcp``.
  Each caller sends their *own* Qualys credentials as HTTP headers, so every user
  sees only their own data and the server holds no shared Qualys account:

      X-Qualys-Url:   https://gateway.qg2.apps.qualys.com
      X-Qualys-Token: <your Qualys API token>      (or Authorization: Bearer <token>)

  ``X-Qualys-Username`` + ``X-Qualys-Password`` (or ``Authorization: Basic``) work
  instead of a token. If ``X-Qualys-Url`` is omitted, ``QUALYS_URL`` from the
  server environment is used as the default gateway. See shared/qualys_auth.py.
"""

import inspect
import logging
import os
import sys
from typing import Annotated, Any, Literal

# Make the shared tool registry importable from the project root.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import httpx
from pydantic import Field
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from qualys_client import Credentials, QualysAuthError, request
from shared.tool_registry import TOOLS, build_route, get_tool_method, preflight_filter, run_local_tool
from shared import qql

logger = logging.getLogger("qualys-mcp")

mcp = FastMCP(
    "qualys-cs",
    instructions=(
        "Qualys Container Security tools. Never guess QQL filter token names: use a verified "
        "filter below or call lookup_qql_tokens first.\n\n" + qql.prompt_block()
    ),
)

# "env": use QUALYS_* environment variables (local stdio use).
# "headers": require per-user credentials in request headers (hosted use).
# Set from the CLI in __main__; defaults to env so imports/tests behave like stdio.
AUTH_MODE = os.environ.get("QUALYS_AUTH_MODE", "env")


# --------------------------------------------------------------------------- #
# Credentials
# --------------------------------------------------------------------------- #

def _resolve_credentials(ctx: Context | None) -> Credentials:
    if AUTH_MODE == "headers":
        req = getattr(getattr(ctx, "request_context", None), "request", None) if ctx else None
        if req is None:
            raise QualysAuthError("Per-user header auth requires the HTTP transport")
        return Credentials.from_headers(req.headers, os.environ.get("QUALYS_URL"))
    return Credentials.from_env()


# --------------------------------------------------------------------------- #
# Tools (generated from the shared registry)
# --------------------------------------------------------------------------- #

_JSON_TO_PY = {"string": str, "integer": int, "number": float, "boolean": bool,
               "array": list, "object": dict}


def _annotation(spec: dict[str, Any]):
    if "enum" in spec:
        base = Literal[tuple(spec["enum"])]  # type: ignore[misc]
    else:
        base = _JSON_TO_PY.get(spec.get("type", "string"), str)
    if spec.get("description"):
        return Annotated[base, Field(description=spec["description"])]
    return base


def _make_tool_handler(tool: dict[str, Any]):
    """Build an async handler whose signature mirrors the registry parameters.

    FastMCP derives each tool's input schema from the function signature, so a
    real signature (not ``**kwargs``) is what gives MCP clients correct argument
    names, types, defaults and required fields.
    """
    name = tool["name"]
    method = "LOCAL" if tool.get("local") else get_tool_method(name)

    async def handler(ctx: Context, **kwargs: Any) -> Any:
        if method == "LOCAL":  # no Qualys call, no credentials needed
            return run_local_tool(name, kwargs)
        rejected = preflight_filter(name, kwargs)
        if rejected:
            raise ToolError(f"{rejected['message']} Did you mean: {rejected['did_you_mean']}")
        try:
            creds = _resolve_credentials(ctx)
            path, params = build_route(name, kwargs)
            if method == "GET":
                return await request(creds, "GET", path, params=params)
            return await request(creds, method, path, body=params)
        except QualysAuthError as e:
            raise ToolError(f"Qualys authentication error: {e}") from None
        except httpx.HTTPStatusError as e:
            raise ToolError(
                f"Qualys API returned HTTP {e.response.status_code}: {e.response.text[:2000]}"
            ) from None
        except httpx.HTTPError as e:
            raise ToolError(f"Could not reach the Qualys API: {e}") from None

    params = [inspect.Parameter("ctx", inspect.Parameter.KEYWORD_ONLY, annotation=Context)]
    for pname, spec in tool["parameters"].items():
        params.append(inspect.Parameter(
            pname,
            inspect.Parameter.KEYWORD_ONLY,
            annotation=_annotation(spec),
            default=spec["default"] if "default" in spec else inspect.Parameter.empty,
        ))
    handler.__signature__ = inspect.Signature(params)
    handler.__annotations__ = {p.name: p.annotation for p in params}
    handler.__name__ = name
    handler.__doc__ = tool["description"]
    return handler


for _tool in TOOLS:
    mcp.add_tool(_make_tool_handler(_tool), name=_tool["name"], description=_tool["description"])


# --------------------------------------------------------------------------- #
# Documentation resources
# --------------------------------------------------------------------------- #

@mcp.resource("docs://qualys-container-security")
def qualys_container_security_docs() -> str:
    """Qualys Container Security product documentation."""
    return "https://docs.qualys.com/en/cs/latest/get_started/cs_docs.htm"


@mcp.resource("docs://qualys-container-scanner")
def qualys_container_scanner_docs() -> str:
    """Qualys Container Scanner usage documentation."""
    return "https://docs.qualys.com/en/qscanner/latest/qscanner_usage/use_qscanner.htm"


@mcp.resource("docs://qualys-cybersecurity-risk-rating")
def qualys_crs_docs() -> str:
    """Qualys CyberSecurity Risk Rating (CRS) getting started documentation."""
    return "https://docs.qualys.com/en/crs/latest/get_started/get_started.htm"


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_: Request) -> JSONResponse:
    """Load balancer health check (no auth, no Qualys call)."""
    return JSONResponse({"status": "ok"})


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #

def _configure_http(host: str, port: int) -> None:
    mcp.settings.host = host
    mcp.settings.port = port
    # Stateless: no server-side session affinity needed, so any task behind the
    # load balancer can answer any request and the service scales horizontally.
    mcp.settings.stateless_http = True
    allowed_hosts = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    if allowed_hosts:
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed_hosts,
            allowed_origins=[o.strip() for o in os.environ.get("MCP_ALLOWED_ORIGINS", "").split(",") if o.strip()],
        )
    elif host not in ("127.0.0.1", "localhost", "::1"):
        # Behind a load balancer the Host header is the public DNS name; DNS
        # rebinding protection targets localhost servers, so relax it here.
        mcp.settings.transport_security = TransportSecuritySettings(enable_dns_rebinding_protection=False)


if __name__ == "__main__":
    import argparse
    import dotenv

    dotenv.load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)s  %(message)s")

    parser = argparse.ArgumentParser(description="Qualys Container Security MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        help=(
            "Transport to use. 'stdio' (default) runs as a local subprocess launched by "
            "the MCP client. 'http' (streamable-http) hosts the server over the network "
            "at http://<host>:<port>/mcp. 'sse' is for legacy SSE-only clients."
        ),
    )
    parser.add_argument("--host", default=os.environ.get("MCP_HOST", "127.0.0.1"),
                        help="Bind host for http/sse transport (use 0.0.0.0 to accept remote connections).")
    parser.add_argument("--port", type=int, default=int(os.environ.get("MCP_PORT", "8000")),
                        help="Bind port for http/sse transport.")
    parser.add_argument(
        "--auth",
        choices=["env", "headers"],
        default=os.environ.get("QUALYS_AUTH_MODE"),
        help=(
            "Where Qualys credentials come from. 'env' uses QUALYS_* environment variables; "
            "'headers' requires each caller to send their own credentials as HTTP headers. "
            "Defaults to 'env' for stdio and 'headers' for http/sse."
        ),
    )
    args = parser.parse_args()

    if args.transport in ("http", "sse"):
        AUTH_MODE = args.auth or "headers"
        _configure_http(args.host, args.port)
        logger.info("Starting %s transport on %s:%s (auth=%s)", args.transport, args.host, args.port, AUTH_MODE)
        mcp.run(transport="streamable-http" if args.transport == "http" else "sse")
    else:
        AUTH_MODE = args.auth or "env"
        mcp.run(transport="stdio")
