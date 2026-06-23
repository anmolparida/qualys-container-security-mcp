import os
import json
import httpx
from typing import AsyncGenerator
import anthropic

BEDROCK_MODEL = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")

SYSTEM_PROMPT = """You are a Qualys Container Security assistant. You help security teams understand
their container environment by answering questions about containers, images, vulnerabilities,
registries, Kubernetes clusters, sensors, and security posture.

You have access to tools that call the Qualys Container Security API. Always use these tools
to fetch real data before answering. Be concise, clear, and highlight critical security findings.
When presenting vulnerability data, always lead with critical and high severity issues.
Never make up data — only report what the API returns."""


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


# MCP tool definitions matching server.py tools
TOOLS = [
    {"name": "list_containers", "description": "List containers in the Qualys account with optional filtering and sorting.", "input_schema": {"type": "object", "properties": {"filter": {"type": "string", "default": ""}, "page_number": {"type": "integer", "default": 1}, "page_size": {"type": "integer", "default": 50}, "sort": {"type": "string", "default": "created:desc"}}}},
    {"name": "get_container_details", "description": "Get full details of a specific container by its SHA.", "input_schema": {"type": "object", "properties": {"container_sha": {"type": "string"}}, "required": ["container_sha"]}},
    {"name": "get_container_vulns", "description": "Get vulnerability details for a specific container.", "input_schema": {"type": "object", "properties": {"container_sha": {"type": "string"}, "filter": {"type": "string", "default": ""}, "vuln_type": {"type": "string", "default": "ALL", "enum": ["ALL", "DETAILS", "SUMMARY"]}}, "required": ["container_sha"]}},
    {"name": "get_container_vuln_count", "description": "Get vulnerability count summary for a specific container.", "input_schema": {"type": "object", "properties": {"container_sha": {"type": "string"}}, "required": ["container_sha"]}},
    {"name": "get_container_software", "description": "List software installed on a specific container.", "input_schema": {"type": "object", "properties": {"container_sha": {"type": "string"}, "filter": {"type": "string", "default": ""}}, "required": ["container_sha"]}},
    {"name": "get_container_compliance", "description": "Get policy compliance details for a specific container.", "input_schema": {"type": "object", "properties": {"container_sha": {"type": "string"}}, "required": ["container_sha"]}},
    {"name": "list_containers_bulk", "description": "Bulk list containers with pagination support.", "input_schema": {"type": "object", "properties": {"filter": {"type": "string", "default": ""}, "limit": {"type": "integer", "default": 50}, "pagination_query": {"type": "string", "default": ""}}}},
    {"name": "list_images", "description": "List container images in the Qualys account with optional filtering.", "input_schema": {"type": "object", "properties": {"filter": {"type": "string", "default": ""}, "page_number": {"type": "integer", "default": 1}, "page_size": {"type": "integer", "default": 50}, "sort": {"type": "string", "default": "created:desc"}}}},
    {"name": "get_image_details", "description": "Get full details of a specific image by its SHA.", "input_schema": {"type": "object", "properties": {"image_sha": {"type": "string"}}, "required": ["image_sha"]}},
    {"name": "get_image_vulns", "description": "Get vulnerability details for a specific image.", "input_schema": {"type": "object", "properties": {"image_sha": {"type": "string"}, "filter": {"type": "string", "default": ""}, "vuln_type": {"type": "string", "default": "ALL"}}, "required": ["image_sha"]}},
    {"name": "get_image_vuln_count", "description": "Get vulnerability count summary for a specific image.", "input_schema": {"type": "object", "properties": {"image_sha": {"type": "string"}}, "required": ["image_sha"]}},
    {"name": "get_image_software", "description": "List software installed in a specific image.", "input_schema": {"type": "object", "properties": {"image_sha": {"type": "string"}, "filter": {"type": "string", "default": ""}}, "required": ["image_sha"]}},
    {"name": "get_image_compliance", "description": "Get policy compliance details for a specific image.", "input_schema": {"type": "object", "properties": {"image_sha": {"type": "string"}}, "required": ["image_sha"]}},
    {"name": "get_image_secrets", "description": "Get detected secrets in a specific image.", "input_schema": {"type": "object", "properties": {"image_sha": {"type": "string"}}, "required": ["image_sha"]}},
    {"name": "get_image_malware", "description": "Get detected malware across image layers.", "input_schema": {"type": "object", "properties": {"image_sha": {"type": "string"}}, "required": ["image_sha"]}},
    {"name": "get_image_association", "description": "Get container associations for a specific image.", "input_schema": {"type": "object", "properties": {"image_sha": {"type": "string"}}, "required": ["image_sha"]}},
    {"name": "list_images_bulk", "description": "Bulk list images with pagination support.", "input_schema": {"type": "object", "properties": {"filter": {"type": "string", "default": ""}, "limit": {"type": "integer", "default": 50}, "pagination_query": {"type": "string", "default": ""}}}},
    {"name": "list_registries", "description": "List all container registries configured in Qualys.", "input_schema": {"type": "object", "properties": {"filter": {"type": "string", "default": ""}, "page_number": {"type": "integer", "default": 1}, "page_size": {"type": "integer", "default": 50}}}},
    {"name": "get_registry_details", "description": "Get details of a specific registry.", "input_schema": {"type": "object", "properties": {"registry_id": {"type": "string"}}, "required": ["registry_id"]}},
    {"name": "get_registry_repositories", "description": "List repositories in a specific registry.", "input_schema": {"type": "object", "properties": {"registry_id": {"type": "string"}, "page_number": {"type": "integer", "default": 1}, "page_size": {"type": "integer", "default": 50}}, "required": ["registry_id"]}},
    {"name": "get_registry_schedules", "description": "Get scan schedules for a specific registry.", "input_schema": {"type": "object", "properties": {"registry_id": {"type": "string"}}, "required": ["registry_id"]}},
    {"name": "list_sensors", "description": "List all sensors deployed in the environment.", "input_schema": {"type": "object", "properties": {"filter": {"type": "string", "default": ""}, "page_number": {"type": "integer", "default": 1}, "page_size": {"type": "integer", "default": 50}}}},
    {"name": "get_sensor_details", "description": "Get details of a specific sensor.", "input_schema": {"type": "object", "properties": {"sensor_id": {"type": "string"}}, "required": ["sensor_id"]}},
    {"name": "list_k8s_clusters", "description": "List all Kubernetes clusters monitored by Qualys.", "input_schema": {"type": "object", "properties": {"filter": {"type": "string", "default": ""}, "page_number": {"type": "integer", "default": 1}, "page_size": {"type": "integer", "default": 50}}}},
    {"name": "get_k8s_cluster", "description": "Get details of a specific Kubernetes cluster.", "input_schema": {"type": "object", "properties": {"cluster_uid": {"type": "string"}}, "required": ["cluster_uid"]}},
    {"name": "list_k8s_pods", "description": "List Kubernetes pods across clusters.", "input_schema": {"type": "object", "properties": {"filter": {"type": "string", "default": ""}, "page_number": {"type": "integer", "default": 1}, "page_size": {"type": "integer", "default": 50}}}},
    {"name": "list_k8s_namespaces", "description": "List Kubernetes namespaces across clusters.", "input_schema": {"type": "object", "properties": {"filter": {"type": "string", "default": ""}, "page_number": {"type": "integer", "default": 1}, "page_size": {"type": "integer", "default": 50}}}},
    {"name": "get_k8s_postures", "description": "Get Kubernetes security posture assessment results.", "input_schema": {"type": "object", "properties": {"filter": {"type": "string", "default": ""}, "page_number": {"type": "integer", "default": 1}, "page_size": {"type": "integer", "default": 50}}}},
    {"name": "get_k8s_posture_count", "description": "Get Kubernetes posture control count summary.", "input_schema": {"type": "object", "properties": {"filter": {"type": "string", "default": ""}}}},
    {"name": "list_vulnerabilities", "description": "List vulnerabilities detected across the environment.", "input_schema": {"type": "object", "properties": {"filter": {"type": "string", "default": ""}, "page_number": {"type": "integer", "default": 1}, "page_size": {"type": "integer", "default": 50}}}},
    {"name": "get_vulnerability_details", "description": "Get details of a specific vulnerability by UUID.", "input_schema": {"type": "object", "properties": {"vuln_uuid": {"type": "string"}}, "required": ["vuln_uuid"]}},
    {"name": "list_controls", "description": "List security controls available in Qualys CS.", "input_schema": {"type": "object", "properties": {"filter": {"type": "string", "default": ""}, "page_number": {"type": "integer", "default": 1}, "page_size": {"type": "integer", "default": 50}}}},
    {"name": "list_exceptions", "description": "List vulnerability exceptions configured in Qualys CS.", "input_schema": {"type": "object", "properties": {"filter": {"type": "string", "default": ""}, "page_number": {"type": "integer", "default": 1}, "page_size": {"type": "integer", "default": 50}}}},
    {"name": "list_secret_detectors", "description": "List secret detection rules configured in Qualys CS.", "input_schema": {"type": "object", "properties": {"filter": {"type": "string", "default": ""}, "page_number": {"type": "integer", "default": 1}, "page_size": {"type": "integer", "default": 50}}}},
]


def _call_qualys_tool(name: str, inputs: dict) -> str:
    """Execute a Qualys API call matching the tool name."""
    from qualys_client import get

    routes = {
        "list_containers": lambda i: get("/containers", {"filter": i.get("filter", ""), "pageNumber": i.get("page_number", 1), "pageSize": i.get("page_size", 50), "sort": i.get("sort", "created:desc")}),
        "get_container_details": lambda i: get(f"/containers/{i['container_sha']}"),
        "get_container_vulns": lambda i: get(f"/containers/{i['container_sha']}/vuln", {"filter": i.get("filter", ""), "type": i.get("vuln_type", "ALL")}),
        "get_container_vuln_count": lambda i: get(f"/containers/{i['container_sha']}/vuln/count"),
        "get_container_software": lambda i: get(f"/containers/{i['container_sha']}/software", {"filter": i.get("filter", "")}),
        "get_container_compliance": lambda i: get(f"/containers/{i['container_sha']}/compliance"),
        "list_containers_bulk": lambda i: get("/containers/list", {"filter": i.get("filter", ""), "limit": i.get("limit", 50)}),
        "list_images": lambda i: get("/images", {"filter": i.get("filter", ""), "pageNumber": i.get("page_number", 1), "pageSize": i.get("page_size", 50), "sort": i.get("sort", "created:desc")}),
        "get_image_details": lambda i: get(f"/images/{i['image_sha']}"),
        "get_image_vulns": lambda i: get(f"/images/{i['image_sha']}/vuln", {"filter": i.get("filter", ""), "type": i.get("vuln_type", "ALL")}),
        "get_image_vuln_count": lambda i: get(f"/images/{i['image_sha']}/vuln/count"),
        "get_image_software": lambda i: get(f"/images/{i['image_sha']}/software", {"filter": i.get("filter", "")}),
        "get_image_compliance": lambda i: get(f"/images/{i['image_sha']}/compliance"),
        "get_image_secrets": lambda i: get(f"/images/{i['image_sha']}/secrets"),
        "get_image_malware": lambda i: get(f"/images/{i['image_sha']}/layers/malware"),
        "get_image_association": lambda i: get(f"/images/{i['image_sha']}/association"),
        "list_images_bulk": lambda i: get("/images/list", {"filter": i.get("filter", ""), "limit": i.get("limit", 50)}),
        "list_registries": lambda i: get("/registry", {"filter": i.get("filter", ""), "pageNumber": i.get("page_number", 1), "pageSize": i.get("page_size", 50)}),
        "get_registry_details": lambda i: get(f"/registry/{i['registry_id']}"),
        "get_registry_repositories": lambda i: get(f"/registry/{i['registry_id']}/repository", {"pageNumber": i.get("page_number", 1), "pageSize": i.get("page_size", 50)}),
        "get_registry_schedules": lambda i: get(f"/registry/{i['registry_id']}/schedule"),
        "list_sensors": lambda i: get("/sensors", {"filter": i.get("filter", ""), "pageNumber": i.get("page_number", 1), "pageSize": i.get("page_size", 50)}),
        "get_sensor_details": lambda i: get(f"/sensors/{i['sensor_id']}"),
        "list_k8s_clusters": lambda i: get("/k8sClusters", {"filter": i.get("filter", ""), "pageNumber": i.get("page_number", 1), "pageSize": i.get("page_size", 50)}),
        "get_k8s_cluster": lambda i: get(f"/k8sClusters/{i['cluster_uid']}"),
        "list_k8s_pods": lambda i: get("/k8sResource/pod", {"filter": i.get("filter", ""), "pageNumber": i.get("page_number", 1), "pageSize": i.get("page_size", 50)}),
        "list_k8s_namespaces": lambda i: get("/k8sResource/namespace", {"filter": i.get("filter", ""), "pageNumber": i.get("page_number", 1), "pageSize": i.get("page_size", 50)}),
        "get_k8s_postures": lambda i: get("/k8s_postures/list", {"filter": i.get("filter", ""), "pageNumber": i.get("page_number", 1), "pageSize": i.get("page_size", 50)}),
        "get_k8s_posture_count": lambda i: get("/k8s_postures/count", {"filter": i.get("filter", "")}),
        "list_vulnerabilities": lambda i: get("/vulnerability", {"filter": i.get("filter", ""), "pageNumber": i.get("page_number", 1), "pageSize": i.get("page_size", 50)}),
        "get_vulnerability_details": lambda i: get(f"/vulnerability/{i['vuln_uuid']}"),
        "list_controls": lambda i: get("/controls", {"filter": i.get("filter", ""), "pageNumber": i.get("page_number", 1), "pageSize": i.get("page_size", 50)}),
        "list_exceptions": lambda i: get("/exception", {"filter": i.get("filter", ""), "pageNumber": i.get("page_number", 1), "pageSize": i.get("page_size", 50)}),
        "list_secret_detectors": lambda i: get("/secretDetector", {"filter": i.get("filter", ""), "pageNumber": i.get("page_number", 1), "pageSize": i.get("page_size", 50)}),
    }

    fn = routes.get(name)
    if not fn:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        result = fn(inputs)
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def run_agent(user_message: str, history: list) -> AsyncGenerator[str, None]:
    client = get_client()
    messages = history + [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model=BEDROCK_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # stream text blocks
        for block in response.content:
            if hasattr(block, "text"):
                yield block.text

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = _call_qualys_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            break
