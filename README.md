# Sheldon — AI assistant for Qualys Container Security

Ask questions about your containers in plain English. Sheldon picks the right
Qualys Container Security (CS) API, fetches **live data from your own Qualys
account**, and answers in seconds — with tables and charts when they help.

> "Show me critical CVEs in running containers" · "Which images have secrets or malware?"
> · "List pods in the prod namespace" · "How do I deploy the sensor with Helm?"

The same 40+ Qualys tools are also available as an **MCP server**, so you can use them
from Cursor, Claude Code or Claude Desktop.

---

## Contents

1. [What's in the box](#whats-in-the-box)
2. [Quick start (local)](#quick-start-local)
3. [Configuration](#configuration)
4. [Who sees what, and who pays](#who-sees-what-and-who-pays)
5. [Deploy to AWS](#deploy-to-aws)
6. [AWS permissions](#aws-permissions)
7. [Use the MCP server](#use-the-mcp-server)
8. [How it works](#how-it-works)
9. [Project structure](#project-structure)
10. [API endpoints](#api-endpoints)
11. [Troubleshooting](#troubleshooting)
12. [Reference: tools and QQL tokens](#reference-tools-and-qql-tokens)
13. [Extending the project](#extending-the-project)

---

## What's in the box

| Part | What it is | Runs on |
|---|---|---|
| **Web app** | Chat with Sheldon + dashboards (containers, images, registries, K8s) | React UI + FastAPI backend, port 8000 |
| **MCP server** | The same Qualys tools for any MCP client | Python, stdio locally or HTTP at `/mcp` when hosted |
| **AWS deployment** | Both of the above on ECS Fargate behind one HTTPS load balancer | `deploy/` — one command |

Everything is answered from **live Qualys API calls**. No vector database, nothing pre-indexed.

---

## Quick start (local)

**You need:** Docker Desktop, a Qualys account with CS API access, and either AWS access
to Amazon Bedrock or an Anthropic API key.

```bash
git clone https://github.com/anmolparida/qualys-container-security-mcp.git
cd qualys-container-security-mcp
cp .env.example .env        # then edit .env (see Configuration)
docker compose up --build
```

| Open | What you get |
|---|---|
| http://localhost:8000 | The web app (sign in with your Qualys URL + API token if prompted) |
| http://localhost:8080/healthz | MCP server health check |

Stop with `Ctrl+C`.

<details>
<summary><b>Run without Docker (for development)</b></summary>

Needs Python 3.11+ and Node.js 18+.

```bash
./start.sh    # installs deps, starts backend :8000 and frontend :5173, tails logs
./stop.sh     # stops both
./logs.sh     # tail logs again
```

Or by hand:

```bash
cd backend && pip install -r requirements.txt && uvicorn main:app --reload --port 8000
cd frontend && npm install && npm run dev      # http://localhost:5173
```

</details>

---

## Configuration

All settings live in `.env` in the repo root (git-ignored — never committed).

| Setting | Example | What it does |
|---|---|---|
| `QUALYS_AUTH_MODE` | `user` | `user`: everyone signs in with **their own** Qualys URL + API token. `service`: everyone shares the account below |
| `QUALYS_URL` | `https://gateway.qg2.apps.qualys.com` | Qualys API gateway for your platform |
| `QUALYS_TOKEN` | `eyJ…` | Qualys API token (or use `QUALYS_USERNAME` + `QUALYS_PASSWORD`). Used in `service` mode and by the local MCP server |
| `LLM_BILLING` | `host` | `host`: the AWS Bedrock access below pays for chat. `user`: each person enters their own AI key |
| `AWS_REGION` | `us-east-1` | Region for Amazon Bedrock |
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-haiku-5-5` | Claude model on Bedrock (`global.…` routes worldwide, `us.…` stays in the US) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | | Optional. If unset, your AWS profile / SSO (or the IAM role on AWS) is used |

> **Claude 3.x models are end-of-life on Bedrock.** Use Claude Haiku 5.5 as above. To list
> what's available in your region:
> `aws bedrock list-foundation-models --by-provider anthropic --region $AWS_REGION --output table`

**Prefer SSO over keys:**

```bash
aws configure sso --profile qualys-kcs && aws sso login --profile qualys-kcs
export AWS_PROFILE=qualys-kcs
```

---

## Who sees what, and who pays

Two independent switches. Pick per deployment.

| Switch | Value | Whose Qualys data / whose AI bill | What a user enters at sign-in |
|---|---|---|---|
| `QUALYS_AUTH_MODE` | `user` *(recommended)* | Each person sees **only their own** Qualys data | Qualys platform URL + API token |
| | `service` | Everyone sees one shared account's data | Nothing |
| `LLM_BILLING` | `host` *(default)* | **You** pay for every chat (your Bedrock) | Nothing |
| | `user` | **Each person** pays for their own chats | Their Anthropic API key, or Amazon Bedrock API key + region |

- **Dashboards** never call the AI model, so they cost no AI tokens.
- **MCP users** always pay through their own AI client (Cursor / Claude), whatever `LLM_BILLING` says.
- Keys and tokens are sent only to this app, used for that one request, and **never stored or logged** on the server.

**Getting a Qualys API token:** generate one in the Qualys UI where your platform offers it, or:

```bash
curl -s -X POST https://gateway.qg2.apps.qualys.com/auth \
  -d "username=$QUALYS_USERNAME&password=$QUALYS_PASSWORD&token=true"
```

---

## Deploy to AWS

Both the web app and the MCP server run on **ECS Fargate** behind one HTTPS load balancer:
`https://your-host/` → web app, `https://your-host/mcp` → MCP server.

```bash
cp deploy/aws/params.example.env deploy/aws/params.env   # VPC, subnets, certificate, the two switches
deploy/aws/deploy.sh all                                  # build, push, deploy
```

Then point your DNS name at the `LoadBalancerDnsName` output. Full step-by-step guide,
settings and operations: **[DEPLOYMENT.md](DEPLOYMENT.md)**.

---

## AWS permissions

Three different identities need AWS access. Grant only the one you need.

### 1. The person who runs `deploy.sh`

Needs to create the stack's ECR repositories, ECS cluster and services, load balancer,
security groups, IAM roles and log groups.

- **Least-privilege policy:** [`deploy/aws/deployer-iam-policy.json`](deploy/aws/deployer-iam-policy.json).
  Attach it to the deploying user or role. It is scoped to resources named `qualys-kcs*`,
  so keep `STACK_NAME` starting with `qualys-kcs` (or edit the policy).

  ```bash
  aws iam create-policy --policy-name qualys-kcs-deployer \
    --policy-document file://deploy/aws/deployer-iam-policy.json
  aws iam attach-user-policy --user-name <you> \
    --policy-arn arn:aws:iam::<account-id>:policy/qualys-kcs-deployer
  ```

- **Quick alternative:** `AdministratorAccess` in a sandbox account.

| Service | Why |
|---|---|
| CloudFormation | Create / update the `qualys-kcs*` stack |
| ECR | Create the two image repositories and push images |
| ECS | Cluster, task definitions, services |
| Elastic Load Balancing | Load balancer, target groups, HTTPS listener, `/mcp` rule |
| EC2 | Read VPC / subnets; create the two security groups |
| IAM | Create the app's two roles and pass them to ECS (+ first-time service-linked roles) |
| CloudWatch Logs | Two log groups |
| Secrets Manager | Only for `QUALYS_AUTH_MODE=service` (shared Qualys account) |
| ACM | Read the TLS certificate |

### 2. The running app (created for you)

The CloudFormation template creates these — nothing to set up by hand.

| Role | Permissions | When |
|---|---|---|
| Task execution role | Pull images from ECR, write logs (`AmazonECSTaskExecutionRolePolicy`); read the Qualys secret | Always; secret only in `service` mode |
| Web app task role | `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream` | Only when `LLM_BILLING=host` |
| MCP server | **No** AWS permissions | — |

### 3. People using the app

| Situation | What they need |
|---|---|
| Running locally with `LLM_BILLING=host` | An AWS profile / keys with `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream`, and **model access** enabled for Claude Haiku 5.5 in the Bedrock console |
| Hosted, `LLM_BILLING=user`, using a **Bedrock API key** | A key from *Bedrock console → API keys* in their own account. Long-term keys get `AmazonBedrockLimitedAccess` by default; the minimum is `bedrock:CallWithBearerToken` + `bedrock:InvokeModel` + `bedrock:InvokeModelWithResponseStream`, plus model access enabled. AWS recommends short-term keys (max 12 h) outside experiments |
| Hosted, `LLM_BILLING=user`, using an **Anthropic API key** | No AWS permissions — just a key from console.anthropic.com |
| Using only the MCP server | No AWS permissions |

Minimal IAM policy for a person's own Bedrock access:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "bedrock:CallWithBearerToken",
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream"
    ],
    "Resource": "*"
  }]
}
```

(`bedrock:CallWithBearerToken` is only needed when using a Bedrock API key.)

---

## Use the MCP server

The MCP server exposes the same Qualys tools to any MCP client. Your AI client does the
thinking (and pays for its own tokens); the server only calls Qualys.

### Hosted (recommended)

Point your client at `https://your-host/mcp` and send your own Qualys URL + token as headers.

**Cursor** — `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "qualys-cs": {
      "url": "https://your-host/mcp",
      "headers": {
        "X-Qualys-Url": "https://gateway.qg2.apps.qualys.com",
        "X-Qualys-Token": "${env:QUALYS_TOKEN}"
      }
    }
  }
}
```

**Claude Code:**

```bash
claude mcp add --transport http qualys-cs https://your-host/mcp \
  --header "X-Qualys-Url: https://gateway.qg2.apps.qualys.com" \
  --header "X-Qualys-Token: $QUALYS_TOKEN"
```

Claude Desktop and more: see [DEPLOYMENT.md](DEPLOYMENT.md#connecting-an-mcp-client-to-the-hosted-server).

### Local (stdio)

Runs on your machine and reads `QUALYS_URL` + `QUALYS_TOKEN` from `.env`.

```bash
pip install -r mcp_server/requirements.txt
```

```json
{
  "mcpServers": {
    "qualys-cs": {
      "command": "python",
      "args": ["/path/to/qualys-container-security-mcp/mcp_server/server.py"]
    }
  }
}
```

Step-by-step for non-developers: [mcp_access_guide.md](mcp_access_guide.md).

---

## How it works

1. You ask a question in the chat.
2. The backend sends it to **Claude** with the list of 40+ Qualys tools.
3. Claude picks the tool(s); the backend calls the **Qualys CS API** with *your* token — in parallel when it can.
4. Claude turns the live results into an answer, table or chart, streamed back to you.

```
 Browser (React UI)                      MCP client (Cursor / Claude)
        │  Qualys URL + token                  │  Qualys URL + token (headers)
        ▼                                       ▼
 FastAPI backend :8000 ──▶ Claude         MCP server :8080 / stdio
        │      (your Bedrock, or the user's           │
        │       own Anthropic / Bedrock key)          │
        └──────────────┬────────────────────────────────┘
                       ▼
          Shared tool registry (40+ tools, one definition)
                       ▼
             Qualys CS API — live data, per user
```

**Design choices**

- **One tool registry** (`shared/tool_registry.py`) feeds both the web agent and the MCP server. Add a tool once, it works everywhere.
- **Per-user credentials** (`shared/qualys_auth.py`) — only Qualys gateway domains are allowed, tokens cached per user, never logged.
- **No RAG** — answers come from the live API, so they're always current.

---

## Project structure

```
├── backend/                 FastAPI app
│   ├── main.py              App, per-user auth middleware, serves the built UI
│   ├── agent.py             Chat agent: Claude + tool calling
│   ├── llm.py               Who pays for AI (LLM_BILLING) — host Bedrock or user's key
│   ├── qualys_client.py     Qualys API client (per-request credentials)
│   └── routes/              /api/chat and /api/dashboard/*
├── frontend/src/            React UI
│   ├── App.tsx              Layout, sign-in gate, account switcher
│   ├── components/QualysSignIn.tsx   Sign-in: Qualys URL + token, optional AI key
│   ├── lib/                 API client, credential storage
│   └── pages/               Chat and dashboards
├── mcp_server/              MCP server (stdio or HTTP)
├── shared/
│   ├── tool_registry.py     The 40+ Qualys tools (single source of truth)
│   └── qualys_auth.py       Credential parsing, gateway allowlist, token cache
├── deploy/
│   ├── web.Dockerfile, mcp.Dockerfile
│   └── aws/                 cloudformation.yaml, deploy.sh, params.example.env, deployer-iam-policy.json
├── docker-compose.yml       Run both containers locally
├── DEPLOYMENT.md            Full AWS guide
├── mcp_access_guide.md      MCP setup for non-developers
└── .env.example             Settings template
```

---

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/config` | Tells the UI which sign-in fields to show (`auth_mode`, `llm_billing`) |
| GET | `/api/session` | Validates the caller's Qualys URL + token |
| POST | `/api/llm/check` | Validates the caller's own AI key (`LLM_BILLING=user`) |
| POST | `/api/chat/` | Chat — streams the answer as plain text |
| GET | `/api/dashboard/containers/overview` | Container counts and riskiest containers |
| GET | `/api/dashboard/images/vulnerabilities` | Image vulnerability summary |
| GET | `/api/dashboard/registry/health` | Registries |
| GET | `/api/dashboard/k8s/posture` | Kubernetes posture |
| GET | `/api/dashboard/sensors/overview` | Sensors |
| POST | `/docs/refresh` | Refresh the cached Qualys docs |

Per-user headers: `X-Qualys-Url` + `X-Qualys-Token` on `/api/*`; with `LLM_BILLING=user`,
also `X-LLM-Provider`, `X-LLM-Api-Key`, `X-LLM-Region`, `X-LLM-Model` on `/api/chat/`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `404 … model version has reached the end of its life` | You're on a Claude 3.x model. Set `BEDROCK_MODEL_ID=us.anthropic.claude-haiku-5-5` (or `global.…`) |
| `AccessDenied` / not authorized from Bedrock | Enable **model access** for Claude Haiku 5.5 in the Bedrock console; check the IAM permissions above |
| `Qualys rejected the API token` | Token expired or wrong platform — generate a new one and pick the right gateway URL |
| `not an allowed Qualys gateway` | Use the bare gateway URL, e.g. `https://gateway.qg2.apps.qualys.com` |
| `The AI provider rejected your API key` | Check the Anthropic / Bedrock key and, for Bedrock, its region |
| Port 8000 or 5173 already in use | `./stop.sh`, or `lsof -ti:8000 \| xargs kill -9` |
| UI on another origin can't reach the API | Add it to `CORS_ORIGINS` (comma-separated) |
| Anything else | `docker compose logs -f web`, or `./logs.sh` without Docker |

---

## Reference: tools and QQL tokens

<details>
<summary><b>Available tools (40+)</b> — defined once in <code>shared/tool_registry.py</code></summary>

**Containers:** `list_containers`, `get_container_details`, `get_container_vulns`,
`get_container_vuln_count`, `get_container_software`, `get_container_compliance`,
`list_containers_bulk`

**Images:** `list_images`, `get_image_details`, `get_image_vulns`, `get_image_vuln_count`,
`get_image_software`, `get_image_compliance`, `get_image_secrets`, `get_image_malware`,
`find_images_with_secrets`, `find_images_with_malware`, `find_images_by_vuln_severity`,
`find_containers_by_vuln_severity`, `get_image_association`, `list_images_bulk`

**Registries & Kubernetes:** `list_registries`, `get_registry_details`,
`get_registry_repositories`, `get_registry_schedules`, `list_sensors`,
`get_sensor_details`, `list_k8s_clusters`, `get_k8s_cluster`, `list_k8s_pods`

</details>

<details>
<summary><b>QQL filter tokens</b> — usable directly in questions</summary>

| Question | Use with | Filter |
|---|---|---|
| CISA Known Exploited Vulnerabilities | vulnerabilities | `threatIntel.cisaKnownExploitedVulns:true` |
| Critical vulnerabilities | vulnerabilities | `severity:5` |
| Under active attack | vulnerabilities | `threatIntel.activeAttacks:true` |
| Images with secrets | images | `container.image.hasSecrets:true` |
| Images with malware | images | `image.malware.count>0` |
| Images used in the last 24h | images | `container.image.lastUsedDate:[now-1d ... now]` |
| Running containers | containers | `container.instance.state:RUNNING` |
| Containers running as root | containers | `container.instance.isRoot:true` |
| Software reaching EOL in 3 months | software | `software.lifecycle.eol:[now ... now+3M]` |

Tokens differ by resource, and severity is a number (5 = critical). Full catalog:
`shared/qql_catalog.txt` · [Qualys docs](https://docs.qualys.com/en/cs/latest/search_tips/search_tokens.htm)

</details>

### How Sheldon gets filters right

Sheldon doesn't guess filter tokens any more:

1. **Verified examples** (`shared/qql_examples.txt`) are put in its instructions, so common questions use a known-good filter straight away.
2. **`lookup_qql_tokens` tool** searches the documented tokens (`shared/qql_catalog.txt`) without calling Qualys.
3. **Pre-flight check** — before a call goes to Qualys, every token in the `filter` is checked against the catalog for that resource. An unknown token is stopped and the closest real tokens are suggested (e.g. `vulnerability.kevs` → `threatIntel.cisaKnownExploitedVulns`), saving a slow wasted call. If the model repeats the exact same call it's let through, in case the catalog is missing a token. Turn off with `QQL_CHECK=off`.

**To teach it a new filter:** add a line to `shared/qql_examples.txt`
(`question | resource | filter`) once you've confirmed it works. For a token the catalog
doesn't know, add it to `shared/qql_catalog.txt`. Both the chat and the MCP server pick it
up on restart.

---

## Extending the project

| To… | Do this |
|---|---|
| Add a Qualys tool | Add it to `shared/tool_registry.py` — it appears in the chat **and** the MCP server |
| Teach Sheldon when to use it | Update the system prompt in `backend/agent.py` |
| Add a UI page | Create it in `frontend/src/pages/` and register it in `App.tsx` |

Secrets stay out of git: `.env`, logs and build output are all in `.gitignore`.

## License

MIT
