"""QQL (Qualys Query Language) token catalog, lookup and filter checking.

Why: the model used to *guess* filter tokens (e.g. ``vulnerability.cisaKev:true``)
and waste Qualys calls. Now it can:

* look tokens up with the ``lookup_qql_tokens`` tool (no Qualys call), and
* get immediate feedback when a filter uses a token that isn't documented for
  that resource, with the closest real tokens suggested.

Data lives in two plain-text files next to this module so anyone can extend them:
``qql_catalog.txt`` (documented tokens per resource) and ``qql_examples.txt``
(team-verified filters).
"""

from __future__ import annotations

import difflib
import os
import re
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS_URL = "https://docs.qualys.com/en/cs/latest/search_tips/search_tokens.htm"

# Which catalog section applies to each tool's ``filter`` parameter.
TOOL_RESOURCE = {
    "list_vulnerabilities": "vulnerability",
    "get_image_vulns": "vulnerability",
    "get_container_vulns": "vulnerability",
    "list_images": "image",
    "list_images_bulk": "image",
    "list_containers": "container",
    "list_containers_bulk": "container",
    "get_image_software": "software",
    "get_container_software": "software",
    "list_sensors": "sensor",
    "list_registries": "registry",
}

RESOURCES = ("vulnerability", "image", "container", "software", "sensor", "registry")

# token followed by ':' or a comparison operator, outside quotes/brackets
_TOKEN_RE = re.compile(r"(?<![\w.\"'`\[])([A-Za-z][\w]*(?:\.[\w]+)*)\s*(?=:|>=|<=|>|<)")
_KEYWORDS = {"and", "or", "not", "now"}


@lru_cache(maxsize=1)
def catalog() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    section = None
    with open(os.path.join(HERE, "qql_catalog.txt"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
                out[section] = []
                continue
            parts = [p.strip() for p in line.split("|")]
            if section and len(parts) >= 3:
                out[section].append({"token": parts[0], "values": parts[1], "description": parts[2]})
    return out


@lru_cache(maxsize=1)
def examples() -> list[dict]:
    out = []
    path = os.path.join(HERE, "qql_examples.txt")
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 3:
                out.append({"question": parts[0], "resource": parts[1], "filter": parts[2]})
    return out


def _tokens(resource: str) -> set[str]:
    return {t["token"] for t in catalog().get(resource, [])}


def tokens_in(filter_text: str) -> list[str]:
    """Token names used in a QQL filter (quoted values and ranges are ignored)."""
    stripped = re.sub(r'"[^"]*"|`[^`]*`|\[[^\]]*\]', " ", filter_text or "")
    seen = []
    for m in _TOKEN_RE.finditer(stripped):
        tok = m.group(1)
        if tok.lower() not in _KEYWORDS and tok not in seen:
            seen.append(tok)
    return seen


def _acronym(word: str) -> str:
    # cisaKnownExploitedVulns -> "ckev"; also keep the first lowercase run ("cisa")
    return "".join(ch for i, ch in enumerate(word) if i == 0 or ch.isupper()).lower()


def suggest(token: str, resource: str, n: int = 3) -> list[str]:
    """Closest documented tokens, matching on the whole name and on its last part.

    e.g. vulnerability.cisaKev -> threatIntel.cisaKnownExploitedVulns,
         vulnerability.severity -> severity, state -> container.instance.state
    """
    last = token.split(".")[-1]
    last_l = last.lower().rstrip("s")
    words = {w.lower().rstrip("s") for w in re.findall(r"[a-z]+|[A-Z][a-z]*", last) if len(w) >= 3}
    descs = {t["token"]: t["description"].lower() for t in catalog().get(resource, [])}
    scored = []
    for k in _tokens(resource):
        k_last = k.split(".")[-1]
        k_last_l = k_last.lower()
        score = max(
            difflib.SequenceMatcher(None, token.lower(), k.lower()).ratio(),
            difflib.SequenceMatcher(None, last.lower(), k_last_l).ratio(),
        )
        if last_l == k_last_l:
            score += 1.0                                   # same final word
        if len(last_l) >= 3 and (k_last_l.startswith(last_l) or last_l in _acronym(k_last)):
            score += 0.6                                   # prefix or acronym (kev)
        if len(last_l) >= 4 and last_l[:4] in k_last_l:
            score += 0.3
        hay = f"{k.lower()} {descs.get(k, '')}"
        score += 0.25 * sum(1 for w in words if w in hay)  # shared words (malware, count, use)
        scored.append((score, -len(k), k))
    scored.sort(reverse=True)
    return [k for score, _, k in scored[:n] if score >= 0.6]


def check_filter(tool_name: str, filter_text: str) -> dict | None:
    """Return None if the filter only uses documented tokens, else a problem report."""
    resource = TOOL_RESOURCE.get(tool_name)
    if not resource or not (filter_text or "").strip():
        return None
    known = _tokens(resource)
    unknown = [t for t in tokens_in(filter_text) if t not in known]
    if not unknown:
        return None
    return {
        "resource": resource,
        "unknown_tokens": unknown,
        "did_you_mean": {t: suggest(t, resource) for t in unknown},
    }


def lookup(resource: str = "", query: str = "", limit: int = 25) -> dict:
    """Search the catalog (and verified examples) by resource and keywords."""
    resources = [resource] if resource in RESOURCES else list(RESOURCES)
    words = [w for w in re.split(r"[\s,]+", (query or "").lower()) if w]
    results = []
    for r in resources:
        for t in catalog().get(r, []):
            hay = f"{t['token']} {t['description']} {t['values']}".lower()
            if not words or any(w in hay for w in words):
                results.append({"resource": r, **t})
    ex = [e for e in examples()
          if (not resource or e["resource"] == resource)
          and (not words or any(w in f"{e['question']} {e['filter']}".lower() for w in words))]
    return {
        "verified_examples": ex[:10],
        "tokens": results[:limit],
        "total_matches": len(results),
        "syntax": "token:value, token>N, token:[from ... to] (dates/now-7d), \"quoted text\", combine with and / or / not",
        "docs": DOCS_URL,
    }


def prompt_block() -> str:
    """Compact guidance + verified examples for the system prompt."""
    lines = [
        "QQL FILTERS — NEVER GUESS TOKEN NAMES:",
        "- Before using a `filter`, use a verified example below or call lookup_qql_tokens(resource, keywords).",
        "- Tokens differ by resource: the vulnerability list uses `threatIntel.*`/`severity`, images use "
        "`vulnerabilities.*`/`container.image.*`, containers use `container.instance.*`.",
        "- Severity is a number 1-5 (5 = critical), not a word.",
        "- If a tool says a token is unknown, use its suggestions; don't retry variations blindly.",
        "VERIFIED FILTERS (question → resource → filter):",
    ]
    for e in examples():
        lines.append(f"- {e['question']} → {e['resource']} → {e['filter']}")
    return "\n".join(lines)
