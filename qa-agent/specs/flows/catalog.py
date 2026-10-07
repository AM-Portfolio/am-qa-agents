"""Load builtin FLOW_* from plugin catalogs + authored flows."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from specs.flows.authored_store import get_authored, list_authored


def _plugins_root() -> Path:
    return Path(__file__).resolve().parents[2] / "plugins"


def _step_to_node(step: dict[str, Any]) -> dict[str, Any]:
    sid = str(step.get("id") or "").strip()
    expect = step.get("expect_status")
    if isinstance(expect, int):
        expect = [expect]
    elif not isinstance(expect, list):
        expect = None
    return {
        "id": sid,
        "kind": str(step.get("kind") or "call_tool"),
        "service": str(step.get("service") or "").strip(),
        "method": str(step.get("method") or "get").lower(),
        "path": step.get("path"),
        "path_contains": step.get("path_contains"),
        "exact_path": step.get("exact_path"),
        "tool_match": step.get("tool_match"),
        "auth": bool(step.get("auth")),
        "optional": bool(step.get("optional") or step.get("optional_service")),
        "capture_tokens": bool(step.get("capture_tokens")),
        "uses_spt_auth_creds": bool(step.get("uses_spt_auth_creds")),
        "credential_id": step.get("credential_id"),
        "base_url_override": step.get("base_url_override"),
        "body_override": step.get("body_override"),
        "expect_status": expect,
        "label": step.get("label") or step.get("title") or sid,
        "note": step.get("note"),
    }


def _default_group(api_pack: str) -> str:
    p = (api_pack or "").strip().lower()
    if p.startswith("am-"):
        p = p[3:]
    return p or "other"


def _flow_from_yaml(flow: dict[str, Any], *, plugin_id: str, api_pack: str) -> dict[str, Any]:
    fid = str(flow.get("id") or "").strip()
    steps = [s for s in (flow.get("steps") or []) if isinstance(s, dict)]
    nodes = [_step_to_node(s) for s in steps]
    edges: list[dict[str, Any]] = []
    for i in range(len(nodes) - 1):
        edges.append(
            {
                "from": nodes[i]["id"],
                "to": nodes[i + 1]["id"],
                "optional": bool(nodes[i + 1].get("optional")),
            }
        )
    group = str(flow.get("group") or _default_group(api_pack)).strip().lower()
    category = str(flow.get("category") or "general").strip().lower()
    tags = flow.get("tags") if isinstance(flow.get("tags"), list) else []
    return {
        "id": fid,
        "title": str(flow.get("title") or fid),
        "gate": str(flow.get("gate") or "prod_safe"),
        "source": "builtin",
        "created_by": str(flow.get("created_by") or "builtin"),
        "plugin_id": plugin_id,
        "api_pack": api_pack,
        "group": group,
        "category": category,
        "description": str(flow.get("description") or ""),
        "tags": [str(t) for t in tags],
        "in_pack": bool(flow.get("in_pack")),
        "credential_id": flow.get("credential_id"),
        "env_default": flow.get("env_default"),
        "nodes": nodes,
        "edges": edges,
    }


def _load_builtin_flows() -> list[dict[str, Any]]:
    root = _plugins_root()
    if not root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for plugin_dir in sorted(root.iterdir()):
        if not plugin_dir.is_dir():
            continue
        manifest_path = plugin_dir / "plugin.yaml"
        apis_path = plugin_dir / "catalog" / "apis.yaml"
        if not apis_path.is_file():
            continue
        plugin_id = plugin_dir.name
        api_pack = plugin_id
        if manifest_path.is_file():
            try:
                man = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
                api_pack = str(man.get("api_pack") or plugin_id)
                plugin_id = str(man.get("id") or plugin_id)
            except Exception:  # noqa: BLE001
                pass
        try:
            raw = yaml.safe_load(apis_path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            continue
        for flow in raw.get("flows") or []:
            if not isinstance(flow, dict) or not flow.get("id"):
                continue
            out.append(
                _flow_from_yaml(flow, plugin_id=plugin_id, api_pack=api_pack)
            )
    return out


def _pack_document(api_pack: str, flows: list[dict[str, Any]]) -> dict[str, Any] | None:
    pack_flows = [f for f in flows if f.get("api_pack") == api_pack and f.get("source") == "builtin"]
    if not pack_flows:
        return None
    marked = [f for f in pack_flows if f.get("in_pack")]
    if marked:
        pack_flows = marked
    # Prefer LOGIN then main flow order by id heuristics
    pack_flows_sorted = sorted(
        pack_flows,
        key=lambda f: (0 if "LOGIN" in str(f.get("id") or "").upper() else 1, f.get("id")),
    )
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    prev_last: str | None = None
    for flow in pack_flows_sorted:
        fnodes = list(flow.get("nodes") or [])
        # Prefix node ids with flow id to avoid collisions across flows
        id_map: dict[str, str] = {}
        for n in fnodes:
            old = n["id"]
            new = f"{flow['id']}::{old}"
            id_map[old] = new
            nn = dict(n)
            nn["id"] = new
            nn["flow_id"] = flow["id"]
            nodes.append(nn)
        for e in flow.get("edges") or []:
            edges.append(
                {
                    "from": id_map.get(e["from"], e["from"]),
                    "to": id_map.get(e["to"], e["to"]),
                    "optional": bool(e.get("optional")),
                }
            )
        if prev_last and fnodes:
            first_old = fnodes[0]["id"]
            edges.append(
                {
                    "from": prev_last,
                    "to": id_map[first_old],
                    "optional": False,
                    "pack_join": True,
                }
            )
        if fnodes:
            last_old = fnodes[-1]["id"]
            prev_last = id_map[last_old]
    group = _default_group(api_pack)
    return {
        "id": f"pack:{api_pack}",
        "title": f"API pack · {api_pack}",
        "gate": "prod_safe",
        "source": "pack",
        "created_by": "builtin",
        "api_pack": api_pack,
        "group": group,
        "category": "pack",
        "description": f"Joined pack for {api_pack} (in_pack members only).",
        "tags": ["pack"],
        "plugin_id": pack_flows_sorted[0].get("plugin_id"),
        "credential_id": None,
        "nodes": nodes,
        "edges": edges,
        "member_flows": [f["id"] for f in pack_flows_sorted],
    }


def _summary_row(f: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f["id"],
        "title": f.get("title") or f["id"],
        "gate": f.get("gate"),
        "source": f.get("source"),
        "created_by": f.get("created_by") or f.get("source"),
        "api_pack": f.get("api_pack"),
        "plugin_id": f.get("plugin_id"),
        "group": f.get("group") or "other",
        "category": f.get("category") or "general",
        "description": f.get("description") or "",
        "tags": list(f.get("tags") or []),
        "credential_id": f.get("credential_id"),
        "env_default": f.get("env_default"),
        "node_count": len(f.get("nodes") or []),
        "member_flows": f.get("member_flows"),
        "services": sorted(
            {
                str(n.get("service"))
                for n in (f.get("nodes") or [])
                if n.get("service")
            }
        ),
    }


def list_flows(
    *,
    group: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    builtin = _load_builtin_flows()
    authored = list_authored()
    packs: dict[str, list[dict[str, Any]]] = {}
    for f in builtin:
        packs.setdefault(str(f.get("api_pack") or "unknown"), []).append(f)
    summaries: list[dict[str, Any]] = []
    for f in builtin:
        summaries.append(_summary_row(f))
    for pack_id in sorted(packs):
        doc = _pack_document(pack_id, builtin)
        if doc:
            summaries.append(_summary_row(doc))
    for f in authored:
        row = _summary_row({**f, "source": "authored"})
        summaries.append(row)
    g = (group or "").strip().lower() or None
    c = (category or "").strip().lower() or None
    if g:
        summaries = [r for r in summaries if str(r.get("group") or "").lower() == g]
    if c:
        summaries = [r for r in summaries if str(r.get("category") or "").lower() == c]
    return summaries


def get_flow(flow_id: str) -> dict[str, Any] | None:
    fid = (flow_id or "").strip()
    if not fid:
        return None
    if fid.startswith("pack:"):
        pack = fid.split(":", 1)[1]
        return _pack_document(pack, _load_builtin_flows())
    authored = get_authored(fid)
    if authored:
        return authored
    for f in _load_builtin_flows():
        if f.get("id") == fid:
            return f
    return None
