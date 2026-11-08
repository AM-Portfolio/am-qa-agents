"""Derive api_surface + invent_profile from tools; persist in bank repo (Mongo/memory)."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from ui_evidence.scenario_bank.repo import get_repo, norm_env

_MUTATE = frozenset({"post", "put", "patch", "delete"})
_PUBLIC_HINTS = ("/health", "/ready", "/live", "/ping", "/openapi", "/docs")
_VERBS = (
    "pause",
    "resume",
    "cancel",
    "upgrade",
    "login",
    "register",
    "logout",
    "refresh",
    "meter",
    "check",
    "bootstrap",
)


def _tools_digest(tools: list[dict[str, Any]]) -> str:
    blob = json.dumps(
        sorted(
            {
                f"{(t.get('method') or '').lower()} {(t.get('path') or t.get('operation_path') or '')}"
                for t in tools
                if t.get("path") or t.get("operation_path")
            }
        ),
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def normalize_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for t in tools or []:
        method = str(t.get("method") or "get").lower()
        path = str(t.get("path") or t.get("operation_path") or "")
        if not path:
            continue
        key = f"{method} {path}"
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": str(t.get("name") or key),
                "method": method,
                "path": path,
                "title": str(t.get("title") or t.get("name") or path),
            }
        )
    return rows


def derive_invent_profile(
    service_key: str,
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = normalize_tools(tools)
    gets = [r for r in rows if r["method"] == "get"]
    mutates = [r for r in rows if r["method"] in _MUTATE]
    primary_reads = [
        f"{r['method'].upper()} {r['path']}"
        for r in gets
        if not any(h in r["path"].lower() for h in _PUBLIC_HINTS)
    ][:8]
    if not primary_reads and gets:
        primary_reads = [f"GET {gets[0]['path']}"]
    protected = [
        r["path"]
        for r in rows
        if not any(h in r["path"].lower() for h in _PUBLIC_HINTS)
    ][:20]
    mutate_paths = [r["path"] for r in mutates][:20]
    entities: list[str] = []
    for r in rows:
        parts = [p for p in r["path"].split("/") if p and not p.startswith("{")]
        for p in parts[:3]:
            if p.lower() not in {"api", "v1", "v2", "internal"} and p not in entities:
                entities.append(p.lower())
        if len(entities) >= 8:
            break
    lifecycle = [v for v in _VERBS if any(v in r["path"].lower() for r in rows)]
    observe = next(
        (f"GET {r['path']}" for r in gets if "me" in r["path"].lower()),
        primary_reads[0] if primary_reads else "",
    )
    skill_overlays = {
        "happy_flow": {
            "diversify": [
                "primary reads in sequence from api_surface",
                "health then primary read if /health on surface",
            ]
        },
        "level2_alt_path": {
            "diversify": ["reverse primary read order", "secondary then current"]
        },
        "validation": {
            "diversify": [
                "mutate with empty body",
                "mutate with invalid id on surface path",
            ]
        },
        "null_point": {
            "diversify": [
                "GET unknown id → 404",
                "mutate unknown id → 404",
            ]
        },
        "tweak_data": {
            "diversify": [
                f"mutate then observe ({observe})" if observe else "mutate then GET",
            ]
        },
        "level4_state": {
            "diversify": [
                " → ".join(lifecycle[:4]) if lifecycle else "multi-step lifecycle on surface"
            ]
        },
        "level5_abuse": {
            "diversify": [
                "double terminal action",
                "illegal transition → 4xx",
            ]
        },
        "security": {
            "diversify": [
                f"GET {protected[0]} auth=none → 401" if protected else "protected GET auth=none → 401",
                "mutate auth=none → 401/403",
            ]
        },
        "level3_edge": {
            "diversify": ["idempotent re-apply", "boundary / already-active edge"]
        },
    }
    prefixes = sorted(
        {
            "/" + r["path"].strip("/").split("/")[0]
            for r in rows
            if r["path"].strip("/")
        }
    )[:6]
    domain = (
        f"Auto-derived invent profile for {service_key}. "
        f"Path families: {', '.join(prefixes) or '(none)'}. "
        f"Reads={len(gets)} mutates={len(mutates)}. "
        "Use ONLY api_surface paths for this service."
    )
    return {
        "apiVersion": "am.qa.plugin.invent/v1",
        "service_key": service_key,
        "derived": True,
        "domain": domain,
        "default_auth": "user_jwt",
        "auth_modes": ["user_jwt", "service_token", "none"],
        "entities": entities or [service_key.replace("am-", "")],
        "primary_reads": primary_reads,
        "protected_paths": protected,
        "mutate_paths": mutate_paths,
        "observe_after_mutate": observe,
        "null_ids": ["does-not-exist-xyz", "00000000-0000-0000-0000-000000000000"],
        "lifecycle": lifecycle,
        "notes": [
            "Derived from ingested tools; not hand-authored plugin files",
            "Bind scenarios to this service only",
        ],
        "skill_overlays": skill_overlays,
    }


def derive_and_store(
    service_key: str,
    env: str,
    tools: list[dict[str, Any]],
    *,
    source: str = "tools",
) -> dict[str, Any]:
    """Ingest tools snapshot + write surface + invent_profile to repo."""
    env_n = norm_env(env)
    repo = get_repo()
    rows = normalize_tools(tools)
    digest = _tools_digest(tools)
    lines = [
        f"{r['method'].upper()} {r['path']}"
        + (f"  # {r['title']}" if r.get("title") else "")
        for r in rows
    ]
    surface = {
        "tools": rows,
        "lines": lines,
        "tools_digest": digest,
        "count": len(rows),
    }
    profile = derive_invent_profile(service_key, tools)
    repo.upsert_spec(
        {
            "service_key": service_key,
            "env": env_n,
            "source": source,
            "tools_digest": digest,
            "tool_count": len(rows),
            "tools": rows[:500],
        }
    )
    repo.upsert_surface(service_key, env_n, surface)
    repo.upsert_profile(service_key, env_n, profile)
    return {
        "ok": True,
        "service_key": service_key,
        "env": env_n,
        "tools_digest": digest,
        "surface_count": len(rows),
        "profile": profile,
        "surface": surface,
    }


def load_derived(service_key: str, env: str) -> dict[str, Any]:
    repo = get_repo()
    return {
        "surface": repo.get_surface(service_key, env),
        "profile": repo.get_profile(service_key, env),
        "spec": repo.get_spec(service_key, env),
    }
