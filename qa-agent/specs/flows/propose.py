"""Propose new API-flow use cases from OpenAPI catalog (+ optional LiteLLM)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_SERVICE_GROUP = {
    "am-identity": "identity",
    "am-subscription": "subscription",
}


def _list_tools(service: str) -> list[dict[str, Any]]:
    try:
        from specs.openapi_tools.registry import list_tools

        return list(list_tools(service=service, limit=200).get("tools") or [])
    except Exception:  # noqa: BLE001
        logger.exception("propose list_tools failed service=%s", service)
        return []


def _existing_paths(group: str) -> set[str]:
    from specs.flows.catalog import list_flows, get_flow

    paths: set[str] = set()
    for row in list_flows(group=group):
        doc = get_flow(str(row["id"]))
        if not doc:
            continue
        for n in doc.get("nodes") or []:
            for key in ("exact_path", "path", "path_contains"):
                p = n.get(key)
                if isinstance(p, str) and p.startswith("/"):
                    paths.add(p.lower())
    return paths


def _heuristic_proposals(
    *,
    service: str,
    group: str,
    category: str | None,
    gate: str,
    max_scenarios: int,
    tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    existing = _existing_paths(group)
    out: list[dict[str, Any]] = []
    for tool in tools:
        if len(out) >= max_scenarios:
            break
        method = str(tool.get("method") or "get").lower()
        path = str(tool.get("path") or tool.get("path_template") or "").strip()
        if not path.startswith("/"):
            continue
        if path.lower() in existing:
            continue
        # Skip destructive methods for auto-propose under prod_safe
        if gate == "prod_safe" and method in {"delete", "put", "patch"}:
            continue
        name = str(tool.get("name") or tool.get("operation_id") or path).strip()
        slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()[:40]
        cat = (category or ("auth" if "auth" in path.lower() else "general")).lower()
        needs_auth = "auth" not in path.lower() and method == "get"
        nodes: list[dict[str, Any]] = []
        if needs_auth and group == "subscription":
            nodes.append(
                {
                    "id": "login",
                    "kind": "call_tool",
                    "service": "am-identity",
                    "method": "post",
                    "path_contains": "/auth/login",
                    "uses_spt_auth_creds": True,
                    "capture_tokens": True,
                    "label": "login",
                }
            )
        nodes.append(
            {
                "id": f"step_{len(nodes)+1}",
                "kind": "call_tool",
                "service": service,
                "method": method,
                "exact_path": path,
                "auth": needs_auth,
                "optional": True,
                "label": name.split(".")[-1] if "." in name else name,
            }
        )
        out.append(
            {
                "id": f"FLOW_{group.upper()}_{slug}"[:80],
                "title": f"{group}: {name}",
                "gate": gate,
                "group": group,
                "category": cat,
                "description": f"Proposed from OpenAPI {method.upper()} {path}",
                "tags": ["proposed", "openapi"],
                "created_by": "llm",
                "nodes": nodes,
                "rationale": "Heuristic from OpenAPI tool catalog (LLM unavailable or unused).",
                "source": "heuristic",
            }
        )
    return out


def _llm_proposals(
    *,
    service: str,
    group: str,
    category: str | None,
    gate: str,
    max_scenarios: int,
    tools: list[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    """Ask LiteLLM for flow JSON; return None if LLM unavailable."""
    try:
        from ui_evidence.scenario_bank.llm_status import probe_litellm
        from ui_evidence.scenario_bank.scenario_planner import _default_chat
    except Exception:  # noqa: BLE001
        return None
    probe = probe_litellm(ping_chat=False)
    if not probe.get("available"):
        return None
    catalog = [
        {
            "method": t.get("method"),
            "path": t.get("path") or t.get("path_template"),
            "name": t.get("name") or t.get("operation_id"),
        }
        for t in tools[:80]
    ]
    system = (
        "You propose API QA flow use-cases as JSON only. "
        "Return {\"scenarios\":[{id,title,category,description,nodes,rationale}]}. "
        "Each node: id, service, method, exact_path or path_contains, auth bool, optional bool. "
        "No secrets. Prefer GET/POST login. Max nodes per scenario: 4."
    )
    user = json.dumps(
        {
            "service": service,
            "group": group,
            "category_hint": category,
            "gate": gate,
            "max_scenarios": max_scenarios,
            "openapi_tools": catalog,
        },
        ensure_ascii=False,
    )
    try:
        text = _default_chat(system, user)
    except Exception:  # noqa: BLE001
        logger.exception("propose llm chat failed")
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text or "")
        if not m:
            return None
        try:
            parsed = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    rows = parsed.get("scenarios") if isinstance(parsed, dict) else None
    if not isinstance(rows, list):
        return None
    out: list[dict[str, Any]] = []
    for raw in rows[:max_scenarios]:
        if not isinstance(raw, dict):
            continue
        nodes = raw.get("nodes") if isinstance(raw.get("nodes"), list) else []
        if not nodes:
            continue
        fid = str(raw.get("id") or "").strip() or f"FLOW_{group.upper()}_LLM_{len(out)+1}"
        out.append(
            {
                "id": fid[:80],
                "title": str(raw.get("title") or fid),
                "gate": gate,
                "group": group,
                "category": str(raw.get("category") or category or "general").lower(),
                "description": str(raw.get("description") or ""),
                "tags": ["proposed", "llm"],
                "created_by": "llm",
                "nodes": nodes,
                "rationale": str(raw.get("rationale") or ""),
                "source": "llm",
            }
        )
    return out or None


def _canned_tools(service: str) -> list[dict[str, Any]]:
    """When OpenAPI registry is empty locally, still propose useful gaps."""
    if service == "am-subscription":
        return [
            {"name": "timeLeft", "method": "get", "path": "/subscriptions/time-left"},
            {"name": "entitlements", "method": "get", "path": "/subscriptions/entitlements"},
            {"name": "plansByCode", "method": "get", "path": "/subscriptions/plans/{code}"},
        ]
    if service == "am-identity":
        return [
            {"name": "refresh", "method": "post", "path": "/auth/refresh"},
            {"name": "me", "method": "get", "path": "/auth/me"},
            {"name": "logout", "method": "post", "path": "/auth/logout"},
        ]
    return []


def propose_scenarios(
    *,
    service: str,
    group: str | None = None,
    category: str | None = None,
    env: str = "prod",
    max_scenarios: int = 5,
    gate: str = "prod_safe",
    use_llm: bool = True,
) -> dict[str, Any]:
    svc = (service or "").strip()
    if svc not in _SERVICE_GROUP:
        return {
            "ok": False,
            "error": f"unsupported service {svc!r}; use am-identity or am-subscription",
        }
    grp = (group or _SERVICE_GROUP[svc]).strip().lower()
    max_n = max(1, min(int(max_scenarios or 5), 12))
    tools = _list_tools(svc)
    if not tools:
        tools = _canned_tools(svc)
    proposals: list[dict[str, Any]] = []
    mode = "heuristic"
    if use_llm:
        llm_rows = _llm_proposals(
            service=svc,
            group=grp,
            category=category,
            gate=gate,
            max_scenarios=max_n,
            tools=tools,
        )
        if llm_rows:
            proposals = llm_rows
            mode = "llm"
    if not proposals:
        proposals = _heuristic_proposals(
            service=svc,
            group=grp,
            category=category,
            gate=gate,
            max_scenarios=max_n,
            tools=tools,
        )
        mode = "heuristic"
    return {
        "ok": True,
        "service": svc,
        "group": grp,
        "env": env,
        "mode": mode,
        "proposals": proposals,
        "count": len(proposals),
        "note": "Proposals are not saved. Confirm with qa_flow_upsert / POST /api/flows.",
    }
