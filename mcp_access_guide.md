# Connecting to the Qualys Container Security MCP Server

This guide is for anyone who wants to use the **MCP server** in this project —
not the web chat app. It covers exactly what you need, what it costs, and how
to wire it into your AI client (Cursor, Claude Desktop, Claude Code, or any
other MCP-compatible tool).

If you just want the fastest path and only use Cursor, see
[`mcp_server/README.md`](mcp_server/README.md) instead — it's a shorter,
non-technical walkthrough. This guide covers the same ground plus more
clients and the cost/credentials question in full.

---

## What you get

Once connected, you can ask your AI assistant things like:

- "List my running containers"
- "Show me images with critical vulnerabilities"
- "Which images have detected secrets or malware?"
- "List my Kubernetes pods in the prod namespace"

Your assistant calls the Qualys Container Security API live and answers from
real data in your account — nothing is cached or pre-indexed.

---

## What you need (and who pays for what)

| Requirement | Whose account | Notes |
|---|---|---|
| Qualys Container Security API access | **Yours** | Own username/password with CS API enabled |
| An MCP-compatible AI client (Cursor, Claude Desktop, Claude Code, etc.) | **Yours** | You bring your own subscription |
| AI model / LLM tokens | **Yours** | See below — this is the important part |
| AWS / Amazon Bedrock account | **Nobody** | Not needed for the MCP server at all |
| Python 3.11+ | Local machine | To run the MCP server process |

### Whose tokens get used?

**Yours — always.** The MCP server itself contains no AI model. It's a thin
tool layer: it takes a request from your AI client, calls the Qualys API,
and returns raw data. All the "thinking" — reading your question, deciding
which tool to call, writing the final answer — happens inside *your* AI
client, using *your own* subscription:

- If you connect via **Cursor**, Cursor's own AI usage/tokens are consumed.
- If you connect via **Claude Desktop or Claude Code**, your own Claude
  subscription's usage is consumed.
- The project owner's AWS Bedrock account (used only by the separate web
  chat app in this repo) is **never** touched by the MCP path.

### Whose Qualys account gets used?

**Yours.** Each person runs their own copy of the MCP server locally with
their own `QUALYS_TOKEN` (or `QUALYS_USERNAME` / `QUALYS_PASSWORD`) in their own `.env` file.
API calls run against your own Qualys account and count against your own
account's API limits — not the project owner's.

You can either run your own local instance (below), or connect to a **hosted**
instance if your team has deployed one (see [`DEPLOYMENT.md`](DEPLOYMENT.md#connecting-an-mcp-client-to-the-hosted-server)).
The hosted server stores no Qualys credentials: your client sends your own
Qualys URL and API token as headers on each request, so calls still run against
your own Qualys account and you see only your own data.

---

## Step 1 — Get your Qualys credentials

Ask your Qualys administrator for:

- `QUALYS_USERNAME`
- `QUALYS_PASSWORD`
- `QUALYS_URL` — e.g. `https://gateway.qg2.apps.qualys.com` (varies
  by Qualys platform/pod — confirm yours with your admin)

Your account must have **Container Security API access** enabled.

---

## Step 2 — Get the project and install dependencies

```bash
git clone <repo-url-from-your-admin>
cd qualys-container-security-mcp
pip3 install -r mcp_server/requirements.txt
```

You only need Python and the `mcp_server` dependencies — you do **not** need
to install the frontend or backend, and you do **not** need AWS credentials.

---

## Step 3 — Configure your `.env`

```bash
cp .env.example .env
```

Edit `.env` and fill in only the Qualys section:

```env
QUALYS_USERNAME=your-qualys-username
QUALYS_PASSWORD=your-qualys-password
QUALYS_URL=https://gateway.qg2.apps.qualys.com
```

Leave the AWS/Bedrock variables blank — they're unused by the MCP server.
`.env` is git-ignored, so your credentials are never committed.

---

## Step 4 — Point your AI client at the server

The server uses `stdio` transport, so any MCP-compatible client works by
launching it as a local process. Use the full absolute path to
`mcp_server/server.py` on your machine.

### Cursor

Command palette (`Cmd/Ctrl+Shift+P`) → **Open MCP Settings**, then add:

```json
{
  "mcpServers": {
    "qualys-cs": {
      "command": "python3",
      "args": ["/absolute/path/to/qualys-container-security-mcp/mcp_server/server.py"]
    }
  }
}
```

### Claude Desktop

Edit the config file:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "qualys-cs": {
      "command": "python3",
      "args": ["/absolute/path/to/qualys-container-security-mcp/mcp_server/server.py"]
    }
  }
}
```

Restart Claude Desktop after saving.

### Claude Code

From the project directory (or any directory):

```bash
claude mcp add qualys-cs python3 /absolute/path/to/qualys-container-security-mcp/mcp_server/server.py
```

Or add the same JSON block shown above to a `.mcp.json` file.

### Any other MCP client

Use the same pattern — command `python3`, single argument being the
absolute path to `mcp_server/server.py`. The server reads `.env` from the
project root automatically at startup, so no credentials need to go in the
client config itself.

---

## Step 5 — Verify it works

Start a new chat in your client and ask:

```
List my running containers
```

Your client should show it invoking the `qualys-cs` MCP server and return
live results from your Qualys account.

---

## Available tools

40+ tools are exposed, covering:

- **Containers** — list, details, vulnerabilities, software (SBOM), compliance
- **Images** — list, details, vulnerabilities, secrets, malware, compliance
- **Registries** — list, details, repositories, scan schedules
- **Sensors** — list, details
- **Kubernetes** — clusters, pods

Full list in the main [`README.md`](README.md#available-tools). All tools
are defined once in `shared/tool_registry.py` and shared between the MCP
server and the web chat app.

---

## Troubleshooting

**"command not found: python3"** — install Python 3.11+ from
https://www.python.org/downloads/.

**"ModuleNotFoundError"** — re-run `pip3 install -r mcp_server/requirements.txt`.

**Client says the server isn't running** — double-check the path in your
client config points exactly to `mcp_server/server.py`, and that `.env`
exists in the project root with all three Qualys variables filled in.

**401 / 403 errors** — your Qualys username/password is wrong, or your
account lacks Container Security API access. Contact your Qualys admin.

**Updating to the latest tools** — `git pull` in the project directory, then
re-run `pip3 install -r mcp_server/requirements.txt` if dependencies changed.
Restart your AI client afterward.
