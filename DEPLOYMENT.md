# Deploying to AWS (ECS Fargate)

This deploys **both** parts of the project behind one HTTPS load balancer:

| Path | Service | Whose Qualys data | AWS permissions |
|---|---|---|---|
| `/` (UI) and `/api/*` | **Web app** — React UI + FastAPI + Claude on Bedrock | Each user's own (they sign in with their Qualys URL + API token). Optional shared-account mode. | Task role: `bedrock:InvokeModel*` |
| `/mcp` | **MCP server** — streamable HTTP | Each user's own (their MCP client sends URL + token as headers) | None |

```
            ┌──────────────── ALB (HTTPS 443, idle timeout 300s) ────────────────┐
 browser ──▶│  default ─▶ [optional OIDC sign-in] ─▶ web target group  :8000     │
 MCP client▶│  /mcp, /mcp/* ─────────────────────────▶ mcp target group  :8080   │
            └─────────────────────────────────────────────────────────────────────┘
                     │                                        │
              ECS service "web"                         ECS service "mcp"
    (X-Qualys-Url + X-Qualys-Token per request,   (X-Qualys-Url + X-Qualys-Token per
     task role → Bedrock)                           request; stateless)
```

| File | Purpose |
|---|---|
| `deploy/web.Dockerfile` | Builds the React UI and bundles it with the FastAPI backend (one container) |
| `deploy/mcp.Dockerfile` | MCP server in HTTP mode with per-user credentials |
| `docker-compose.yml` | Runs both images locally, same as on AWS |
| `deploy/aws/cloudformation.yaml` | ALB, ECS cluster/services, IAM roles, security groups, log groups |
| `deploy/aws/deploy.sh` | Creates ECR repos, builds/pushes `linux/amd64` images, deploys the stack |
| `deploy/aws/params.example.env` | Settings for `deploy.sh` |

---

## Qualys credentials: URL + API token, per user

Every Qualys call is made with the **caller's own** Qualys gateway URL and API
token, so each person sees exactly the data their Qualys account can see.
Nothing is stored on the server.

| Where | How the URL + token get there |
|---|---|
| Web app | User clicks **Sign in to Qualys**, picks their platform (gateway URL) and pastes their API token. The token is checked against Qualys, kept in the browser tab (or the device, if "Remember" is ticked), and sent with each request as `X-Qualys-Url` / `X-Qualys-Token`. Sidebar shows the account with **Switch** and **Sign out**; switching clears all cached data and chat. |
| MCP server | The user's MCP client config sends `X-Qualys-Url` + `X-Qualys-Token` headers (see below). |
| Local stdio MCP / service mode | `.env`: `QUALYS_URL` + `QUALYS_TOKEN` (or `QUALYS_USERNAME` + `QUALYS_PASSWORD`). |

Accepted request headers (both services):

| Header | Value |
|---|---|
| `X-Qualys-Url` | The Qualys API gateway, e.g. `https://gateway.qg2.apps.qualys.com` |
| `X-Qualys-Token` | The user's Qualys API token (`Authorization: Bearer <token>` also works) |
| `X-Qualys-Username` + `X-Qualys-Password` | Alternative to a token (`Authorization: Basic` also works); exchanged at `<url>/auth` |

Rules enforced by the server: the URL must be `https://` on a Qualys gateway domain
(`*.qualys.com`, `*.qualys.eu`, `*.qualys.in`, `*.qualys.ca`, `*.qualys.ae`,
`*.qualys.co.uk`, `*.qualys.com.au`, `*.qualysksa.com`; override with
`QUALYS_ALLOWED_HOST_SUFFIXES`); credentials are never logged; an expired or
invalid token returns HTTP 401 and the web app asks the user to sign in again.

**Getting an API token:** generate one in the Qualys UI where your platform offers
it, or exchange your login for one:

```bash
curl -s -X POST https://gateway.qg2.apps.qualys.com/auth \
  -d "username=$QUALYS_USERNAME&password=$QUALYS_PASSWORD&token=true"
```

Tokens expire (check your platform's lifetime); paste a new one when prompted.

**Shared-account mode (optional):** set `QUALYS_AUTH_MODE=service` to skip
per-user sign-in on the web app. Everyone then sees one account's data, stored
in Secrets Manager by `deploy.sh secret`. The MCP server is always per-user.

---

## Who pays for AI tokens: `LLM_BILLING`

Choose at deploy time with `LLM_BILLING` in `deploy/aws/params.env` (or `.env` locally):

| `LLM_BILLING` | Who pays for Sheldon chat | What each user enters at sign-in |
|---|---|---|
| `host` (default) | **You**: the AWS account the app runs in (Amazon Bedrock, via the task IAM role) | Nothing extra |
| `user` | **Each user**, on their own AI account | Their own **Anthropic API key**, or their own **Amazon Bedrock API key** + its AWS region |

Dashboards never call the AI model, so they cost no AI tokens in either mode. MCP
users always pay through their own AI client (Cursor, Claude), whatever this is set to.

**Turn on user-pays:**

1. In `deploy/aws/params.env` set `LLM_BILLING=user`.
2. Run `deploy/aws/deploy.sh deploy` (or `all` if the code changed). The app's IAM
   role loses its Bedrock permission, so your account can't be billed for chat.
3. Each user opens the app → **Sign in** → under *AI model (billed to you)* picks a provider:
   - **Anthropic API key** — create one at console.anthropic.com → API keys (`sk-ant-…`).
     Default model `claude-haiku-5-5`.
   - **Amazon Bedrock API key** — in their own AWS account: Bedrock console → API keys →
     generate a key, and enable model access for Claude Haiku 5.5. Pick the key's region.
     Default model `global.anthropic.claude-haiku-5-5`.
   - *Model ID* is optional, for anyone who wants a different Claude model.
4. The app checks the key with a tiny request (a few tokens on the user's account),
   then sends it with each chat request as headers. It is held in memory for that
   request only — never stored on the server or logged. In the browser it lives in
   the tab (or the device, if *Remember* is ticked); **Sign out** clears it.

Headers the backend accepts on `/api/chat` when `LLM_BILLING=user`:

| Header | Value |
|---|---|
| `X-LLM-Provider` | `anthropic` or `bedrock` |
| `X-LLM-Api-Key` | The user's Anthropic API key, or Amazon Bedrock API key |
| `X-LLM-Region` | AWS region of the Bedrock key (bedrock only, default `us-east-1`) |
| `X-LLM-Model` | Optional model ID override |

---

## Prerequisites

- AWS CLI v2 logged in to the target account, Docker with `buildx`, git.
- An existing **VPC** with ≥ 2 subnets for the ALB and subnets for the tasks that
  have outbound internet (NAT) — tasks call Qualys, Bedrock and ECR.
- An **ACM certificate** in the same region for the DNS name you'll use
  (e.g. `kcs.example.com`). HTTPS is mandatory: tokens travel in headers.
- **Bedrock model access** enabled for `BEDROCK_MODEL_ID` in `BEDROCK_REGION` (only for `LLM_BILLING=host`).
- **IAM permissions for whoever runs `deploy.sh`:** attach
  [`deploy/aws/deployer-iam-policy.json`](deploy/aws/deployer-iam-policy.json) (scoped to
  resources named `qualys-kcs*`, so keep `STACK_NAME` starting with `qualys-kcs`), or use
  `AdministratorAccess` in a sandbox account. The app's own runtime roles are created by the
  template. Full breakdown, including what end users need: README → *AWS permissions*.

## Deploy

```bash
cp deploy/aws/params.example.env deploy/aws/params.env   # fill in VPC, subnets, cert, etc.
# QUALYS_AUTH_MODE=user (default) needs no Qualys secret.
# Only for QUALYS_AUTH_MODE=service:  deploy/aws/deploy.sh secret
deploy/aws/deploy.sh all      # build + push both images, then create/update the stack
```

Then point your DNS name at the `LoadBalancerDnsName` output (CNAME or Route 53 alias).

- Web app: `https://kcs.example.com/` → each user signs in with their Qualys URL + token
- MCP server: `https://kcs.example.com/mcp`

Later releases: `deploy/aws/deploy.sh all` again. Images are tagged
`<git-sha>-<timestamp>`; ECS does a rolling update and rolls back automatically
if the new tasks fail health checks. Other sub-commands: `build`, `deploy`
(re-uses the last built tag, or `IMAGE_TAG=...`), `outputs`.

## Access control

- Defaults: `ALB_SCHEME=internal`, `ALLOWED_INGRESS_CIDR=10.0.0.0/8` — reachable
  only from inside the VPC / corporate network.
- In `user` mode nobody sees Qualys data without their own valid token, but
  anyone who can reach the web app can still use Sheldon's Bedrock budget for
  documentation questions. Before going public, also enable the ALB's OIDC
  sign-in (Okta, Entra ID, …): fill in the `OIDC_*` settings and export
  `OIDC_CLIENT_SECRET` before `deploy.sh deploy`. Redirect URI to register:
  `https://<your-dns>/oauth2/idpresponse`.
- `/mcp` skips OIDC (MCP clients can't do a browser sign-in); Qualys checks
  every request's token.

## Connecting an MCP client to the hosted server

**Cursor** — `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "qualys-cs": {
      "url": "https://kcs.example.com/mcp",
      "headers": {
        "X-Qualys-Url": "https://gateway.qg2.apps.qualys.com",
        "X-Qualys-Token": "${env:QUALYS_TOKEN}"
      }
    }
  }
}
```

**Claude Code**:

```bash
claude mcp add --transport http qualys-cs https://kcs.example.com/mcp \
  --header "X-Qualys-Url: https://gateway.qg2.apps.qualys.com" \
  --header "X-Qualys-Token: $QUALYS_TOKEN"
```

**Claude Desktop** (via the `mcp-remote` bridge) — `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "qualys-cs": {
      "command": "npx",
      "args": [
        "-y", "mcp-remote", "https://kcs.example.com/mcp",
        "--header", "X-Qualys-Url:${QUALYS_URL}",
        "--header", "X-Qualys-Token:${QUALYS_TOKEN}"
      ],
      "env": {
        "QUALYS_URL": "https://gateway.qg2.apps.qualys.com",
        "QUALYS_TOKEN": "your_api_token"
      }
    }
  }
}
```

The local stdio setup in `MCP_ACCESS_GUIDE.md` still works unchanged.

## Run the containers locally

```bash
cp .env.example .env          # set QUALYS_AUTH_MODE, AWS values (and Qualys values for service mode)
docker compose up --build
# Web app  → http://localhost:8000
# MCP      → http://localhost:8080/mcp   (send X-Qualys-Url + X-Qualys-Token)
```

## Configuration reference

**Web app**

| Variable | Meaning |
|---|---|
| `QUALYS_AUTH_MODE` | `user` (each person signs in with URL + token) or `service` (one shared account). Default `service` locally, `user` on AWS |
| `QUALYS_URL` + `QUALYS_TOKEN` (or `QUALYS_USERNAME` + `QUALYS_PASSWORD`) | Shared account, service mode only (Secrets Manager on AWS) |
| `LLM_BILLING` | `host` (the app's Bedrock pays) or `user` (each person's own Anthropic / Bedrock API key pays) |
| `AWS_REGION`, `BEDROCK_MODEL_ID` | Bedrock settings for `host` billing (and the default model for user Bedrock keys). AWS keys are optional — on ECS the task role is used |
| `ANTHROPIC_MODEL_ID` | Default model for user Anthropic keys (`claude-haiku-5-5`) |
| `CORS_ORIGINS` | Comma-separated browser origins (only if the UI is served from another origin) |
| `QUALYS_ALLOWED_HOST_SUFFIXES` | Override the allowed Qualys gateway domains |

Endpoints: `GET /health` (load balancer), `GET /api/config` (auth mode), `GET /api/session` (validates the caller's token).

**MCP server** (env vars or CLI flags)

| Variable | Default | Meaning |
|---|---|---|
| `MCP_TRANSPORT` / `--transport` | `stdio` (`http` in the image) | `stdio`, `http` (streamable HTTP at `/mcp`), `sse` |
| `MCP_HOST` / `--host`, `MCP_PORT` / `--port` | `127.0.0.1`, `8000` (`0.0.0.0`, `8080` in the image) | Bind address |
| `QUALYS_AUTH_MODE` / `--auth` | `env` for stdio, `headers` for http/sse | Where Qualys credentials come from |
| `QUALYS_URL` | — | Default gateway when `X-Qualys-Url` is omitted |
| `MCP_ALLOWED_HOSTS` / `MCP_ALLOWED_ORIGINS` | — | Enables DNS-rebinding protection with these `Host` / `Origin` values |

Health check: `GET /healthz`.

## Operations

- **Logs:** CloudWatch log groups `/ecs/<stack>/web` and `/ecs/<stack>/mcp` (30-day retention).
- **Scaling:** both services are stateless; raise `WebDesiredCount` / `McpDesiredCount`.
- **Switch modes:** change `QUALYS_AUTH_MODE` in `params.env` and run `deploy/aws/deploy.sh deploy`.
- **Tear down:** `aws cloudformation delete-stack --stack-name <stack>` (ECR repos and any secret are kept).
