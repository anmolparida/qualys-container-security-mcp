from fastapi import APIRouter
from qualys_client import get

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/containers/overview")
async def container_overview():
    """Aggregate container stats: total, vuln severity breakdown, top risky containers."""
    data = get("/containers", {"pageSize": 100})
    containers = data.get("list", [])

    severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "NONE": 0}
    running = 0
    stopped = 0

    for c in containers:
        state = c.get("state", "").upper()
        if state == "RUNNING":
            running += 1
        else:
            stopped += 1

        vuln_summary = c.get("vulnerabilities", {})
        for sev in severity_counts:
            severity_counts[sev] += vuln_summary.get(sev.lower(), 0)

    top_risky = sorted(
        containers,
        key=lambda c: (
            c.get("vulnerabilities", {}).get("critical", 0) * 1000
            + c.get("vulnerabilities", {}).get("high", 0) * 100
        ),
        reverse=True,
    )[:10]

    return {
        "total": len(containers),
        "running": running,
        "stopped": stopped,
        "severity_breakdown": severity_counts,
        "top_risky_containers": [
            {
                "id": c.get("containerId"),
                "name": c.get("name") or c.get("imageId", "unknown"),
                "state": c.get("state"),
                "critical": c.get("vulnerabilities", {}).get("critical", 0),
                "high": c.get("vulnerabilities", {}).get("high", 0),
            }
            for c in top_risky
        ],
    }


@router.get("/images/vulnerabilities")
async def image_vulnerabilities():
    """Aggregate image vulnerability stats: severity totals, top vulnerable images."""
    data = get("/images", {"pageSize": 100})
    images = data.get("list", [])

    severity_totals = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    for img in images:
        vuln = img.get("vulnerabilities", {})
        for sev in severity_totals:
            severity_totals[sev] += vuln.get(sev, 0)

    top_vulnerable = sorted(
        images,
        key=lambda i: (
            i.get("vulnerabilities", {}).get("critical", 0) * 1000
            + i.get("vulnerabilities", {}).get("high", 0) * 100
        ),
        reverse=True,
    )[:10]

    return {
        "total_images": len(images),
        "severity_totals": severity_totals,
        "top_vulnerable_images": [
            {
                "sha": img.get("imageId"),
                "name": img.get("label", [{}])[0].get("name", "unknown") if img.get("label") else "unknown",
                "tag": img.get("tag", ""),
                "critical": img.get("vulnerabilities", {}).get("critical", 0),
                "high": img.get("vulnerabilities", {}).get("high", 0),
                "medium": img.get("vulnerabilities", {}).get("medium", 0),
                "low": img.get("vulnerabilities", {}).get("low", 0),
            }
            for img in top_vulnerable
        ],
    }


@router.get("/registry/health")
async def registry_health():
    """Registry list with scan status and connector health."""
    data = get("/registry", {"pageSize": 100})
    registries = data.get("list", [])

    return {
        "total": len(registries),
        "registries": [
            {
                "id": r.get("registryId"),
                "name": r.get("connectorName") or r.get("uri", "unknown"),
                "type": r.get("type"),
                "state": r.get("scanStatus") or r.get("state"),
                "last_scanned": r.get("lastScannedDate") or r.get("updatedDate"),
                "total_images": r.get("totalImages", 0),
            }
            for r in registries
        ],
    }


@router.get("/k8s/posture")
async def k8s_posture():
    """K8s cluster overview with posture pass/fail counts."""
    clusters_data = get("/k8sClusters", {"pageSize": 100})
    clusters = clusters_data.get("list", [])

    posture_count = get("/k8s_postures/count", {})

    return {
        "total_clusters": len(clusters),
        "clusters": [
            {
                "uid": c.get("clusterUid"),
                "name": c.get("clusterName"),
                "version": c.get("version"),
                "node_count": c.get("nodeCount", 0),
                "sensor_status": c.get("sensorStatus"),
            }
            for c in clusters
        ],
        "posture_summary": posture_count,
    }


@router.get("/sensors/overview")
async def sensors_overview():
    """Sensor deployment status overview."""
    data = get("/sensors", {"pageSize": 100})
    sensors = data.get("list", [])

    active = sum(1 for s in sensors if s.get("status", "").upper() == "ACTIVE")

    return {
        "total": len(sensors),
        "active": active,
        "inactive": len(sensors) - active,
        "sensors": [
            {
                "id": s.get("sensorId"),
                "hostname": s.get("hostname"),
                "status": s.get("status"),
                "version": s.get("version"),
                "last_updated": s.get("lastUpdated"),
            }
            for s in sensors
        ],
    }
