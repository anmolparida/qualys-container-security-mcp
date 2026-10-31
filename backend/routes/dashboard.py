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


# --------------------------------------------------------------------------- #
# Threat intelligence: vulnerabilities by Qualys threatIntel.* category
# Tokens: https://docs.qualys.com/en/cs/latest/search_tips/searching_for_vulnerabilities.htm
# --------------------------------------------------------------------------- #
import asyncio
import time

import httpx

from fastapi import HTTPException

from qualys_client import cache_scope, get_async

THREAT_INTEL = [
    # key (token suffix), label, description, group
    ("cisaKnownExploitedVulns", "CISA KEV", "Listed in the CISA Known Exploited Vulnerabilities catalog", "exploited"),
    ("activeAttacks", "Active attacks", "Being actively attacked in the wild", "exploited"),
    ("ransomware", "Ransomware", "Associated with ransomware attacks", "exploited"),
    ("malware", "Malware", "Associated with malware", "exploited"),
    ("solorigateSunburst", "Solorigate / Sunburst", "Associated with Solorigate / Sunburst", "exploited"),
    ("publicExploit", "Public exploit", "A public exploit exists", "exploitability"),
    ("easyExploit", "Easy exploit", "Easy to exploit", "exploitability"),
    ("unauthenticatedExploitation", "No auth needed", "Exploitable without authentication", "exploitability"),
    ("remoteCodeExecution", "Remote code execution", "Enables remote code execution", "exploitability"),
    ("wormable", "Wormable", "Can spread on its own", "exploitability"),
    ("predictedHighRisk", "Predicted high risk", "Predicted to become high risk", "exploitability"),
    ("privilegeEscalation", "Privilege escalation", "Leads to privilege escalation", "impact"),
    ("highLateralMovement", "Lateral movement", "Enables high lateral movement", "impact"),
    ("highDataLoss", "High data loss", "Can cause high data loss", "impact"),
    ("denialOfService", "Denial of service", "Can cause denial of service", "impact"),
    ("noPatch", "No patch", "No patch available yet", "impact"),
]
_TI_KEYS = {k for k, *_ in THREAT_INTEL}
_TI_CACHE: dict[tuple, tuple[float, object]] = {}
_TI_TTL = 300          # seconds; per Qualys account
_TI_CONCURRENCY = 2    # parallel Qualys calls per page load (stay gentle on rate limits)
_TI_RETRIES = 3        # retries on 429 / 5xx / timeouts, with backoff


def _cached(key: tuple):
    hit = _TI_CACHE.get(key)
    if hit and time.time() - hit[0] < _TI_TTL:
        return hit[1]
    return None


def _store(key: tuple, value):
    if len(_TI_CACHE) > 2000:
        _TI_CACHE.clear()
    _TI_CACHE[key] = (time.time(), value)
    return value


def _total(data, page_size: int):
    """(count, capped) from a Qualys list response."""
    if isinstance(data, dict):
        for k in ("count", "totalCount", "total", "totalRecords"):
            if isinstance(data.get(k), (int, float)) or str(data.get(k, "")).isdigit():
                return int(data[k]), False
        rows = data.get("data", data.get("list", []))
    else:
        rows = data or []
    return len(rows), len(rows) >= page_size


def _sev(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _first(d: dict, *keys):
    """First key that is present (0 and False are real values)."""
    for k in keys:
        if d.get(k) is not None:
            return d[k]
    return None


def _vuln_row(v: dict) -> dict:
    cves = _first(v, "cveids", "cveIds", "cves") or []
    if isinstance(cves, str):
        cves = [c.strip() for c in cves.split(",") if c.strip()]
    nested = v.get("vulnerabilities") if isinstance(v.get("vulnerabilities"), dict) else {}
    return {
        "qid": v.get("qid"),
        "title": _first(v, "title", "name") or "",
        "severity": _sev(v.get("severity")),
        "cves": list(cves)[:5],
        "patch_available": _first(v, "patchAvailable") if "patchAvailable" in v else nested.get("patchAvailable"),
        "first_found": _first(v, "firstFound", "published"),
        "images": _first(v, "imageCount", "affectedImages", "imagesCount"),
        "containers": _first(v, "containerCount", "affectedContainers", "containersCount"),
    }


@router.get("/threat-intel")
async def threat_intel_overview():
    """How many vulnerabilities fall into each threatIntel category (one small call each, cached 5 min)."""
    scope = cache_scope()
    cached = _cached(("ti-overview", scope))
    if cached is not None:
        return cached

    sem = asyncio.Semaphore(_TI_CONCURRENCY)
    # Only the total is needed: ask for 1 record (Qualys returns the overall count).
    # Fetching hundreds of full records per category made big categories time out.
    probe_size = 1
    fallback_size = 200  # only if this API version returns no total count

    async def fetch(key, size):
        """One category, retrying rate limits / transient errors with backoff."""
        delay = 1.0
        for attempt in range(_TI_RETRIES + 1):
            try:
                return await get_async("/vulnerability", {"filter": f"threatIntel.{key}:true", "pageSize": size})
            except httpx.HTTPStatusError as e:
                code = e.response.status_code
                if code in (429, 500, 502, 503, 504) and attempt < _TI_RETRIES:
                    retry_after = e.response.headers.get("Retry-After", "")
                    wait = float(retry_after) if retry_after.replace(".", "", 1).isdigit() else delay
                    logger.info(f"threat-intel {key}: HTTP {code}, retrying in {min(wait, 10):.1f}s")
                    await asyncio.sleep(min(wait, 10))
                    delay *= 2
                    continue
                raise
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt < _TI_RETRIES:
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                raise

    async def one(key, label, desc, group):
        async with sem:
            try:
                data = await fetch(key, probe_size)
                count, capped = _total(data, probe_size)
                if capped:  # no total in the response: count a bigger page instead
                    data = await fetch(key, fallback_size)
                    count, capped = _total(data, fallback_size)
                return {"key": key, "label": label, "description": desc, "group": group,
                        "count": count, "capped": capped, "error": None}
            except httpx.HTTPStatusError as e:  # one failing category shouldn't break the page
                code = e.response.status_code
                reason = {429: "rate limited by Qualys", 400: "filter not supported on this platform"}.get(code, "")
                logger.warning(f"threat-intel {key}: HTTP {code} {e.response.text[:200]}")
                return {"key": key, "label": label, "description": desc, "group": group,
                        "count": None, "capped": False, "error": f"HTTP {code}{' - ' + reason if reason else ''}"}
            except Exception as e:
                logger.warning(f"threat-intel {key}: {type(e).__name__}: {e}")
                return {"key": key, "label": label, "description": desc, "group": group,
                        "count": None, "capped": False, "error": f"{type(e).__name__}: {str(e)[:150]}"}

    results = await asyncio.gather(*(one(*t) for t in THREAT_INTEL))
    auth_errors = [r for r in results if r["error"] and ("401" in r["error"] or "rejected" in r["error"].lower())]
    if auth_errors and len(auth_errors) == len(results):
        raise HTTPException(status_code=401, detail="Qualys rejected the credentials")
    body = {"categories": list(results), "cached_for_seconds": _TI_TTL}
    if any(r["error"] for r in results):
        return body  # don't cache partial failures: Refresh retries them right away
    return _store(("ti-overview", scope), body)


@router.get("/threat-intel/{key}")
async def threat_intel_detail(key: str, severity_min: int = 0, page_size: int = 25):
    """Top vulnerabilities in one threatIntel category, most severe first."""
    if key not in _TI_KEYS:
        raise HTTPException(status_code=404, detail="Unknown threat-intel category")
    page_size = max(1, min(page_size, 100))
    scope = cache_scope()
    ck = ("ti-detail", scope, key, severity_min, page_size)
    cached = _cached(ck)
    if cached is not None:
        return cached

    flt = f"threatIntel.{key}:true"
    if 1 <= severity_min <= 5:
        sevs = " or ".join(f"severity:{n}" for n in range(int(severity_min), 6))
        flt += f" and ({sevs})"
    data = await get_async("/vulnerability", {"filter": flt, "pageSize": page_size})
    rows = data.get("data", data.get("list", [])) if isinstance(data, dict) else (data or [])
    count, capped = _total(data, page_size)
    items = sorted((_vuln_row(v) for v in rows if isinstance(v, dict)), key=lambda r: -r["severity"])
    label = next(l for k, l, *_ in THREAT_INTEL if k == key)
    return _store(ck, {"key": key, "label": label, "filter": flt, "total": count, "capped": capped, "items": items})
