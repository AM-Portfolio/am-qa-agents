"""Flow runtime: variables, Specs payload version, suite preview/execute helpers."""
from __future__ import annotations

from typing import Any

from specs.flows.authored_store import AuthoredFlowError, get_authored, upsert_authored
from specs.flows.catalog import get_flow, list_flows
from specs.flows.runner import start_execution


def primary_payload_service(flow: dict[str, Any]) -> str | None:
    """Best-effort Specs service key for payload sets (am-identity / am-subscription)."""
    api_pack = str(flow.get("api_pack") or "").strip().lower()
    group = str(flow.get("group") or "").strip().lower()
    if api_pack in {"identity", "subscription"}:
        return f"am-{api_pack}"
    if group in {"identity", "subscription"}:
        return f"am-{group}"
    for n in flow.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        svc = str(n.get("service") or "").strip()
        if svc.startswith("am-"):
            return svc
    return None


def get_runtime(flow_id: str) -> dict[str, Any] | None:
    from specs.payloads.payload_store import list_payload_sets

    doc = get_flow(flow_id)
    if not doc:
        return None
    svc = primary_payload_service(doc)
    payload_sets: list[dict[str, Any]] = []
    active_version = None
    if svc:
        try:
            ps = list_payload_sets(svc)
            payload_sets = list(ps.get("sets") or [])
            active_version = ps.get("active_version")
        except Exception:  # noqa: BLE001
            payload_sets = []
    pinned = doc.get("payload_set_version")
    selected = pinned if pinned is not None else active_version
    variables = doc.get("variables") if isinstance(doc.get("variables"), dict) else {}
    return {
        "flow_id": flow_id,
        "title": doc.get("title"),
        "group": doc.get("group"),
        "category": doc.get("category"),
        "env_default": doc.get("env_default") or "prod",
        "credential_id": doc.get("credential_id"),
        "variables": {str(k): v for k, v in variables.items()},
        "payload_service": svc,
        "payload_sets": payload_sets,
        "active_version": active_version,
        "selected_version": selected,
        "payload_set_version": pinned,
        "source": doc.get("source"),
    }


def set_variables(
    flow_id: str,
    variables: dict[str, Any],
    *,
    payload_set_version: int | None = None,
    clear_payload_pin: bool = False,
) -> dict[str, Any]:
    """Persist variables on authored flows; builtins get an authored overlay clone."""
    fid = (flow_id or "").strip()
    existing = get_authored(fid)
    base = existing or get_flow(fid)
    if not base:
        raise AuthoredFlowError(f"flow not found: {fid}")
    # Authored store rejects pack: ids — only allow letter-start ids
    if fid.startswith("pack:"):
        raise AuthoredFlowError("cannot store variables on pack flows; use suite execute body")
    clean = {str(k): v for k, v in (variables or {}).items() if str(k).strip()}
    doc = dict(base)
    doc["id"] = fid
    doc["variables"] = clean
    if clear_payload_pin:
        doc["payload_set_version"] = None
    elif payload_set_version is not None:
        doc["payload_set_version"] = int(payload_set_version)
    elif "payload_set_version" in base:
        doc["payload_set_version"] = base.get("payload_set_version")
    # Ensure nodes for normalize
    if not doc.get("nodes"):
        raise AuthoredFlowError("nodes required")
    # Builtin ids like FLOW_* are valid authored ids
    saved = upsert_authored(doc, flow_id=fid)
    return get_runtime(fid) or {"flow": saved}


def set_payload_version(
    *,
    flow_id: str | None = None,
    service: str | None = None,
    version: int,
    activate: bool = True,
    pin_on_flow: bool = True,
) -> dict[str, Any]:
    from specs.payloads.payload_store import set_active_payload_set

    svc = (service or "").strip()
    fid = (flow_id or "").strip() or None
    if not svc and fid:
        rt = get_runtime(fid)
        if not rt:
            raise ValueError(f"flow not found: {fid}")
        svc = str(rt.get("payload_service") or "")
    if not svc:
        raise ValueError("service or flow_id with resolvable payload_service required")
    activated = None
    if activate:
        activated = set_active_payload_set(svc, int(version))
    pinned = None
    if pin_on_flow and fid and not fid.startswith("pack:"):
        try:
            rt = get_runtime(fid) or {}
            pinned = set_variables(
                fid,
                dict(rt.get("variables") or {}),
                payload_set_version=int(version),
            )
        except AuthoredFlowError:
            pinned = None
    return {
        "ok": True,
        "service": svc,
        "version": int(version),
        "activate": activate,
        "activated": activated,
        "runtime": pinned or (get_runtime(fid) if fid else None),
    }


def suite_preview(
    *,
    group: str | None = None,
    api_pack: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    g = (group or "").strip().lower() or None
    pack = (api_pack or "").strip().lower() or None
    cat = (category or "").strip().lower() or None
    rows = list_flows(group=g, category=cat)
    if pack:
        rows = [
            r
            for r in rows
            if str(r.get("api_pack") or "").lower() == pack
            or str(r.get("id") or "") == f"pack:{pack}"
        ]
    # Prefer concrete flows over packs when listing a group suite
    if g and not pack:
        rows = [r for r in rows if r.get("source") != "pack"]
    return {
        "ok": True,
        "group": g,
        "api_pack": pack,
        "category": cat,
        "flows": rows,
        "count": len(rows),
    }


def suite_execute(
    *,
    flow_ids: list[str],
    env: str = "prod",
    credential_id: str | None = None,
    payload_set_version: int | None = None,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import uuid

    ids = [str(x).strip() for x in (flow_ids or []) if str(x).strip()]
    if not ids:
        raise ValueError("flow_ids required")
    suite_run_id = uuid.uuid4().hex
    execution_ids: list[str] = []
    started: list[dict[str, Any]] = []
    for fid in ids:
        out = start_execution(
            fid,
            env=env,
            credential_id=credential_id,
            variables=variables,
            payload_set_version=payload_set_version,
            suite_run_id=suite_run_id,
        )
        execution_ids.append(str(out.get("execution_id")))
        started.append(out)
    return {
        "ok": True,
        "suite_run_id": suite_run_id,
        "execution_ids": execution_ids,
        "executions": started,
        "count": len(execution_ids),
    }
