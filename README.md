# Qualys KCS — AI Security Intelligence Platform

An AI-powered Kubernetes & Container Security intelligence platform built on top of the **Qualys Container Security (CS)** API. It combines a Python MCP (Model Context Protocol) server, a FastAPI backend orchestrator, and a React + Tailwind frontend to let security teams ask natural-language questions about containers, images, vulnerabilities, registries, Kubernetes clusters, and sensors — powered by **Sheldon**, the AI assistant.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [How It Works](#how-it-works)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Running Locally](#running-locally)
- [Project Structure](#project-structure)
- [API Endpoints](#api-endpoints)
- [MCP Tools](#mcp-tools)
- [Known Filter Tokens](#known-filter-tokens)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Overview

**Sheldon** is an AI assistant for Qualys Container Security. It uses a tool-calling agent pattern (not RAG) — all data is fetched live from the Qualys CS API at query time, so results are always current. It enables conversational exploration of:

- Container and image inventories
- Vulnerability counts and details (CVE, severity, affected components)
- Detected secrets and malware in images
- Software bills of materials (SBOM) for containers/images
- Policy compliance and security posture
- Registries and repositories
- Kubernetes clusters, pods, namespaces, and sensors
- Security posture dashboards and summaries
- Inline chart visualizations (pie, bar, line) rendered from agent output

The backend uses **Claude on Amazon Bedrock** for reasoning and tool selection. There is no vector database or embedding layer — the agent calls Qualys APIs directly via structured tools.

## Architecture

```
┌──────────────┐      ┌──────────────┐      ┌─────────────────┐
│   React UI   │──────▶│  FastAPI     │──────▶│  Anthropic      │
│  (port 5173) │      │  Backend     │      │  Claude Bedrock │
└──────────────┘      │  (port 8000) │      └────────┬────────┘
                      └──────────────┘               │
                             │                       │
                             │                       │
                             ▼                       ▼
                      ┌──────────────┐      ┌─────────────────┐
                      │  MCP Server  │──────▶│  Qualys CS API  │
                      │  (stdio)     │      │                 │
                      └──────────────┘      └─────────────────┘
```

- **Frontend**: Vite + React + TypeScript + Tailwind CSS + Lucide icons + Recharts
- **Backend**: FastAPI + Uvicorn + Anthropic Bedrock client + custom agent loop
- **MCP Server**: Python FastMCP server that wraps the Qualys Container Security REST API
- **Qualys API**: Uses the official Qualys Container Security API endpoints for live data

## How It Works

When a user asks a question in the **Sheldon** chat, the following steps happen:

1. **User submits a prompt** in the React frontend at `http://localhost:5173`.
2. The frontend sends the message + conversation history to the FastAPI backend via a POST to `/api/chat/` with a streaming response.
3. The backend starts the agent loop in `backend/agent.py`, truncating/sanitising the history to avoid Anthropic API errors (orphaned tool_results, consecutive same-role messages, empty lists).
4. The agent calls **Claude on Amazon Bedrock** with the system prompt, tool definitions, and sanitised history.
5. Claude decides whether it needs data. If so, it returns `tool_use` blocks.
6. The agent executes all tool calls in parallel via `asyncio.gather` using the shared async `httpx` client in `backend/qualys_client.py`.
7. Tool results are returned as `tool_result` blocks. Claude reasons over the data and produces a final answer.
8. **Only the final answer is streamed to the UI** — intermediate tool-use text is suppressed.
9. The frontend renders the streaming text, parses markdown tables into styled tables and `chart` code blocks into Recharts visualizations.
10. Conversation history is stored in the browser session only — nothing is persisted server-side.

Dashboard tabs (Containers, Images, Registry, K8s) bypass the LLM and call the Qualys API directly through the backend for faster summary views.

### Agent Architecture Notes

- **No RAG / no vector DB** — all data is fetched live from Qualys APIs
- **Shared tool registry** (`shared/tool_registry.py`) — single source of truth for tool definitions used by both the agent and the MCP server
- **Async tool calls** — agent calls are fully async; dashboard routes use sync calls (blocking, acceptable for low-concurrency use)
- **No max concurrency cap** on parallel tool calls — Qualys API rate limits apply
- **No max turn limit** — Claude self-limits but a runaway query could loop; monitor `backend.log`

## Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- macOS, Linux, or WSL
- A Qualys account with Container Security API access
- AWS credentials configured with access to Amazon Bedrock (Claude model)

## Configuration

Create a `.env` file in the project root by copying the example:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Qualys Container Security API
QUALYS_USERNAME=your-qualys-username
QUALYS_PASSWORD=your-qualys-password
QUALYS_PLATFORM_URL=https://gateway.qg2.apps.qualys.com

# AWS Bedrock (for the LLM agent)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-3-5-sonnet-20241022-v2:0
```

> **Note**: `.env` is listed in `.gitignore` and will **never** be committed. Only `.env.example` and `.env.template` are tracked as templates.

> **Model IDs**: Bedrock model IDs change over time. Use the AWS CLI to find currently available models in your region:
> ```bash
> aws bedrock list-foundation-models --by-provider anthropic --region $AWS_REGION --output table
> ```
> Look for `anthropic.claude-3-5-sonnet-*` or `us.anthropic.claude-3-5-sonnet-*` (cross-region inference) entries.

### AWS Authentication Options

Instead of hardcoding AWS keys, you can also use:

```bash
aws configure sso --profile qualys-cs-mcp
aws sso login --profile qualys-cs-mcp
export AWS_PROFILE=qualys-cs-mcp
```

If you use SSO, update the backend code in `backend/agent.py` to use `anthropic.AnthropicBedrock()` without explicit credentials so it picks up the AWS profile.

## Running Locally

The project includes convenience scripts to start and stop all services.

### Start all services

```bash
./start.sh
```

This script will:

1. Install Python dependencies for the backend (`pip install -r backend/requirements.txt`)
2. Install Node.js dependencies for the frontend (`npm install` inside `frontend/`)
3. Start the FastAPI backend on `http://localhost:8000`
4. Start the Vite frontend dev server on `http://localhost:5173`
5. Save process IDs to `.pids` and tail logs from both services

Open your browser at:

- **Frontend**: http://localhost:5173
- **Backend Health**: http://localhost:8000/health

### Stop all services

```bash
./stop.sh
```

This stops the backend and frontend processes and frees ports 8000 and 5173.

### Manual startup (alternative)

If you prefer to run components individually:

```bash
# Terminal 1 — Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm install
npm run dev
```

## Project Structure

```
qualys-container-security-mcp/
├── .env                  # Local secrets (ignored by git)
├── .env.example          # Example environment variables
├── .env.template         # Additional template for env vars
├── .gitignore            # Git exclusions (.env, logs, node_modules, etc.)
├── README.md             # This file
├── start.sh              # One-command startup script
├── stop.sh               # One-command shutdown script
├── logs.sh               # Helper to view logs
├── backend/
│   ├── main.py           # FastAPI app with CORS and route registration
│   ├── agent.py          # Claude Bedrock agent + Qualys tool definitions
│   ├── qualys_client.py  # Shared Qualys API client utilities
│   ├── requirements.txt  # Python dependencies
│   └── routes/
│       ├── dashboard.py  # Dashboard summary endpoints
│       └── chat.py       # Chat + streaming SSE endpoint
├── frontend/
│   ├── index.html        # HTML entry point
│   ├── package.json      # Node dependencies and scripts
│   ├── vite.config.ts    # Vite configuration
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── tsconfig.json
│   └── src/
│       ├── main.tsx      # React app bootstrap
│       ├── App.tsx       # Main layout and routing
│       ├── index.css     # Tailwind imports and global styles
│       ├── components/   # Reusable UI components
│       ├── context/      # React context providers
│       ├── hooks/        # Custom React hooks
│       ├── lib/          # Utility libraries
│       └── pages/        # Chat, Dashboard, etc.
└── mcp_server/
    ├── server.py         # FastMCP server exposing Qualys CS tools
    ├── qualys_client.py  # Qualys API HTTP client
    └── requirements.txt  # MCP server dependencies
```

## API Endpoints

### Backend (FastAPI)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/dashboard/summary` | High-level security summary |
| GET | `/dashboard/critical` | Critical/high vulnerability summary |
| POST | `/chat` | Stream chat response via SSE |

The `/chat` endpoint accepts JSON with a `message` field and returns a Server-Sent Events (SSE) stream of response tokens from the LLM agent.

## MCP Tools

The `mcp_server/server.py` exposes the following tool categories to the LLM:

### Containers
- `list_containers` — list containers with filtering/sorting
- `get_container_details` — details for a specific container SHA
- `get_container_vulns` — vulnerability details for a container
- `get_container_vuln_count` — vulnerability count summary
- `get_container_software` — software inventory (SBOM)
- `get_container_compliance` — policy compliance details
- `list_containers_bulk` — bulk container listing with pagination

### Images
- `list_images` — list container images
- `get_image_details` — image details by SHA
- `get_image_vulns` — image vulnerabilities
- `get_image_vuln_count` — image vulnerability counts
- `get_image_software` — image software inventory
- `get_image_compliance` — image compliance status
- `get_image_secrets` — secrets detected in an image
- `get_image_malware` — malware detected in an image
- `find_images_with_secrets` — find all images with secrets
- `find_images_with_malware` — find all images with malware
- `find_images_by_vuln_severity` — find images by vulnerability severity
- `find_containers_by_vuln_severity` — find containers by vulnerability severity
- `get_image_association` — containers using a specific image
- `list_images_bulk` — bulk image listing with pagination

### Registries & Kubernetes
- `list_registries` — configured registries
- `get_registry_details` — registry details
- `get_registry_repositories` — repositories in a registry
- `get_registry_schedules` — registry scan schedules
- `list_sensors` — deployed sensors
- `get_sensor_details` — sensor details
- `list_k8s_clusters` — Kubernetes clusters
- `get_k8s_cluster` — cluster details
- `list_k8s_pods` — pods across clusters

## Troubleshooting

### Port already in use

```bash
lsof -ti:8000 | xargs kill -9
lsof -ti:5173 | xargs kill -9
```

Or simply run `./stop.sh`.

### Backend or frontend won't start

Check the logs:

```bash
./logs.sh
# or
tail -f backend.log frontend.log
```

### AWS Bedrock authentication errors

- Verify your AWS credentials are exported or configured via `aws configure`
- Ensure the selected IAM user/role has `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream` permissions
- Make sure the Claude model is enabled in the target AWS region

### Qualys API errors (401/403)

- Confirm your `QUALYS_USERNAME` and `QUALYS_PASSWORD` are correct
- Check that your account has Container Security API access enabled
- Verify the `QUALYS_PLATFORM_URL` matches your Qualys platform (e.g., `https://gateway.qg2.apps.qualys.com` for US2)

### Frontend can't connect to backend

The backend CORS middleware allows `http://localhost:5173` and `http://localhost:3000`. If you run the frontend on a different port, update `backend/main.py` `allow_origins` accordingly.

## Known Filter Tokens

These Qualys CS search token filter strings are used by the agent when querying the API. Reference: https://docs.qualys.com/en/cs/latest/search_tips/search_tokens.htm

| Query | Filter Token |
|---|---|
| Images active in last 24h | `imagesInUse:[now-1d ... now]` |
| Images with detected secrets | `container.image.hasSecrets:true` |
| Images with malware | `malware.imageMalwareCount:>0` |
| Software nearing EOL (3 months) | `software.lifecycle.eol:[now .. now+3M]` |
| Images with AI software | `container.image.hasAiSoftware:true` |
| Critical vulnerabilities | `vulnerability.severity:CRITICAL` |

## Contributing

If you want to extend this project:

1. Add new tools to `shared/tool_registry.py` — they are automatically picked up by both the agent and the MCP server
2. Update the system prompt in `backend/agent.py` if the new tools need workflow guidance
3. Add new frontend pages or components under `frontend/src/pages/` and `frontend/src/components/`
4. Keep `.env` out of commits — the `.gitignore` already handles this

## License

MIT
