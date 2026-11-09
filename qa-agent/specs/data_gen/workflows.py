"""Materialize am-specs cross_flow examples into Specs authored workflows."""
from __future__ import annotations

import re
from typing import Any

from specs.data_gen.constants import WORKFLOW_GROUP, WORKFLOW_SOURCE_TAG
from specs.flows.authored_store import delete_authored, list_authored, upsert_authored

_SAFE = re.compile(r"[^A-Za-z0-9_-]+")


def flow_doc_id(service: str, profile: str, flow_id: str) -> str:
    raw = f"dg_{service}_{profile}_{flow_id}"
    cleaned = _SAFE.sub("_", raw).strip("_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = "f" + cleaned
    return cleaned[:80]


_PROFILE_LABEL = {
    "prod": "default",
    "default": "default",
    "working": "default",
    "full": "full",
    "premium": "premium",
}


def _humanize_flow_id(flow_id: str) -> str:
    parts = [p for p in str(flow_id or "").replace("-", "_").split("_") if p]
    if not parts:
        return str(flow_id or "")

    def _words(xs: list[str]) -> str:
        return " ".join(x.capitalize() for x in xs if x)

    if "to" in parts:
        i = parts.index("to")
        left = _words(parts[:i])
        right = _words(parts[i + 1 :])
        if left and right:
            return f"{left} → {right}"
        return left or right or str(flow_id)
    return _words(parts)


def _modules_for_flow(flow_id: str, rows: list[dict[str, Any]]) -> list[str]:
    mods: list[str] = []
    for ex in rows:
        meta = ex.get("meta") if isinstance(ex.get("meta"), dict) else {}
        raw = meta.get("modules") or meta.get("module")
        if isinstance(raw, list):
            mods.extend(str(m).strip() for m in raw if str(m).strip())
        elif isinstance(raw, str) and raw.strip():
            mods.append(raw.strip())
    if mods:
        # preserve order, unique
        seen: set[str] = set()
        out: list[str] = []
        for m in mods:
            if m not in seen:
                seen.add(m)
                out.append(m)
        return out
    # Heuristic from flow_id tokens
    fid = str(flow_id or "").lower()
    guesses = []
    for token, mod in (
        ("watchlist", "watchlist"),
        ("index", "market_index"),
        ("ipo", "ipo"),
        ("mf_", "mutual_fund"),
        ("mutual", "mutual_fund"),
        ("fundamental", "fundamentals"),
        ("search", "instrument"),
        ("securit", "securities"),
        ("ltp", "market_data"),
        ("quote", "market_data"),
    ):
        if token in fid and mod not in guesses:
            guesses.append(mod)
    return guesses


def _api_id_from_request(method: str, path: str) -> str:
    m = (method or "get").lower()
    p = (path or "").strip("/")
    raw = f"{m}_{p}".replace("/", "_").replace("{", "").replace("}", "").replace("-", "_")
    cleaned = _SAFE.sub("_", raw).strip("_").lower()
    return cleaned[:80] or "api"


def _template_bind_map(raw: dict[str, Any] | None) -> dict[str, str]:
    """Keep only values that are ``{{var}}`` templates for bind_* synthesis."""
    out: dict[str, str] = {}
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        if isinstance(v, str) and "{{" in v and "}}" in v:
            out[str(k)] = v
    return out


def _subst_templates(value: Any, variables: dict[str, str]) -> Any:
    """Lightweight ``{{var}}`` replace (avoid importing flow runner)."""
    if isinstance(value, str):
        out = value
        for k, v in variables.items():
            out = out.replace("{{" + str(k) + "}}", str(v))
        return out
    if isinstance(value, dict):
        return {str(k): _subst_templates(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [_subst_templates(v, variables) for v in value]
    return value


def _steps_from_examples(
    examples: list[dict[str, Any]],
    *,
    service: str,
    variables: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    ordered = sorted(
        examples,
        key=lambda e: int(
            ((e.get("meta") or {}) if isinstance(e.get("meta"), dict) else {}).get("flow_step")
            or 0
        ),
    )
    vars_ = dict(variables or {})
    nodes: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for i, ex in enumerate(ordered):
        meta = ex.get("meta") if isinstance(ex.get("meta"), dict) else {}
        req = ex.get("request") if isinstance(ex.get("request"), dict) else {}
        method = str(req.get("method") or ex.get("method") or "GET").lower()
        path = str(req.get("path") or ex.get("path") or "")
        nid = str(meta.get("variant_id") or f"step{i+1}")
        nid = _SAFE.sub("_", nid).strip("_") or f"step{i+1}"
        if not nid[0].isalpha():
            nid = "s" + nid
        nid = nid[:80]
        if nid in seen_ids:
            nid = f"{nid[:70]}_{i+1}"
        seen_ids.add(nid)
        expect = meta.get("expect_status")
        if expect is None and isinstance(ex.get("response"), dict):
            expect = ex["response"].get("status")
        api_id = str(meta.get("api_id") or "").strip() or _api_id_from_request(method, path)
        node: dict[str, Any] = {
            "id": nid,
            "kind": "call_tool",
            "service": service,
            "method": method,
            "path": path,
            "exact_path": path,
            "label": str(ex.get("name") or nid),
            "auth": True,
            "payload_api_id": api_id,
            "payload_name": str(meta.get("payload_name") or meta.get("name") or "must_work"),
        }
        # Seed body/query from the example so runs work even before payload merge.
        body = req.get("body")
        if isinstance(body, dict) and body:
            # Live Jackson rejects unknown InstrumentSearchCriteria.symbols
            # (use queries / tradingSymbols only).
            if "instruments/search" in path and isinstance(body, dict):
                body = {k: v for k, v in body.items() if k != "symbols"}
            node["body_override"] = _subst_templates(body, vars_) if vars_ else body
        query = req.get("query")
        if isinstance(query, dict) and query:
            node["query_override"] = _subst_templates(query, vars_) if vars_ else query
        path_params = req.get("path_params")
        if isinstance(path_params, dict) and path_params:
            node["path_params"] = path_params
        if expect is not None:
            try:
                node["expect_status"] = [int(expect)]
            except (TypeError, ValueError):
                node["expect_status"] = [200]
        if isinstance(meta.get("capture"), dict):
            node["capture"] = meta["capture"]
        # search → fundamentals: live hits use snake_case trading_symbol
        if (
            "instruments/search" in path
            and not node.get("capture")
            and "search" in str(meta.get("flow_id") or "").lower()
        ):
            node["capture"] = {
                "symbol": "$[0].trading_symbol",
                "symbols": "$[0].trading_symbol",
            }
        # bind_* may live on meta (from am-specs expand) or already be in request.
        bind_query = meta.get("bind_query") if isinstance(meta.get("bind_query"), dict) else None
        bind_path = meta.get("bind_path") if isinstance(meta.get("bind_path"), dict) else None
        # Synthesize from templated path_params / query when packs omit bind_*.
        if not bind_path:
            synth_path = _template_bind_map(
                path_params if isinstance(path_params, dict) else None
            )
            if synth_path:
                bind_path = synth_path
        if not bind_query:
            synth_q = _template_bind_map(query if isinstance(query, dict) else None)
            if synth_q:
                bind_query = synth_q
        if bind_query:
            node["bind_query"] = bind_query
        if bind_path:
            node["bind_path"] = bind_path
        nodes.append(node)
    return nodes


def collect_cross_flow_groups(
    examples: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for ex in examples:
        if not isinstance(ex, dict):
            continue
        meta = ex.get("meta") if isinstance(ex.get("meta"), dict) else {}
        ck = str(meta.get("case_kind") or "").lower()
        if ck != "cross_flow":
            continue
        fid = str(meta.get("flow_id") or "unnamed").strip() or "unnamed"
        groups.setdefault(fid, []).append(ex)
    return groups


def sync_cross_flow_workflows(
    *,
    service: str,
    profile: str,
    examples: list[dict[str, Any]],
    payload_set_version: int | None = None,
    prune: bool = True,
    environment: str = "dev",
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Upsert data_gen workflows; prune stale flow_ids for service+profile."""
    groups = collect_cross_flow_groups(examples)
    upserted: list[str] = []
    profile_key = str(profile or "prod").strip().lower() or "prod"
    profile_label = _PROFILE_LABEL.get(profile_key, profile_key)
    flow_vars: dict[str, str] = {
        str(k): "" if v is None else str(v)
        for k, v in (variables or {}).items()
        if not str(k).startswith("_")
    }
    if not flow_vars:
        try:
            from specs.data_gen.pack import load_var_defaults

            flow_vars = load_var_defaults(service, environment or "dev")
        except Exception:  # noqa: BLE001
            flow_vars = {}
    for flow_id, rows in groups.items():
        fid = flow_doc_id(service, profile, flow_id)
        nodes = _steps_from_examples(rows, service=service, variables=flow_vars)
        if not nodes:
            continue
        modules = _modules_for_flow(flow_id, rows)
        human = _humanize_flow_id(flow_id)
        svc_short = service.replace("am-", "") if service.startswith("am-") else service
        tags = [
            WORKFLOW_SOURCE_TAG,
            f"profile:{profile_key}",
            f"profile:{profile_label}",
            f"flow:{flow_id}",
            service,
            *[f"module:{m}" for m in modules],
        ]
        doc = {
            "id": fid,
            "title": f"{human} · {profile_label}",
            "group": WORKFLOW_GROUP,
            "category": "cross_flow",
            "api_pack": service,
            "description": f"{svc_short} cross_flow {flow_id} ({profile_label})",
            "tags": tags,
            "env_default": environment or "dev",
            "payload_set_version": payload_set_version,
            "variables": dict(flow_vars),
            "nodes": nodes,
            "created_by": "authored",
        }
        upsert_authored(doc, flow_id=fid)
        upserted.append(fid)

    pruned: list[str] = []
    if prune:
        prefix_tag_profile = f"profile:{profile}"
        for row in list_authored():
            tags = [str(t) for t in (row.get("tags") or [])]
            if WORKFLOW_SOURCE_TAG not in tags:
                continue
            if str(row.get("api_pack") or "") != service and service not in tags:
                continue
            if prefix_tag_profile not in tags:
                continue
            rid = str(row.get("id") or "")
            if rid and rid not in upserted:
                if delete_authored(rid):
                    pruned.append(rid)

    return {
        "ok": True,
        "service": service,
        "profile": profile,
        "group": WORKFLOW_GROUP,
        "upserted": upserted,
        "pruned": pruned,
        "flow_ids": sorted(groups.keys()),
        "count": len(upserted),
    }


def list_data_gen_workflows(
    *,
    service: str | None = None,
    profile: str | None = None,
    flow_id: str | None = None,
) -> list[dict[str, Any]]:
    from specs.flows.runtime import suite_preview

    preview = suite_preview(group=WORKFLOW_GROUP)
    rows = list(preview.get("flows") or [])
    if service:
        svc = service.strip().lower()
        rows = [
            r
            for r in rows
            if str(r.get("api_pack") or "").lower() == svc
            or svc in [str(t).lower() for t in (r.get("tags") or [])]
            or svc in [str(s).lower() for s in (r.get("services") or [])]
        ]
    if profile:
        tag = f"profile:{profile.strip().lower()}"
        rows = [r for r in rows if tag in [str(t).lower() for t in (r.get("tags") or [])]]
    if flow_id:
        want = f"flow:{flow_id.strip().lower()}"
        rows = [
            r
            for r in rows
            if want in [str(t).lower() for t in (r.get("tags") or [])]
            or flow_id.lower() in str(r.get("id") or "").lower()
        ]
    return rows
