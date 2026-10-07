"""Build portal/MCP graph payload from a flow document."""
from __future__ import annotations

from typing import Any

from specs.flows.catalog import get_flow

MANUAL_TRIGGER_ID = "__manual_trigger__"


def build_graph(flow_id: str) -> dict[str, Any] | None:
    doc = get_flow(flow_id)
    if not doc:
        return None

    raw_nodes = list(doc.get("nodes") or [])
    nodes_out: list[dict[str, Any]] = [
        {
            "id": MANUAL_TRIGGER_ID,
            "label": "Manual Trigger",
            "kind": "manual_trigger",
            "service": "",
            "method": "START",
            "path": "click to run",
            "optional": False,
            "auth": False,
            "capture_tokens": False,
            "credential_id": None,
            "flow_id": None,
            "order": 0,
            "x": 40,
            "y": 160,
        }
    ]
    for i, n in enumerate(raw_nodes):
        path_hint = (
            n.get("exact_path")
            or n.get("path")
            or n.get("path_contains")
            or (n.get("tool_match") and f"tool:{n.get('tool_match')}")
            or ""
        )
        step_label = n.get("label") or n["id"]
        if "::" in str(n["id"]) and (
            not n.get("label") or n.get("label") == n["id"]
        ):
            step_label = str(n["id"]).split("::")[-1]
        nodes_out.append(
            {
                "id": n["id"],
                "label": step_label,
                "kind": n.get("kind") or "call_tool",
                "service": n.get("service"),
                "method": (n.get("method") or "get").upper(),
                "path": path_hint,
                "optional": bool(n.get("optional")),
                "auth": bool(n.get("auth") or n.get("uses_spt_auth_creds")),
                "capture_tokens": bool(n.get("capture_tokens")),
                "credential_id": n.get("credential_id"),
                "flow_id": n.get("flow_id"),
                "order": i + 1,
                "x": 40 + (i + 1) * 280,
                "y": 160 + (40 if i % 2 else 0),
            }
        )

    edges_out: list[dict[str, Any]] = []
    if raw_nodes:
        first_id = raw_nodes[0]["id"]
        edges_out.append(
            {
                "id": f"{MANUAL_TRIGGER_ID}->{first_id}",
                "from": MANUAL_TRIGGER_ID,
                "to": first_id,
                "optional": False,
                "pack_join": False,
                "trigger": True,
            }
        )
    for e in doc.get("edges") or []:
        edges_out.append(
            {
                "id": f"{e['from']}->{e['to']}",
                "from": e["from"],
                "to": e["to"],
                "optional": bool(e.get("optional")),
                "pack_join": bool(e.get("pack_join")),
            }
        )
    return {
        "id": doc.get("id"),
        "title": doc.get("title"),
        "source": doc.get("source"),
        "api_pack": doc.get("api_pack"),
        "credential_id": doc.get("credential_id"),
        "nodes": nodes_out,
        "edges": edges_out,
    }
