"""Shared Qualys Container Security tool registry.

This module is the single source of truth for tool definitions used by both the
MCP server and the backend agent. It contains:
  - Tool metadata (name, description, parameters)
  - A route builder that maps tool names to Qualys API paths and parameters

Both the FastMCP server and the Anthropic Bedrock agent import from here so the
tool surface stays consistent and changes only need to be made in one place.
"""

from typing import Callable, Any

ToolDef = dict[str, Any]
RouteBuilder = Callable[[dict[str, Any]], tuple[str, dict[str, Any]]]


def _path(path: str, fixed_params: dict[str, Any] | None = None, transform: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None) -> RouteBuilder:
    def build(inputs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        params = {k: v for k, v in inputs.items() if v not in (None, "")}
        if fixed_params:
            params.update(fixed_params)
        if transform:
            params = transform(inputs, params)
        return path, params
    return build


def _path_with_sha(path_template: str) -> RouteBuilder:
    def build(inputs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        path = path_template.format(**inputs)
        params = {k: v for k, v in inputs.items() if k not in path_template and v not in (None, "")}
        return path, params
    return build


TOOLS: list[ToolDef] = [
    # Containers
    {
        "name": "list_containers",
        "description": "List containers in the Qualys account with optional filtering and sorting.",
        "parameters": {
            "filter": {"type": "string", "default": ""},
            "page_number": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 50},
            "sort": {"type": "string", "default": "created:desc"},
        },
        "route": _path("/containers"),
    },
    {
        "name": "get_container_details",
        "description": "Get full details of a specific container by its SHA.",
        "parameters": {"container_sha": {"type": "string"}},
        "route": _path_with_sha("/containers/{container_sha}"),
    },
    {
        "name": "get_container_vulns",
        "description": "Get vulnerability details for a specific container.",
        "parameters": {
            "container_sha": {"type": "string"},
            "filter": {"type": "string", "default": ""},
            "vuln_type": {"type": "string", "default": "ALL", "enum": ["ALL", "DETAILS", "SUMMARY"]},
        },
        "route": _path_with_sha("/containers/{container_sha}/vuln"),
    },
    {
        "name": "get_container_vuln_count",
        "description": "Get vulnerability count summary for a specific container.",
        "parameters": {"container_sha": {"type": "string"}},
        "route": _path_with_sha("/containers/{container_sha}/vuln/count"),
    },
    {
        "name": "get_container_software",
        "description": "List software installed on a specific container.",
        "parameters": {
            "container_sha": {"type": "string"},
            "filter": {"type": "string", "default": ""},
        },
        "route": _path_with_sha("/containers/{container_sha}/software"),
    },
    {
        "name": "get_container_compliance",
        "description": "Get policy compliance details for a specific container.",
        "parameters": {"container_sha": {"type": "string"}},
        "route": _path_with_sha("/containers/{container_sha}/compliance"),
    },
    {
        "name": "list_containers_bulk",
        "description": "Bulk list containers with pagination support.",
        "parameters": {
            "filter": {"type": "string", "default": ""},
            "limit": {"type": "integer", "default": 50},
        },
        "route": _path("/containers/list"),
    },

    # Images
    {
        "name": "list_images",
        "description": "List container images in the Qualys account with optional filtering.",
        "parameters": {
            "filter": {"type": "string", "default": ""},
            "page_number": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 50},
            "sort": {"type": "string", "default": "created:desc"},
        },
        "route": _path("/images"),
    },
    {
        "name": "get_image_details",
        "description": "Get full details of a specific image by its SHA.",
        "parameters": {"image_sha": {"type": "string"}},
        "route": _path_with_sha("/images/{image_sha}"),
    },
    {
        "name": "get_image_vulns",
        "description": "Get vulnerability details for a specific image.",
        "parameters": {
            "image_sha": {"type": "string"},
            "filter": {"type": "string", "default": ""},
            "vuln_type": {"type": "string", "default": "ALL"},
        },
        "route": _path_with_sha("/images/{image_sha}/vuln"),
    },
    {
        "name": "get_image_vuln_count",
        "description": "Get vulnerability count summary for a specific image.",
        "parameters": {"image_sha": {"type": "string"}},
        "route": _path_with_sha("/images/{image_sha}/vuln/count"),
    },
    {
        "name": "get_image_software",
        "description": "List software installed in a specific image.",
        "parameters": {
            "image_sha": {"type": "string"},
            "filter": {"type": "string", "default": ""},
        },
        "route": _path_with_sha("/images/{image_sha}/software"),
    },
    {
        "name": "get_image_compliance",
        "description": "Get policy compliance details for a specific image.",
        "parameters": {"image_sha": {"type": "string"}},
        "route": _path_with_sha("/images/{image_sha}/compliance"),
    },
    {
        "name": "get_image_secrets",
        "description": "Get detected secrets inside a SPECIFIC image by SHA.",
        "parameters": {"image_sha": {"type": "string"}},
        "route": _path_with_sha("/images/{image_sha}/secrets"),
    },
    {
        "name": "get_image_malware",
        "description": "Get detected malware inside a SPECIFIC image by SHA.",
        "parameters": {"image_sha": {"type": "string"}},
        "route": _path_with_sha("/images/{image_sha}/layers/malware"),
    },
    {
        "name": "get_image_association",
        "description": "Get container associations for a specific image.",
        "parameters": {"image_sha": {"type": "string"}},
        "route": _path_with_sha("/images/{image_sha}/association"),
    },
    {
        "name": "list_images_bulk",
        "description": "Bulk list images with pagination support.",
        "parameters": {
            "filter": {"type": "string", "default": ""},
            "limit": {"type": "integer", "default": 50},
        },
        "route": _path("/images/list"),
    },
    {
        "name": "find_images_with_secrets",
        "description": "Find all images that have secrets detected. Uses filter 'detection.type:secret' per Qualys CS search token docs.",
        "parameters": {"page_size": {"type": "integer", "default": 50}},
        "route": _path("/images", {"filter": "container.image.hasSecrets:true", "sort": "created:desc"}),
    },
    {
        "name": "find_images_with_malware",
        "description": "Find all images that have malware detected. Uses filter 'detection.type:malware' per Qualys CS search token docs.",
        "parameters": {"page_size": {"type": "integer", "default": 50}},
        "route": _path("/images", {"filter": "malware.imageMalwareCount:>0", "sort": "created:desc"}),
    },
    {
        "name": "find_images_by_vuln_severity",
        "description": "Find images filtered by vulnerability severity.",
        "parameters": {
            "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"], "default": "CRITICAL"},
            "page_size": {"type": "integer", "default": 50},
        },
        "route": _path(
            "/images",
            fixed_params={"sort": "created:desc"},
            transform=lambda inputs, params: {**params, "filter": f"vulnerability.severity:{inputs.get('severity', 'CRITICAL')}"},
        ),
    },
    {
        "name": "find_containers_by_vuln_severity",
        "description": "Find containers filtered by vulnerability severity.",
        "parameters": {
            "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"], "default": "CRITICAL"},
            "page_size": {"type": "integer", "default": 50},
        },
        "route": _path(
            "/containers",
            fixed_params={"sort": "created:desc"},
            transform=lambda inputs, params: {**params, "filter": f"vulnerability.severity:{inputs.get('severity', 'CRITICAL')}"},
        ),
    },

    # Registries
    {
        "name": "list_registries",
        "description": "List all container registries configured in Qualys.",
        "parameters": {
            "filter": {"type": "string", "default": ""},
            "page_number": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 50},
        },
        "route": _path("/registry"),
    },
    {
        "name": "get_registry_details",
        "description": "Get details of a specific registry.",
        "parameters": {"registry_id": {"type": "string"}},
        "route": _path_with_sha("/registry/{registry_id}"),
    },
    {
        "name": "get_registry_repositories",
        "description": "List repositories in a specific registry.",
        "parameters": {
            "registry_id": {"type": "string"},
            "page_number": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 50},
        },
        "route": _path_with_sha("/registry/{registry_id}/repository"),
    },
    {
        "name": "get_registry_schedules",
        "description": "Get scan schedules for a specific registry.",
        "parameters": {"registry_id": {"type": "string"}},
        "route": _path_with_sha("/registry/{registry_id}/schedule"),
    },
    {
        "name": "get_registry_schedule_executions",
        "description": "Get execution history for a registry scan schedule.",
        "parameters": {"registry_id": {"type": "string"}, "schedule_id": {"type": "string"}},
        "route": _path_with_sha("/registry/{registry_id}/schedule/{schedule_id}/executions"),
    },

    # Sensors / K8s
    {
        "name": "list_sensors",
        "description": "List all sensors deployed in the environment.",
        "parameters": {
            "filter": {"type": "string", "default": ""},
            "page_number": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 50},
        },
        "route": _path("/sensors"),
    },
    {
        "name": "get_sensor_details",
        "description": "Get details of a specific sensor.",
        "parameters": {"sensor_id": {"type": "string"}},
        "route": _path_with_sha("/sensors/{sensor_id}"),
    },
    {
        "name": "get_activation_keys",
        "description": "Get sensor activation keys.",
        "parameters": {},
        "route": _path("/activationkey"),
    },

    # Reports
    {
        "name": "list_reports",
        "description": "List generated reports in the Qualys account.",
        "parameters": {
            "filter": {"type": "string", "default": ""},
            "page_number": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 50},
        },
        "route": _path("/reports"),
    },
    {
        "name": "get_scheduled_reports",
        "description": "List all scheduled reports.",
        "parameters": {},
        "route": _path("/reports/schedules"),
    },

    # K8s
    {
        "name": "list_k8s_clusters",
        "description": "List all Kubernetes clusters monitored by Qualys.",
        "parameters": {
            "filter": {"type": "string", "default": ""},
            "page_number": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 50},
        },
        "route": _path("/k8sClusters"),
    },
    {
        "name": "get_k8s_cluster",
        "description": "Get details of a specific Kubernetes cluster.",
        "parameters": {"cluster_uid": {"type": "string"}},
        "route": _path_with_sha("/k8sClusters/{cluster_uid}"),
    },
    {
        "name": "list_k8s_pods",
        "description": "List Kubernetes pods across clusters.",
        "parameters": {
            "filter": {"type": "string", "default": ""},
            "page_number": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 50},
        },
        "route": _path("/k8sResource/pod"),
    },
    {
        "name": "list_k8s_namespaces",
        "description": "List Kubernetes namespaces across clusters.",
        "parameters": {
            "filter": {"type": "string", "default": ""},
            "page_number": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 50},
        },
        "route": _path("/k8sResource/namespace"),
    },
    {
        "name": "get_k8s_postures",
        "description": "Get Kubernetes security posture assessment results.",
        "parameters": {
            "filter": {"type": "string", "default": ""},
            "page_number": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 50},
        },
        "route": _path("/k8s_postures/list"),
    },
    {
        "name": "get_k8s_posture_count",
        "description": "Get Kubernetes posture control count summary.",
        "parameters": {"filter": {"type": "string", "default": ""}},
        "route": _path("/k8s_postures/count"),
    },

    # Vulnerabilities / Controls / Exceptions
    {
        "name": "list_vulnerabilities",
        "description": "List vulnerabilities detected across the environment.",
        "parameters": {
            "filter": {"type": "string", "default": ""},
            "page_number": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 50},
        },
        "route": _path("/vulnerability"),
    },
    {
        "name": "get_vulnerability_details",
        "description": "Get details of a specific vulnerability by UUID.",
        "parameters": {"vuln_uuid": {"type": "string"}},
        "route": _path_with_sha("/vulnerability/{vuln_uuid}"),
    },
    {
        "name": "list_controls",
        "description": "List security controls available in Qualys CS.",
        "parameters": {
            "filter": {"type": "string", "default": ""},
            "page_number": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 50},
        },
        "route": _path("/controls"),
    },
    {
        "name": "get_control_details",
        "description": "Get details of a specific security control.",
        "parameters": {"control_id": {"type": "string"}},
        "route": _path_with_sha("/controls/{control_id}"),
    },
    {
        "name": "list_exceptions",
        "description": "List vulnerability exceptions configured in Qualys CS.",
        "parameters": {
            "filter": {"type": "string", "default": ""},
            "page_number": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 50},
        },
        "route": _path("/exception"),
    },
    {
        "name": "get_exception_details",
        "description": "Get details of a specific vulnerability exception.",
        "parameters": {"exception_id": {"type": "string"}},
        "route": _path_with_sha("/exception/{exception_id}"),
    },
    {
        "name": "list_secret_detectors",
        "description": "List secret detection rules configured in Qualys CS.",
        "parameters": {
            "filter": {"type": "string", "default": ""},
            "page_number": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 50},
        },
        "route": _path("/secretDetector"),
    },
]


def get_tool_metadata(name: str) -> ToolDef | None:
    return next((t for t in TOOLS if t["name"] == name), None)


def build_anthropic_tools() -> list[dict[str, Any]]:
    """Convert the shared registry into Anthropic Bedrock tool definitions."""
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "input_schema": {
                "type": "object",
                "properties": t["parameters"],
                "required": [k for k, v in t["parameters"].items() if "default" not in v],
            },
        }
        for t in TOOLS
    ]


def build_route(name: str, inputs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Build the Qualys API path and params for a given tool call."""
    tool = get_tool_metadata(name)
    if not tool:
        raise ValueError(f"Unknown tool: {name}")
    return tool["route"](inputs)
