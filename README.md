# Qualys KCS — AI Security Intelligence Platform  

**Sheldon** is an AI assistant for Qualys Kubernetes & Container Security. You type a question in plain English — Sheldon calls the right Qualys API, fetches live data from your environment, and returns an answer in seconds.

No searching through docs. No waiting on an SME. No tickets.

## Table of Contents

- [What Sheldon Can Do](#what-sheldon-can-do)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Running Locally](#running-locally)
- [Project Structure](#project-structure)
- [API Endpoints](#api-endpoints)
- [Available Tools](#available-tools)
- [QQL Filter Tokens](#qql-filter-tokens)
- [Troubleshooting](#troubleshooting)
- [Extending the Project](#extending-the-project)
- [Connecting to the MCP Server](#connecting-to-the-mcp-server)
- [License](#license)

## What Sheldon Can Do

Ask Sheldon anything about your container environment:

- **Vulnerabilities** — "Show me all critical CVEs in running containers"
- **Images** — "Which images have detected secrets or malware?"
- **Kubernetes** — "List all pods in the prod namespace"
- **Sensors** — "How do I deploy the Qualys sensor using Helm?"
- **Registries** — "What registries are configured in my account?"
- **Posture** — "Give me a summary of my current security posture"
- **SBOM** — "What software is installed in image SHA abc123?"
- **Charts** — Sheldon can render pie charts, bar charts, and tables inline

All answers come from **live Qualys API data** — nothing is pre-indexed or cached from a database.

## How It Works

1. You type a question in the chat UI
2. The question is sent to the FastAPI backend
3. The backend passes it to **Claude on Amazon Bedrock** along with a list of 40+ Qualys API tools
4. Claude reads the question, picks the right tool(s), and calls the Qualys CS API — in parallel if needed
5. The live API results are returned to Claude, which formats them into a clear answer
6. The answer streams back to your browser in real time

> **No AI guessing.** Claude is the router — it decides which API to call. The answer always comes from your actual Qualys environment.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                        User                              │
│              (Web Chat — React UI)                       │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   FastAPI Backend    │
              │  Async Python · 8000 │
              └──────────┬───────────┘
                         │
          ┌──────────────▼──────────────┐
          │      Claude 3 Haiku         │
          │    (Amazon Bedrock)         │
          │  reads question, picks tool │
          └──────────────┬──────────────┘
                         │ tool call
                         ▼
          ┌──────────────────────────────┐
          │    Shared Tool Registry      │
          │  40+ tools · single source   │
          │  of truth for agent + MCP    │
          └────────┬─────────────────────┘
                   │                    │
                   ▼                    ▼
     ┌─────────────────────┐   ┌────────────────────┐
     │   Qualys CS API     │   │    MCP Server       │
     │  Live data · always │   │  Cursor · any MCP  │
     │  from your account  │   │  compatible client  │
     └─────────────────────┘   └────────────────────┘
```

### Key Design Decisions

- **No RAG, no vector database** — Claude calls the Qualys API directly. Data is always live and current.
- **Shared Tool Registry** (`shared/tool_registry.py`) — one place where all 40+ tools are defined. Both the web chat agent and the MCP server read from it. Add a tool once, it works everywhere.
- **MCP Server** (`mcp_server/server.py`) — exposes the same Qualys tools over the Model Context Protocol so developers can use them inside Cursor or any MCP-compatible IDE.
- **Parallel API calls** — when a question needs multiple API calls, they fire simultaneously for speed.
- **Your AWS, your data** — Claude runs on your own Amazon Bedrock account. No data is sent to third-party AI services.

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

## Available Tools

All tools are defined in `shared/tool_registry.py` and are automatically available in both the web chat and the MCP server.

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

## QQL Filter Tokens

When Sheldon queries the Qualys API with filters, it uses these QQL (Qualys Query Language) tokens. You can also use them directly in questions like *"show me images where container.image.hasSecrets:true"*.

Full reference: https://docs.qualys.com/en/cs/latest/search_tips/search_tokens.htm

| Query | Filter Token |
|---|---|
| Images active in last 24h | `imagesInUse:[now-1d ... now]` |
| Images with detected secrets | `container.image.hasSecrets:true` |
| Images with malware | `malware.imageMalwareCount:>0` |
| Software nearing EOL (3 months) | `software.lifecycle.eol:[now .. now+3M]` |
| Images with AI software | `container.image.hasAiSoftware:true` |
| Critical vulnerabilities | `vulnerability.severity:CRITICAL` |

## Extending the Project

The project is designed to be easy to extend:

1. **Add a new Qualys API tool** — add it to `shared/tool_registry.py`. It is automatically available in the web chat agent AND the MCP server. No other changes needed.
2. **Add workflow guidance** — if the new tool needs special instructions (e.g. when to use it, how to combine it), update the system prompt in `backend/agent.py`.
3. **Add a new UI page** — add it under `frontend/src/pages/` and register it in `App.tsx`.
4. **Keep secrets safe** — `.env` is in `.gitignore` and will never be committed.

## Connecting to the MCP Server

The MCP server uses `stdio` transport. Any MCP-compatible client (Cursor, etc.) connects by running the server as a local process.

### Cursor

Add this to your Cursor MCP config at `~/.cursor/mcp.json`:

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

Replace `/path/to/` with the actual path to your project root. The server calls `dotenv.load_dotenv()` on startup, so it will automatically pick up credentials from the `.env` file in the project root — no need to duplicate them in the config.

### Verifying the connection

Once connected, your MCP client should list `qualys-cs` as an available server with all 40+ Qualys tools. You can then ask questions like:

- *"List my running containers"*
- *"Show me images with critical vulnerabilities"*
- *"Which images have detected secrets?"*

The MCP server calls the same Qualys CS API as the web chat — live data, same tools, no extra setup.

## License

MIT
