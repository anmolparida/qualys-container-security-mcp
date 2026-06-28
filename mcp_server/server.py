from mcp.server.fastmcp import FastMCP
from qualys_client import get

mcp = FastMCP("qualys-cs")

# ── Containers ────────────────────────────────────────────────────────────────

@mcp.tool()
def list_containers(filter: str = "", page_number: int = 1, page_size: int = 50, sort: str = "created:desc") -> dict:
    """List containers in the Qualys account with optional filtering and sorting."""
    return get("/containers", {"filter": filter, "pageNumber": page_number, "pageSize": page_size, "sort": sort})


@mcp.tool()
def get_container_details(container_sha: str) -> dict:
    """Get full details of a specific container by its SHA."""
    return get(f"/containers/{container_sha}")


@mcp.tool()
def get_container_vulns(container_sha: str, filter: str = "", vuln_type: str = "ALL") -> dict:
    """Get vulnerability details for a specific container."""
    return get(f"/containers/{container_sha}/vuln", {"filter": filter, "type": vuln_type})


@mcp.tool()
def get_container_vuln_count(container_sha: str) -> dict:
    """Get vulnerability count summary for a specific container."""
    return get(f"/containers/{container_sha}/vuln/count")


@mcp.tool()
def get_container_software(container_sha: str, filter: str = "", sort: str = "name:asc") -> dict:
    """List software installed on a specific container."""
    return get(f"/containers/{container_sha}/software", {"filter": filter, "sort": sort})


@mcp.tool()
def get_container_compliance(container_sha: str) -> dict:
    """Get policy compliance details for a specific container."""
    return get(f"/containers/{container_sha}/compliance")


@mcp.tool()
def list_containers_bulk(filter: str = "", limit: int = 50, pagination_query: str = "") -> dict:
    """Bulk list containers with pagination support."""
    params = {"filter": filter, "limit": limit}
    if pagination_query:
        params["paginationQuery"] = pagination_query
    return get("/containers/list", params)


# ── Images ────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_images(filter: str = "", page_number: int = 1, page_size: int = 50, sort: str = "created:desc") -> dict:
    """List container images in the Qualys account with optional filtering."""
    return get("/images", {"filter": filter, "pageNumber": page_number, "pageSize": page_size, "sort": sort})


@mcp.tool()
def get_image_details(image_sha: str) -> dict:
    """Get full details of a specific image by its SHA."""
    return get(f"/images/{image_sha}")


@mcp.tool()
def get_image_vulns(image_sha: str, filter: str = "", vuln_type: str = "ALL") -> dict:
    """Get vulnerability details for a specific image."""
    return get(f"/images/{image_sha}/vuln", {"filter": filter, "type": vuln_type})


@mcp.tool()
def get_image_vuln_count(image_sha: str) -> dict:
    """Get vulnerability count summary for a specific image."""
    return get(f"/images/{image_sha}/vuln/count")


@mcp.tool()
def get_image_software(image_sha: str, filter: str = "") -> dict:
    """List software installed in a specific image."""
    return get(f"/images/{image_sha}/software", {"filter": filter})


@mcp.tool()
def get_image_compliance(image_sha: str) -> dict:
    """Get policy compliance details for a specific image."""
    return get(f"/images/{image_sha}/compliance")


@mcp.tool()
def get_image_secrets(image_sha: str) -> dict:
    """Get detected secrets in a specific image."""
    return get(f"/images/{image_sha}/secrets")


@mcp.tool()
def get_image_malware(image_sha: str) -> dict:
    """Get detected malware across image layers."""
    return get(f"/images/{image_sha}/layers/malware")


@mcp.tool()
def get_image_association(image_sha: str) -> dict:
    """Get container associations for a specific image."""
    return get(f"/images/{image_sha}/association")


@mcp.tool()
def list_images_bulk(filter: str = "", limit: int = 50, pagination_query: str = "") -> dict:
    """Bulk list images with pagination support."""
    params = {"filter": filter, "limit": limit}
    if pagination_query:
        params["paginationQuery"] = pagination_query
    return get("/images/list", params)


# ── Registry ──────────────────────────────────────────────────────────────────

@mcp.tool()
def list_registries(filter: str = "", page_number: int = 1, page_size: int = 50) -> dict:
    """List all container registries configured in Qualys."""
    return get("/registry", {"filter": filter, "pageNumber": page_number, "pageSize": page_size})


@mcp.tool()
def get_registry_details(registry_id: str) -> dict:
    """Get details of a specific registry."""
    return get(f"/registry/{registry_id}")


@mcp.tool()
def get_registry_repositories(registry_id: str, page_number: int = 1, page_size: int = 50) -> dict:
    """List repositories in a specific registry."""
    return get(f"/registry/{registry_id}/repository", {"pageNumber": page_number, "pageSize": page_size})


@mcp.tool()
def get_registry_schedules(registry_id: str) -> dict:
    """Get scan schedules for a specific registry."""
    return get(f"/registry/{registry_id}/schedule")


@mcp.tool()
def get_registry_schedule_executions(registry_id: str, schedule_id: str) -> dict:
    """Get execution history for a registry scan schedule."""
    return get(f"/registry/{registry_id}/schedule/{schedule_id}/executions")


# ── Sensors ───────────────────────────────────────────────────────────────────

@mcp.tool()
def list_sensors(filter: str = "", page_number: int = 1, page_size: int = 50) -> dict:
    """List all sensors deployed in the environment."""
    return get("/sensors", {"filter": filter, "pageNumber": page_number, "pageSize": page_size})


@mcp.tool()
def get_sensor_details(sensor_id: str) -> dict:
    """Get details of a specific sensor."""
    return get(f"/sensors/{sensor_id}")


@mcp.tool()
def get_activation_keys() -> dict:
    """Get sensor activation keys."""
    return get("/activationkey")


# ── Reports ───────────────────────────────────────────────────────────────────

@mcp.tool()
def list_reports(filter: str = "", page_number: int = 1, page_size: int = 50) -> dict:
    """List generated reports in the Qualys account."""
    return get("/reports", {"filter": filter, "pageNumber": page_number, "pageSize": page_size})


@mcp.tool()
def get_scheduled_reports() -> dict:
    """List all scheduled reports."""
    return get("/reports/schedules")


# ── K8s ───────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_k8s_clusters(filter: str = "", page_number: int = 1, page_size: int = 50) -> dict:
    """List all Kubernetes clusters monitored by Qualys."""
    return get("/k8sClusters", {"filter": filter, "pageNumber": page_number, "pageSize": page_size})


@mcp.tool()
def get_k8s_cluster(cluster_uid: str) -> dict:
    """Get details of a specific Kubernetes cluster."""
    return get(f"/k8sClusters/{cluster_uid}")


@mcp.tool()
def list_k8s_pods(filter: str = "", page_number: int = 1, page_size: int = 50) -> dict:
    """List Kubernetes pods across clusters."""
    return get("/k8sResource/pod", {"filter": filter, "pageNumber": page_number, "pageSize": page_size})


@mcp.tool()
def list_k8s_namespaces(filter: str = "", page_number: int = 1, page_size: int = 50) -> dict:
    """List Kubernetes namespaces across clusters."""
    return get("/k8sResource/namespace", {"filter": filter, "pageNumber": page_number, "pageSize": page_size})


@mcp.tool()
def get_k8s_postures(filter: str = "", page_number: int = 1, page_size: int = 50) -> dict:
    """Get Kubernetes security posture assessment results."""
    return get("/k8s_postures/list", {"filter": filter, "pageNumber": page_number, "pageSize": page_size})


@mcp.tool()
def get_k8s_posture_count(filter: str = "") -> dict:
    """Get Kubernetes posture control count summary."""
    return get("/k8s_postures/count", {"filter": filter})


# ── Vulnerabilities ───────────────────────────────────────────────────────────

@mcp.tool()
def list_vulnerabilities(filter: str = "", page_number: int = 1, page_size: int = 50) -> dict:
    """List vulnerabilities detected across the environment."""
    return get("/vulnerability", {"filter": filter, "pageNumber": page_number, "pageSize": page_size})


@mcp.tool()
def get_vulnerability_details(vuln_uuid: str) -> dict:
    """Get details of a specific vulnerability by UUID."""
    return get(f"/vulnerability/{vuln_uuid}")


# ── Controls ──────────────────────────────────────────────────────────────────

@mcp.tool()
def list_controls(filter: str = "", page_number: int = 1, page_size: int = 50) -> dict:
    """List security controls available in Qualys CS."""
    return get("/controls", {"filter": filter, "pageNumber": page_number, "pageSize": page_size})


@mcp.tool()
def get_control_details(control_id: str) -> dict:
    """Get details of a specific security control."""
    return get(f"/controls/{control_id}")


# ── Exceptions ────────────────────────────────────────────────────────────────

@mcp.tool()
def list_exceptions(filter: str = "", page_number: int = 1, page_size: int = 50) -> dict:
    """List vulnerability exceptions configured in Qualys CS."""
    return get("/exception", {"filter": filter, "pageNumber": page_number, "pageSize": page_size})


@mcp.tool()
def get_exception_details(exception_id: str) -> dict:
    """Get details of a specific vulnerability exception."""
    return get(f"/exception/{exception_id}")


# ── Secret Detector ───────────────────────────────────────────────────────────

@mcp.tool()
def list_secret_detectors(filter: str = "", page_number: int = 1, page_size: int = 50) -> dict:
    """List secret detection rules configured in Qualys CS."""
    return get("/secretDetector", {"filter": filter, "pageNumber": page_number, "pageSize": page_size})


# ── Documentation Resources ─────────────────────────────────────────────────────

@mcp.resource("docs://qualys-container-security")
def qualys_container_security_docs() -> str:
    """Qualys Container Security product documentation."""
    return "https://docs.qualys.com/en/cs/latest/get_started/cs_docs.htm"


@mcp.resource("docs://qualys-container-scanner")
def qualys_container_scanner_docs() -> str:
    """Qualys Container Scanner usage documentation."""
    return "https://docs.qualys.com/en/qscanner/latest/qscanner_usage/use_qscanner.htm"


@mcp.resource("docs://qualys-cybersecurity-risk-rating")
def qualys_crs_docs() -> str:
    """Qualys CyberSecurity Risk Rating (CRS) getting started documentation."""
    return "https://docs.qualys.com/en/crs/latest/get_started/get_started.htm"


if __name__ == "__main__":
    import dotenv, os
    dotenv.load_dotenv()
    mcp.run(transport="stdio")
