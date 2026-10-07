"""Builtin + pack flow catalog and graph builder."""
from __future__ import annotations

from specs.flows.catalog import get_flow, list_flows
from specs.flows.graph import build_graph


def test_list_flows_includes_subscription_builtin_and_pack():
    rows = list_flows()
    ids = {r["id"] for r in rows}
    assert "FLOW_SUBSCRIPTION" in ids
    assert "FLOW_SUBSCRIPTION_LOGIN" in ids
    assert "FLOW_SUBSCRIPTION_PLANS" in ids
    assert "FLOW_IDENTITY_LOGIN" in ids
    assert "pack:subscription" in ids or any(
        str(r.get("id") or "").startswith("pack:") for r in rows
    )
    sub = next(r for r in rows if r["id"] == "FLOW_SUBSCRIPTION_LOGIN")
    assert sub.get("group") == "subscription"
    assert sub.get("category") == "auth"
    filtered = list_flows(group="identity", category="negative")
    assert filtered
    assert all(r["group"] == "identity" for r in filtered)


def test_pack_subscription_only_in_pack_members():
    doc = get_flow("pack:subscription")
    assert doc is not None
    members = set(doc.get("member_flows") or [])
    assert "FLOW_SUBSCRIPTION_LOGIN" in members
    assert "FLOW_SUBSCRIPTION" in members
    assert "FLOW_SUBSCRIPTION_PLANS" not in members


def test_pack_join_edges_link_login_then_main():
    doc = get_flow("pack:subscription")
    assert doc is not None
    assert doc["source"] == "pack"
    node_ids = [n["id"] for n in doc["nodes"]]
    assert any("LOGIN" in nid for nid in node_ids)
    joins = [e for e in doc["edges"] if e.get("pack_join")]
    assert joins, "pack should join LOGIN flow into main flow"
    for e in joins:
        assert e["from"] in node_ids
        assert e["to"] in node_ids


def test_graph_layout_hints():
    g = build_graph("FLOW_SUBSCRIPTION")
    assert g is not None
    assert g["nodes"]
    assert g["nodes"][0]["kind"] == "manual_trigger"
    assert g["nodes"][0]["id"] == "__manual_trigger__"
    assert "x" in g["nodes"][0]
    assert any(e.get("trigger") for e in g["edges"])
    assert g["edges"] or len(g["nodes"]) == 1
