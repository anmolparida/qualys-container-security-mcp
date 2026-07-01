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
- Documentation: Qualys CS (https://docs.qualys.com/en/cs/latest/get_started/cs_docs.htm), CS API (https://docs.qualys.com/en/cs/api/), CS User Guide (https://docs.qualys.com/en/cs/)

NON-API QUESTIONS:
For questions about installation, configuration, deployment, or anything not answered by the API tools, use the fetch_docs tool to retrieve content from the relevant Qualys documentation page before answering. Always cite the source URL in your response.
If the question is about other Qualys products outside Container Security (e.g. VMDR, WAS, EDR, CSAM, Policy Compliance, etc.), use fetch_docs with https://www.qualys.com/ to find the relevant product information and direct the user there."""


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
            item = {
                **item,
                "content": _truncate_text(item.get("content", ""), MAX_TOOL_RESULT_CHARS),
            }
        # Anthropic content block (TextBlock, ToolUseBlock)
        elif hasattr(item, "type") and getattr(item, "type") == "text" and hasattr(item, "text"):
            text = getattr(item, "text", "")
            if len(text) > MAX_MESSAGE_CHARS:
                item.text = text[:MAX_MESSAGE_CHARS] + "\n... [truncated]"
        trimmed.append(item)
    return trimmed


def _truncate_messages(messages: list) -> list:
    """Keep the conversation within the model's context window.

    - Always preserve the most recent user message.
    - Keep the last MAX_HISTORY_MESSAGES turns.
    - Truncate oversized assistant/user text and tool result JSON.
    - Ensure the first message always has role 'user' (Anthropic requirement).
    """
    trimmed = [{**msg, "content": _truncate_content(msg.get("content"))} for msg in messages]
    # Drop messages with empty content (except an optional final assistant message)
    trimmed = [m for m in trimmed if m.get("content")]
    trimmed = trimmed[-MAX_HISTORY_MESSAGES:]
    # Drop leading non-user messages
    while trimmed and trimmed[0].get("role") != "user":
        trimmed = trimmed[1:]
    return trimmed


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

        for block in response.content:
            if hasattr(block, "text"):
                yield block.text

        if response.stop_reason == "end_turn":
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

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            break
