"""User/MCP-authored flow documents (JSON under data_dir)."""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any

from specs.config import settings

_LOCK = threading.Lock()
_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,79}$")


class AuthoredFlowError(ValueError):
    pass


def _path() -> Path:
    return Path(settings.data_dir) / "qa_authored_flows.json"


def _empty() -> dict[str, Any]:
    return {"version": 1, "flows": {}}


def _load() -> dict[str, Any]:
    path = _path()
    if not path.is_file():
        return _empty()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty()
    if not isinstance(raw, dict):
        return _empty()
    flows = raw.get("flows")
    if not isinstance(flows, dict):
        flows = {}
    return {"version": int(raw.get("version") or 1), "flows": flows}


def _save(data: dict[str, Any]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    with _LOCK:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)


def validate_flow_id(fid: str) -> str:
    s = (fid or "").strip()
    if not _ID_RE.match(s):
        raise AuthoredFlowError(f"Invalid flow id {fid!r}")
    return s


def _normalize_doc(doc: dict[str, Any], *, fid: str) -> dict[str, Any]:
    nodes_in = doc.get("nodes")
    if not isinstance(nodes_in, list) or not nodes_in:
        raise AuthoredFlowError("nodes required (non-empty list)")
    nodes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in nodes_in:
        if not isinstance(raw, dict):
            continue
        nid = str(raw.get("id") or "").strip()
        if not nid or nid in seen:
            raise AuthoredFlowError(f"duplicate or empty node id {nid!r}")
        seen.add(nid)
        expect = raw.get("expect_status")
        if isinstance(expect, int):
            expect = [expect]
        elif not isinstance(expect, list):
            expect = None
        nodes.append(
            {
                "id": nid,
                "kind": str(raw.get("kind") or "call_tool"),
                "service": str(raw.get("service") or "").strip(),
                "method": str(raw.get("method") or "get").lower(),
                "path": raw.get("path"),
                "path_contains": raw.get("path_contains"),
                "exact_path": raw.get("exact_path"),
                "tool_match": raw.get("tool_match"),
                "auth": bool(raw.get("auth")),
                "optional": bool(
                    raw.get("optional") or raw.get("optional_service")
                ),
                "capture_tokens": bool(raw.get("capture_tokens")),
                "uses_spt_auth_creds": bool(raw.get("uses_spt_auth_creds")),
                "credential_id": (raw.get("credential_id") or None),
                "base_url_override": raw.get("base_url_override"),
                "body_override": raw.get("body_override"),
                "expect_status": expect,
                "label": raw.get("label") or nid,
            }
        )
    edges_in = doc.get("edges")
    edges: list[dict[str, Any]] = []
    if isinstance(edges_in, list) and edges_in:
        for e in edges_in:
            if not isinstance(e, dict):
                continue
            frm = str(e.get("from") or e.get("source") or "").strip()
            to = str(e.get("to") or e.get("target") or "").strip()
            if frm not in seen or to not in seen:
                raise AuthoredFlowError(f"edge references unknown node {frm!r}->{to!r}")
            edges.append(
                {"from": frm, "to": to, "optional": bool(e.get("optional"))}
            )
    else:
        for i in range(len(nodes) - 1):
            edges.append(
                {
                    "from": nodes[i]["id"],
                    "to": nodes[i + 1]["id"],
                    "optional": bool(nodes[i + 1].get("optional")),
                }
            )
    tags = doc.get("tags") if isinstance(doc.get("tags"), list) else []
    created_by = str(doc.get("created_by") or "authored").strip().lower()
    if created_by not in {"authored", "llm"}:
        created_by = "authored"
    variables_in = doc.get("variables")
    variables: dict[str, Any] = {}
    if isinstance(variables_in, dict):
        variables = {str(k): v for k, v in variables_in.items() if str(k).strip()}
    pin = doc.get("payload_set_version")
    if pin is not None:
        try:
            pin = int(pin)
        except (TypeError, ValueError):
            pin = None
    return {
        "id": fid,
        "title": str(doc.get("title") or fid),
        "gate": str(doc.get("gate") or "prod_safe"),
        "source": "authored",
        "created_by": created_by,
        "group": str(doc.get("group") or "other").strip().lower(),
        "category": str(doc.get("category") or "general").strip().lower(),
        "description": str(doc.get("description") or ""),
        "tags": [str(t) for t in tags],
        "env_default": doc.get("env_default"),
        "credential_id": doc.get("credential_id"),
        "api_pack": doc.get("api_pack"),
        "variables": variables,
        "payload_set_version": pin,
        "nodes": nodes,
        "edges": edges,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def list_authored() -> list[dict[str, Any]]:
    data = _load()
    return [dict(v) for v in (data.get("flows") or {}).values() if isinstance(v, dict)]


def get_authored(fid: str) -> dict[str, Any] | None:
    data = _load()
    rec = (data.get("flows") or {}).get(fid)
    return dict(rec) if isinstance(rec, dict) else None


def upsert_authored(doc: dict[str, Any], *, flow_id: str | None = None) -> dict[str, Any]:
    fid = validate_flow_id(flow_id or str(doc.get("id") or ""))
    normalized = _normalize_doc(doc, fid=fid)
    data = _load()
    flows = dict(data.get("flows") or {})
    flows[fid] = normalized
    data["flows"] = flows
    _save(data)
    return normalized


def delete_authored(fid: str) -> bool:
    data = _load()
    flows = dict(data.get("flows") or {})
    if fid not in flows:
        return False
    del flows[fid]
    data["flows"] = flows
    _save(data)
    return True
