import logging
from fastapi import APIRouter
from qualys_client import get

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
logger = logging.getLogger("dashboard")


def _int(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _vuln_counts(vuln) -> dict:
    """Normalise Qualys vulnerability dict — always returns ints, never None."""
    if not isinstance(vuln, dict):
        return {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "NONE": 0}
    if "severity5Count" in vuln:
        return {
            "CRITICAL": _int(vuln.get("severity5Count")),
            "HIGH":     _int(vuln.get("severity4Count")),
            "MEDIUM":   _int(vuln.get("severity3Count")),
            "LOW":      _int(vuln.get("severity2Count")),
            "NONE":     _int(vuln.get("severity1Count")),
        }
    return {
        "CRITICAL": _int(vuln.get("critical") or vuln.get("CRITICAL")),
        "HIGH":     _int(vuln.get("high") or vuln.get("HIGH")),
        "MEDIUM":   _int(vuln.get("medium") or vuln.get("MEDIUM")),
        "LOW":      _int(vuln.get("low") or vuln.get("LOW")),
        "NONE":     0,
    }


@router.get("/containers/overview")
async def container_overview():
    """Aggregate container stats: total, vuln severity breakdown, top risky containers."""
    data = get("/containers", {"pageSize": 100})
    logger.info(f"containers/overview raw keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
    containers = data.get("data", data.get("list", []))
    total_count = data.get("count", data.get("totalCount", data.get("total", len(containers))))

    severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "NONE": 0}
    running = 0
    stopped = 0

    for c in containers:
        state = c.get("state", "").upper()
        if state == "RUNNING":
            running += 1
        else:
            stopped += 1

        counts = _vuln_counts(c.get("vulnerabilities", {}))
        for sev in severity_counts:
            severity_counts[sev] += counts[sev]

    top_risky = sorted(
        containers,
        key=lambda c: (
            _vuln_counts(c.get("vulnerabilities", {}))["CRITICAL"] * 1000
            + _vuln_counts(c.get("vulnerabilities", {}))["HIGH"] * 100
        ),
        reverse=True,
    )[:10]

    return {
        "total": total_count,
        "running": running,
        "stopped": stopped,
        "severity_breakdown": severity_counts,
        "top_risky_containers": [
            {
                "id": c.get("containerId"),
                "name": c.get("name") or c.get("imageId", "unknown"),
                "state": c.get("state"),
                "critical": _vuln_counts(c.get("vulnerabilities", {}))["CRITICAL"],
                "high":     _vuln_counts(c.get("vulnerabilities", {}))["HIGH"],
            }
            for c in top_risky
        ],
    }


@router.get("/images/vulnerabilities")
async def image_vulnerabilities():
    """Aggregate image vulnerability stats: severity totals, top vulnerable images."""
    data = get("/images", {"pageSize": 100})
    images = data.get("data", data.get("list", []))
    total_images = data.get("count", data.get("totalCount", data.get("total", len(images))))
    if images:
        logger.info(f"images sample vuln field: {images[0].get('vulnerabilities')}")
    severity_totals = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    for img in images:
        counts = _vuln_counts(img.get("vulnerabilities", {}))
        severity_totals["critical"] += counts["CRITICAL"]
        severity_totals["high"]     += counts["HIGH"]
        severity_totals["medium"]   += counts["MEDIUM"]
        severity_totals["low"]      += counts["LOW"]

    top_vulnerable = sorted(
        images,
        key=lambda i: (
            _vuln_counts(i.get("vulnerabilities", {}))["CRITICAL"] * 1000
            + _vuln_counts(i.get("vulnerabilities", {}))["HIGH"] * 100
        ),
        reverse=True,
    )[:10]

    return {
        "total_images": total_images,
        "severity_totals": severity_totals,
        "top_vulnerable_images": [
            {
                "sha": img.get("sha") or img.get("imageId"),
                "name": (img.get("repo") or [{}])[0].get("repository", "unknown"),
                "tag":  (img.get("repo") or [{}])[0].get("tag", ""),
                "critical": _vuln_counts(img.get("vulnerabilities", {}))["CRITICAL"],
                "high":     _vuln_counts(img.get("vulnerabilities", {}))["HIGH"],
                "medium":   _vuln_counts(img.get("vulnerabilities", {}))["MEDIUM"],
                "low":      _vuln_counts(img.get("vulnerabilities", {}))["LOW"],
            }
            for img in top_vulnerable
        ],
    }


@router.get("/registry/health")
async def registry_health():
    """Registry list with scan status and connector health."""
    data = get("/registry", {"pageSize": 100})
    registries = data.get("data", data.get("list", []))

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
    clusters = clusters_data.get("data", clusters_data.get("list", []))

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
