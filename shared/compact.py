"""Shrink Qualys list responses before they reach the model.

Qualys CS records are large (layers, labels, environment, software lists...).
Sending them raw means only ~10 records fit in the model's tool-result budget,
so the model learns to request tiny pages and page through them - slow and
expensive. Compacting keeps the fields that answer questions and summarises the
bulky ones, so 100+ records fit in one call.

Rules (generic, so they work for every endpoint):
  * nested objects flattened to dotted keys (cluster.k8s.pod.namespace -> pod.namespace)
  * epoch-ms dates -> YYYY-MM-DD; internal nested uuids dropped
  * scalars kept; long text cut to 160 chars (identifiers like sha/id are never cut)
  * nested objects kept to depth 3
  * lists of scalars: first 5 + a count;  lists of objects: first 3 (compacted) + a count
  * known-bulky keys are reduced to a count
  * empty values dropped
"""

from __future__ import annotations

import json
from typing import Any

MAX_STR = 160
MAX_DEPTH = 4
MAX_SCALARS = 5
MAX_OBJECTS = 3

# Bulky fields that rarely answer a question: replaced by their size.
BULKY_KEYS = {
    "layers", "layer", "environment", "env", "arguments", "args", "labels", "label",
    "portMapping", "ports", "path", "software", "softwares", "packages", "services",
    "users", "hostArchitecture", "metadata", "annotations", "drift", "controls",
    "lastScanDetails", "scanTypes", "repoDigests", "history", "command",
}


_ID_HINTS = ("sha", "id", "digest", "uuid", "qid", "cve")


def _cut(s: str, key: str = "") -> str:
    # Identifiers (sha, imageId, digest, ...) stay whole: the model passes them to
    # follow-up tools such as get_image_details(image_sha=...).
    if any(h in key.lower().rsplit(".", 1)[-1] for h in _ID_HINTS):
        return s
    return s if len(s) <= MAX_STR else s[:MAX_STR] + "…"


def _skip(key: str, nested: bool) -> bool:
    k = key.lower()
    if nested and k in ("uuid", "uid", "id"):
        return True                      # internal IDs of nested objects
    return (k.endswith("uuid") and k != "uuid") or k in {"customerid", "customeruuid"}


# Shorter names for long, very common paths (saves ~30% per record).
_ALIASES = (
    ("vulnerabilities.severity5Count", "vulns.critical"),
    ("vulnerabilities.severity4Count", "vulns.high"),
    ("vulnerabilities.severity3Count", "vulns.medium"),
    ("vulnerabilities.severity2Count", "vulns.low"),
    ("vulnerabilities.severity1Count", "vulns.info"),
    ("cluster.k8s.pod.controller.", "pod.controller."),
    ("cluster.k8s.pod.", "pod."),
    ("cluster.k8s.", "k8s."),
)


def _alias(key: str) -> str:
    for long, short in _ALIASES:
        if key == long or (long.endswith(".") and key.startswith(long)):
            return short + key[len(long):] if long.endswith(".") else short
    return key


def _date(key: str, value: Any) -> Any:
    """Epoch milliseconds -> YYYY-MM-DD for date-like fields."""
    k = key.lower()
    if any(w in k for w in ("date", "created", "updated", "changed", "scanned", "time", "found")):
        try:
            n = int(value)
            if 10**11 < n < 10**14:
                import datetime
                return datetime.datetime.fromtimestamp(n / 1000, datetime.timezone.utc).strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            pass
    return value


def _flatten(value: Any, prefix: str, out: dict, depth: int) -> None:
    """Flatten nested objects to dotted keys: {"cluster": {"k8s": {"pod": {"namespace": "prod"}}}}
    -> {"cluster.k8s.pod.namespace": "prod"}. Lists are summarised."""
    if isinstance(value, dict):
        for k, v in value.items():
            if _skip(k, bool(prefix)):
                continue
            key = f"{prefix}.{k}" if prefix else k
            if k in BULKY_KEYS and isinstance(v, (list, dict)):
                if len(v):
                    out[f"{key}Count"] = len(v)
                continue
            _flatten(v, key, out, depth + 1)
        return
    if isinstance(value, list):
        if not value:
            return
        if all(not isinstance(v, (dict, list)) for v in value):
            out[_alias(prefix)] = [_cut(str(v)) if isinstance(v, str) else v for v in value[:MAX_SCALARS]]
            if len(value) > MAX_SCALARS:
                out[_alias(prefix) + "Count"] = len(value)
            return
        if depth >= MAX_DEPTH:
            out[f"{prefix}Count"] = len(value)
            return
        for i, v in enumerate(value[:MAX_OBJECTS]):
            _flatten(v, f"{prefix}[{i}]", out, depth + 1)
        if len(value) > MAX_OBJECTS:
            out[f"{prefix}Count"] = len(value)
        return
    if value is None or value == "":
        return
    value = _date(prefix, value)
    out[_alias(prefix)] = _cut(value, prefix) if isinstance(value, str) else value


def _compact(value: Any, depth: int = 0) -> Any:
    if isinstance(value, (dict, list)):
        out: dict = {}
        _flatten(value, "", out, depth)
        return out
    return _cut(value) if isinstance(value, str) else value


def _rows(data: Any) -> tuple[list | None, str | None]:
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("data", "list", "items", "content"):
            if isinstance(data.get(key), list):
                return data[key], key
    return None, None


def _total(data: Any) -> int | None:
    if isinstance(data, dict):
        for k in ("count", "totalCount", "total", "totalRecords", "totalElements"):
            v = data.get(k)
            if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
                return int(v)
    return None


def compact_response(data: Any, page_size: int | None = None, page_number: int | None = None,
                     max_chars: int | None = None) -> Any:
    """Compact a Qualys response. List responses get a paging envelope.

    With ``max_chars`` the item list is cut at a record boundary (never mid-record)
    and ``omitted`` says how many records didn't fit, so the model knows to narrow
    the filter or fetch the next page instead of assuming it saw everything.
    """
    rows, _ = _rows(data)
    if rows is None:
        return _compact(data)
    total = _total(data)
    returned = len(rows)
    page = page_number or 1
    if total is not None:
        has_more = page * (page_size or returned or 1) < total
    else:
        has_more = bool(page_size) and returned >= page_size
    items, used = [], 200
    for r in rows:
        c = _compact(r, 1)
        size = len(json.dumps(c, default=str)) + 2
        if max_chars and items and used + size > max_chars:
            break
        items.append(c)
        used += size
    env = {"total": total, "returned": returned, "page": page, "has_more": has_more, "items": items}
    if len(items) < returned:
        env["omitted"] = returned - len(items)
        env["note"] = (f"{returned - len(items)} records didn't fit; narrow the filter or ask for a smaller page "
                       "if you need them.")
    return env
