# Qualys CS MCP server, hosted over streamable HTTP at /mcp.
# Each caller supplies their own Qualys credentials via request headers.
# Build from the repo root:  docker build -f deploy/mcp.Dockerfile -t qualys-cs-mcp .
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8080 \
    QUALYS_AUTH_MODE=headers
WORKDIR /app

COPY mcp_server/requirements.txt mcp_server/requirements.txt
RUN pip install -r mcp_server/requirements.txt

COPY shared/ shared/
COPY mcp_server/ mcp_server/

RUN useradd --system --uid 10001 app && chown -R app /app
USER app

WORKDIR /app/mcp_server
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=4).status==200 else 1)"
CMD ["python", "server.py"]
