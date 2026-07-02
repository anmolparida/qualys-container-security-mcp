import os
import sys
import json
import logging
import asyncio
import httpx
from typing import AsyncGenerator, Any
import anthropic

# Make the shared tool registry importable from both backend and mcp_server.
# The shared package lives at the project root, one level above this file.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.tool_registry import build_anthropic_tools, build_route

logger = logging.getLogger("agent")

BEDROCK_MODEL = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

SYSTEM_PROMPT = """You are a Qualys Container Security assistant. You help security teams understand
their container environment by answering questions about containers, images, vulnerabilities,
registries, Kubernetes clusters, sensors, and security posture.

You have access to tools that call the Qualys Container Security API. Always use these tools
to fetch real data before answering. Be concise, clear, and highlight critical security findings.
When presenting vulnerability data, always lead with critical and high severity issues.
Never make up data — only report what the API returns.

SENSOR INSTALLATION KNOWLEDGE:
The official unified Helm chart for all Qualys Container Security sensors is published at:
https://artifacthub.io/packages/helm/qualys-helm-chart/qualys-tc

Add the Helm repo:
```bash
helm repo add qualys https://qualys.github.io/qualys-helm-chart
helm repo update
```

Install the QCS sensor (container/image scanning) on a standard Kubernetes cluster:
```bash
helm install qualys-cs qualys/qualys-tc \
  --namespace qualys --create-namespace \
  --set activationId=<ACTIVATION_ID> \
  --set customerId=<CUSTOMER_ID> \
  --set logLevel=3 \
  --set sensor.image.tag=latest
```

Install on OpenShift (adds SCC and privileged context):
```bash
helm install qualys-cs qualys/qualys-tc \
  --namespace qualys --create-namespace \
  --set activationId=<ACTIVATION_ID> \
  --set customerId=<CUSTOMER_ID> \
  --set isOpenShift=true \
  --set logLevel=3 \
  --set sensor.image.tag=latest
```

Install the Kubernetes cluster sensor (posture/compliance) separately:
```bash
helm install qualys-kcs qualys/qualys-tc \
  --namespace qualys --create-namespace \
  --set activationId=<ACTIVATION_ID> \
  --set customerId=<CUSTOMER_ID> \
  --set deployClusterSensor=true \
  --set logLevel=3
```

On OpenShift, add `--set isOpenShift=true` to any of the above commands.
Replace <ACTIVATION_ID> and <CUSTOMER_ID> with values from the Qualys portal under Help > About.
Full chart reference: https://artifacthub.io/packages/helm/qualys-helm-chart/qualys-tc

KNOWN FILTER TOKENS (use these exactly when building filter params):
- Images active in last 24h:     imagesInUse:[now-1d ... now]
- Images with detected secrets:   container.image.hasSecrets:true
- Images with malware:            malware.imageMalwareCount:>0
- Software nearing EOL (3 months): software.lifecycle.eol:[now .. now+3M]
- Images with AI software:        container.image.hasAiSoftware:true
- Reference for all tokens: https://docs.qualys.com/en/cs/latest/search_tips/search_tokens.htm
- If a filter fails, fetch the above URL to find the correct token syntax and retry.

AWS FARGATE / ECS SCANNING:
- For ANY question about AWS Fargate, ECS, serverless containers, or scanning containers in Fargate — you MUST call fetch_docs FIRST with this URL before generating any response:
  https://docs.qualys.com/en/cs/latest/mergedProjects/cs_sensor_deployment_help/scan_container_images_in_aws_fargate_ecs/scan_container_images_in_aws_fargate_(ecs).htm
- NEVER answer Fargate questions from memory alone — always fetch this doc first, then base your answer strictly on its content.
- Key architecture: Since Fargate is serverless, Qualys deploys a Lambda-based sensor via AWS CloudFormation. When a Fargate ECS task launches, an EventBridge rule triggers the Qualys Lambda function, which then launches AWS CodeBuild to run the Qualys sensor against the container image in Amazon ECR.
- Scanning flow: ECS Fargate task launches → EventBridge captures event → Qualys Lambda triggered → CodeBuild runs Qualys sensor → pulls image from ECR → vulnerability + compliance scan → results uploaded to Qualys Enterprise TruRisk™ Platform.
- Supported architectures: x86_64 and ARM64 Docker images from Amazon ECR.
- Pre-requisite: A CloudFormation stack must be configured with the Qualys subscription details and a Lambda function pointing to the Qualys S3 bucket.
- Stack deployment guide: https://docs.qualys.com/en/cs/latest/mergedProjects/cs_sensor_deployment_help/scan_container_images_in_aws_fargate_ecs/How_to_deploy_the_stack_using_AWS_Console.htm
- For Qualys Private Cloud Platform (PCP) + Fargate: https://www.qualys.com/docs/qualys-container-security-secure-fargate-on-pcp.pdf
- Benefits to highlight: automated vuln scanning, continuous monitoring, faster risk detection, seamless AWS integration (EventBridge + Lambda + CodeBuild + ECR), improved cloud workload protection.
- Wrap all AWS CLI, CloudFormation, and ECS commands in fenced ```bash code blocks.

CI/CD PIPELINE INTEGRATION:
- For ANY question about CI/CD, pipeline scanning, build-time scanning, shift-left security, DevSecOps, Jenkins, GitHub Actions, GitLab CI, Azure DevOps, or integrating container scanning into pipelines — ALWAYS recommend and reference QScanner.
- QScanner is the official Qualys CLI tool for shift-left container security scanning.
- QScanner docs: https://docs.qualys.com/en/qscanner/latest/
- QScanner commands reference: https://docs.qualys.com/en/qscanner/latest/qscanner_usage/qscanner_commands.htm
- Use fetch_docs with the above URLs to get the latest QScanner commands and integration steps before answering.
- Always wrap QScanner commands in fenced ```bash code blocks.

SECRETS & MALWARE WORKFLOWS:
- To find images with detected secrets: call `find_images_with_secrets` — this uses filter 'detection.type:secret'. Then for each image SHA returned, call `get_image_secrets` to get actual secret details.
- To find images with malware: call `find_images_with_malware` — uses filter 'detection.type:malware'. Then call `get_image_malware` per SHA for details.
- To list secret detection rules: call `list_secret_detectors`.
- NEVER try to filter `/images` manually for secrets — always use the dedicated `find_images_with_secrets` tool.
- If a filter query fails, fetch https://docs.qualys.com/en/cs/latest/search_tips/search_tokens.htm to find the correct token syntax, then retry with the correct filter value.
- Qualys CS search token reference: https://docs.qualys.com/en/cs/latest/search_tips/search_tokens.htm — consult this whenever building filter strings for any API tool call.

FORMATTING RULES:
- Always use markdown tables for lists of items (containers, images, vulnerabilities, registries, clusters, etc.)
- Use bold (**text**) for severity labels and important values
- Use bullet points only for short summaries, not for lists of data
- For vulnerability tables include columns: Name/ID, Severity, CVE, Affected Component
- For container tables include columns: Name, State, Image, Critical, High vulns
- For image tables include columns: Image, Tag, Critical, High, Medium vulns
- Keep table rows concise — truncate long strings with ...
- After a table, add a 1–2 line summary of the key finding
- Always wrap shell commands, CLI output, kubectl/helm commands, and code snippets in fenced code blocks with the appropriate language tag (e.g. ```bash, ```yaml, ```json). Never print commands as plain text lines.
- When the user asks for charts, graphs, or visualizations, output a chart data block inside a fenced code block marked ```chart. The block must contain valid JSON with: type ("pie", "bar", or "line"), title (string), data (array of objects with "name" and "value"), and optional colors (array of hex strings). Example:
  ```chart
  {"type": "pie", "title": "Vulnerability Severity", "data": [{"name": "Critical", "value": 5}, {"name": "High", "value": 12}]}
  ```
- Always include a link to https://artifacthub.io/packages/helm/qualys-helm-chart/qualys-tc when answering sensor installation questions.
- Documentation: Qualys CS (https://docs.qualys.com/en/cs/latest/get_started/cs_docs.htm), CS API (https://docs.qualys.com/en/cs/api/), CS User Guide (https://docs.qualys.com/en/cs/), Release Notes (https://www.qualys.com/documentation/release-notes)

VULNERABILITY REPORTS:
- For ANY request to generate, show, list, or fetch a vulnerability report — ALWAYS call `list_reports` first to show existing generated reports, then call `get_scheduled_reports` to show scheduled reports.
- For per-container vulnerability details: call `get_container_vulns` with the container SHA, or `get_container_vuln_count` for a summary.
- For per-image vulnerability details: call `get_image_vulns` with the image SHA, or `get_image_vuln_count` for a summary.
- For environment-wide vulnerability listing: call `list_vulnerabilities` (optionally with a filter like `severity:CRITICAL`).
- For running containers specifically: call `list_containers` with filter `state:RUNNING`, then call `get_container_vuln_count` for each container SHA returned.
- Always present report results as a markdown table. Include columns: Report Name, Type, Status, Created, and a link if available.
- Never fabricate report data — only show what the API returns.

API REFERENCE QUESTIONS:
- When a user asks "what is the API to...", "show me the API for...", "how do I call...", or "what endpoint..." — respond with the full API details: HTTP method, URL path, required headers, and example JSON payload. Do NOT call the API — just show the reference.
- Base URL format: `https://<qualys-gateway>/csapi/v1.3<path>`
- All requests require: `Authorization: Bearer <JWT>` header. Obtain JWT via `POST /auth`.
- Key write APIs (POST/PUT/DELETE — for reference only, never execute):
  - **Create Registry**: `POST /csapi/v1.3/registry` — body: `{"registryType":"V2_PRIVATE","registryUri":"<url>","registryName":"<name>","credentialType":"BasicAuth","credential":{"username":"<u>","password":"<p>"}}`
  - **Validate Registry**: `POST /csapi/v1.3/registry/validate` — same body as create
  - **Update Registry**: `PUT /csapi/v1.3/registry/{registryId}` — same body as create
  - **Delete Registries**: `DELETE /csapi/v1.3/registry` — body: `{"registryIds":["<id>"]}`
  - **Create AWS Connector**: `POST /csapi/v1.3/registry/aws/connector` — body: `{"name":"<name>","arn":"<arn>","accountType":"Global"}`
  - **Create ACR Connector**: `POST /csapi/v1.3/registry/acr/connector` — body: `{"name":"<name>","applicationId":"<id>","clientSecret":"<secret>"}`
  - **Create GCP Connector**: `POST /csapi/v1.3/registry/gcp/connector` — body: `{"name":"<name>","gcpProjectId":"<id>","serviceAccountKey":"<key>"}`
- Always wrap example payloads in ```json code blocks.
- Always note which fields are required vs optional.
- Reference the CS API docs at https://docs.qualys.com/en/cs/api/ for full schema details.

NON-API QUESTIONS:
For questions about installation, configuration, deployment, or anything not answered by the API tools, use the fetch_docs tool to retrieve content from the relevant Qualys documentation page before answering. Always cite the source URL in your response.
When answering questions about release notes or new features, always fetch https://www.qualys.com/documentation/release-notes and reference only the Container Security section — do not mention other Qualys products.
If the question is clearly outside Container Security scope entirely, politely redirect the user to https://www.qualys.com/ for other products."""


def _make_client() -> anthropic.AnthropicBedrock:
    return anthropic.AnthropicBedrock(
        aws_access_key=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        aws_region=os.environ.get("AWS_REGION", "us-east-1"),
    )

# Single shared client — recreating it per query is wasteful (opens new HTTP session each time)
_client: anthropic.AnthropicBedrock | None = None

def get_client() -> anthropic.AnthropicBedrock:
    global _client
    if _client is None:
        _client = _make_client()
    return _client


# Anthropic tool definitions are now generated from the shared registry.
# The MCP server imports the same registry, so both surfaces stay in sync.
_DOCS_TOOL = {
    "name": "fetch_docs",
    "description": (
        "Fetch the text content of a Qualys documentation page or the Helm chart reference. "
        "Use this whenever the user asks about installation steps, configuration, sensor deployment, "
        "or any topic not covered by the Qualys API tools. "
        "Allowed URLs: docs.qualys.com/*, artifacthub.io/packages/helm/qualys-helm-chart/*, "
        "qualys.github.io/*, github.com/qualys/*, qualys.com/*"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The full URL to fetch (must be a Qualys docs or Helm chart page)"
            }
        },
        "required": ["url"]
    }
}

TOOLS = build_anthropic_tools() + [_DOCS_TOOL]


ALLOWED_DOC_HOSTS = (
    "docs.qualys.com",
    "artifacthub.io",
    "qualys.github.io",
    "github.com",
    "qualys.com",
)


async def _fetch_docs(url: str) -> str:
    """Fetch plain text from an allowed Qualys docs/Helm page."""
    from urllib.parse import urlparse
    host = urlparse(url).netloc.lstrip("www.")
    if not any(host.endswith(h) for h in ALLOWED_DOC_HOSTS):
        return json.dumps({"error": f"URL not allowed: {url}"})
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "QualysCS-Assistant/1.0"})
            resp.raise_for_status()
            # Strip HTML tags naively — good enough for docs pages
            import re
            text = re.sub(r"<[^>]+>", " ", resp.text)
            text = re.sub(r"[ \t]{2,}", " ", text)
            text = re.sub(r"\n{3,}", "\n\n", text)
            return text[:8000]  # cap to avoid context overflow
    except Exception as e:
        return json.dumps({"error": str(e)})


async def _call_qualys_tool(name: str, inputs: dict) -> str:
    """Execute a Qualys API call for a tool using the shared route builder."""
    from qualys_client import get_async

    if name == "fetch_docs":
        return await _fetch_docs(inputs.get("url", ""))

    try:
        path, params = build_route(name, inputs)
        # Translate shared snake-case keys to Qualys API camelCase keys.
        param_map = {
            "page_number": "pageNumber",
            "page_size": "pageSize",
            "pagination_query": "paginationQuery",
        }
        params = {param_map.get(k, k): v for k, v in params.items()}
        result = await get_async(path, params)
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


MAX_HISTORY_MESSAGES = 6
MAX_MESSAGE_CHARS = 12000
MAX_TOOL_RESULT_CHARS = 4000


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... [truncated]"


def _truncate_content(content: Any) -> Any:
    """Truncate message content whether it's a string, list of dicts, or Anthropic content blocks."""
    if isinstance(content, str):
        return _truncate_text(content, MAX_MESSAGE_CHARS)

    if not isinstance(content, list):
        return content

    trimmed = []
    for item in content:
        # Tool result list from user messages
        if isinstance(item, dict) and item.get("type") == "tool_result":
            raw = item.get("content", "")
            if isinstance(raw, str):
                raw = _truncate_text(raw, MAX_TOOL_RESULT_CHARS)
            elif isinstance(raw, list):
                raw = str(raw)[:MAX_TOOL_RESULT_CHARS]
            item = {**item, "content": raw}
        # Anthropic content block (TextBlock, ToolUseBlock)
        elif hasattr(item, "type") and getattr(item, "type") == "text" and hasattr(item, "text"):
            text = getattr(item, "text", "")
            if len(text) > MAX_MESSAGE_CHARS:
                item.text = text[:MAX_MESSAGE_CHARS] + "\n... [truncated]"
        trimmed.append(item)
    return trimmed


def _has_block_type(content: Any, block_type: str) -> bool:
    """Return True if content (str or list) contains a block of the given type."""
    if not isinstance(content, list):
        return False
    return any(
        (isinstance(b, dict) and b.get("type") == block_type)
        or (hasattr(b, "type") and getattr(b, "type") == block_type)
        for b in content
    )


def _truncate_messages(messages: list) -> list:
    """Keep the conversation within the model's context window.

    Guarantees:
    - First message is always role='user' (never a tool_result).
    - tool_use/tool_result pairs are never split by the history window.
    - Never returns an empty list.
    """
    # Step 1: truncate content length in each message
    msgs = [{**msg, "content": _truncate_content(msg.get("content"))} for msg in messages]
    # Drop messages with empty/None content
    msgs = [m for m in msgs if m.get("content")]

    # Step 2: trim to MAX_HISTORY_MESSAGES but always keep pairs together.
    # Walk from the tail and collect up to MAX_HISTORY_MESSAGES messages,
    # but if we'd cut between a tool_use and its tool_result, drop both.
    if len(msgs) > MAX_HISTORY_MESSAGES:
        tail = msgs[-MAX_HISTORY_MESSAGES:]
        # If the first message in tail is a tool_result, drop it (its tool_use was cut off)
        while tail and (
            tail[0].get("role") != "user"
            or _has_block_type(tail[0].get("content"), "tool_result")
        ):
            tail = tail[1:]
        msgs = tail

    # Step 3: ensure first message is a plain user message (not tool_result)
    while msgs and (
        msgs[0].get("role") != "user"
        or _has_block_type(msgs[0].get("content"), "tool_result")
    ):
        msgs = msgs[1:]

    # Step 4: scan and drop any remaining orphaned tool_result messages
    cleaned = []
    for msg in msgs:
        if msg.get("role") == "user" and _has_block_type(msg.get("content"), "tool_result"):
            prev = cleaned[-1] if cleaned else None
            if not (prev and _has_block_type(prev.get("content"), "tool_use")):
                continue  # orphaned — drop it
        cleaned.append(msg)

    # Step 5: fallback — if empty, return just the last plain user message
    if not cleaned:
        for msg in reversed(msgs or messages):
            if msg.get("role") == "user" and not _has_block_type(msg.get("content"), "tool_result"):
                return [msg]
        return []

    return cleaned


async def run_agent(user_message: str, history: list) -> AsyncGenerator[str, None]:
    client = get_client()
    messages = _truncate_messages(history + [{"role": "user", "content": user_message}])
    turn = 0

    logger.info(f"AGENT  user: {user_message[:120]}")

    while True:
        turn += 1
        messages = _truncate_messages(messages)
        logger.info(f"AGENT  turn {turn}  → calling Bedrock ({BEDROCK_MODEL})  messages={len(messages)}")
        response = client.messages.create(
            model=BEDROCK_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        logger.info(f"AGENT  turn {turn}  ← stop_reason={response.stop_reason}  tokens={response.usage.input_tokens}in/{response.usage.output_tokens}out")

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    yield block.text
            logger.info("AGENT  done")
            break

        if response.stop_reason == "tool_use":
            tool_blocks = [block for block in response.content if block.type == "tool_use"]
            logger.info(f"AGENT  executing {len(tool_blocks)} tool call(s) in parallel")

            async def _run_tool(block):
                logger.info(f"AGENT  tool_call: {block.name}  inputs={json.dumps(block.input)}")
                result = await _call_qualys_tool(block.name, block.input)
                return {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                }

            tool_results = await asyncio.gather(*[_run_tool(block) for block in tool_blocks])

            def _serialize_block(b):
                if isinstance(b, dict):
                    return b
                t = getattr(b, "type", "")
                if t == "tool_use":
                    return {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
                if t == "text":
                    return {"type": "text", "text": getattr(b, "text", "")}
                return {"type": t}

            assistant_content = [_serialize_block(b) for b in response.content]
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": list(tool_results)})
        else:
            break
