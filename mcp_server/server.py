"""Qualys Container Security MCP server.

This server exposes the Qualys CS API as MCP tools. The tool surface is defined in
``shared/tool_registry.py`` so the backend agent and the MCP server stay in sync.
"""

import os
import sys
from typing import Any

# Make the shared tool registry importable from the project root.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from mcp.server.fastmcp import FastMCP
from qualys_client import get
from shared.tool_registry import TOOLS, build_route

mcp = FastMCP("qualys-cs")


def _make_tool_handler(tool_name: str):
    """Return a handler that routes a tool call through the shared registry."""
    def handler(**kwargs: Any) -> dict:
        path, params = build_route(tool_name, kwargs)
        return get(path, params)
    handler.__name__ = tool_name
    return handler


# Register every tool from the shared registry dynamically.
for tool in TOOLS:
    name = tool["name"]
    description = tool["description"]
    fn = _make_tool_handler(name)
    fn.__doc__ = description
    mcp.add_tool(fn, name=name, description=description)


# Documentation Resources

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


if __name__ == "__main__":
    import dotenv
    dotenv.load_dotenv()
    mcp.run(transport="stdio")
