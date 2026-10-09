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


def _steps_from_examples(examples: list[dict[str, Any]], *, service: str) -> list[dict[str, Any]]:
    ordered = sorted(
        examples,
        key=lambda e: int(
            ((e.get("meta") or {}) if isinstance(e.get("meta"), dict) else {}).get("flow_step")
            or 0
        ),
    )
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
        node: dict[str, Any] = {
            "id": nid,
            "kind": "call_tool",
            "service": service,
            "method": method,
            "path": path,
            "exact_path": path,
            "label": str(ex.get("name") or nid),
            "auth": True,
        }
        if expect is not None:
            try:
                node["expect_status"] = [int(expect)]
            except (TypeError, ValueError):
                node["expect_status"] = [200]
        # capture map → variables hint (flows runner may ignore unknown keys)
        if isinstance(meta.get("capture"), dict):
            node["capture"] = meta["capture"]
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
) -> dict[str, Any]:
    """Upsert data_gen workflows; prune stale flow_ids for service+profile."""
    groups = collect_cross_flow_groups(examples)
    upserted: list[str] = []
    for flow_id, rows in groups.items():
        fid = flow_doc_id(service, profile, flow_id)
        nodes = _steps_from_examples(rows, service=service)
        if not nodes:
            continue
        doc = {
            "id": fid,
            "title": f"{service} · {flow_id} ({profile})",
            "group": WORKFLOW_GROUP,
            "category": "cross_flow",
            "api_pack": service,
            "description": f"am-specs cross_flow {flow_id}",
            "tags": [WORKFLOW_SOURCE_TAG, f"profile:{profile}", f"flow:{flow_id}", service],
            "env_default": None,
            "payload_set_version": payload_set_version,
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
