"""HTTP + MCP surface for flows/credentials (in-process)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_CREDENTIALS_KEY", "test-api-key")
    monkeypatch.setenv("SPT_STORE", "json")
    # Import after env so settings pick up paths where possible
    from specs.config import settings

    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "spt_store", "json")
    monkeypatch.setattr(settings, "spt_acl_required", False)

    from specs.main import app

    with TestClient(app) as c:
        yield c


def test_credentials_and_flows_http(client: TestClient):
    r = client.post(
        "/api/credentials",
        json={
            "id": "cred_dogfood",
            "name": "dogfood",
            "kind": "identity_login",
            "env": "prod",
            "username": "u@example.com",
            "password": "secret",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["has_secret"] is True
    assert "password" not in r.json()

    listed = client.get("/api/credentials")
    assert listed.status_code == 200
    assert listed.json()["count"] >= 1

    flows = client.get("/api/flows")
    assert flows.status_code == 200
    ids = {f["id"] for f in flows.json()["flows"]}
    assert "FLOW_SUBSCRIPTION" in ids

    g = client.get("/api/flows/pack%3Asubscription/graph")
    assert g.status_code == 200
    body = g.json()
    assert body["nodes"]
    assert any(e.get("pack_join") for e in body["edges"])


def test_credential_probe_endpoints(client: TestClient):
    created = client.post(
        "/api/credentials",
        json={
            "id": "cred_probe_cliq",
            "name": "cliq probe",
            "kind": "cliq_webhook",
            "env": "dev",
            "app_id": "resource-cliq",
            "token": "https://example.invalid/cliq/hook",
        },
    )
    assert created.status_code == 200, created.text

    one = client.post("/api/credentials/cred_probe_cliq/probe")
    assert one.status_code == 200, one.text
    body = one.json()
    assert body["id"] == "cred_probe_cliq"
    assert "status" in body
    assert "ok" in body

    missing = client.post("/api/credentials/does-not-exist/probe")
    assert missing.status_code == 404

    all_r = client.post("/api/credentials/probe-all")
    assert all_r.status_code == 200, all_r.text
    payload = all_r.json()
    assert payload["count"] >= 1
    assert any(r.get("id") == "cred_probe_cliq" for r in payload["results"])


def test_mcp_flow_tools_importable():
    from specs.mcp.control import (
        qa_credential_list,
        qa_flow_graph,
        qa_flow_list,
        qa_flow_runtime_get,
        qa_flow_suite_preview,
        qa_flow_variables_set,
    )

    assert callable(qa_flow_list)
    assert callable(qa_flow_graph)
    assert callable(qa_credential_list)
    assert callable(qa_flow_runtime_get)
    assert callable(qa_flow_variables_set)
    assert callable(qa_flow_suite_preview)


def test_flow_node_quick_test_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_CREDENTIALS_KEY", "test-api-key")
    monkeypatch.setenv("SPT_STORE", "json")
    from specs.config import settings

    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "spt_store", "json")

    from specs.flows.catalog import get_flow
    from specs.flows.runner import quick_test_node

    # Prefer pack (has login) — single FLOW_SUBSCRIPTION may be plans-only
    doc = get_flow("pack:subscription") or get_flow("FLOW_SUBSCRIPTION")
    assert doc is not None
    flow_id = str(doc["id"])
    target = None
    for n in doc.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        sid = str(n.get("id") or "").lower()
        if "login" in sid or n.get("uses_spt_auth_creds") or n.get("capture_tokens"):
            target = n
            break
    if target is None:
        target = next(
            (n for n in (doc.get("nodes") or []) if isinstance(n, dict)),
            None,
        )
    assert target is not None
    monkeypatch.setenv("SPT_AUTH_USERNAME", "shape@example.com")
    monkeypatch.setenv("SPT_AUTH_PASSWORD", "x")
    out = quick_test_node(flow_id, str(target["id"]), env="prod")
    assert "ok" in out
    assert "request" in out
    assert "response" in out or out.get("error") is not None
    assert out.get("flow_id") == flow_id
    assert out.get("node_id")


def test_flow_runtime_variables_and_suite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """In-process (avoid MCP session_manager double-run across TestClient fixtures)."""
    monkeypatch.setenv("QA_CREDENTIALS_KEY", "test-api-key")
    monkeypatch.setenv("SPT_STORE", "json")
    from specs.config import settings

    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "spt_store", "json")

    from specs.flows import executions as ex_store
    from specs.flows.runtime import get_runtime, set_variables, suite_preview

    body = get_runtime("FLOW_SUBSCRIPTION")
    assert body is not None
    assert body["flow_id"] == "FLOW_SUBSCRIPTION"
    assert "variables" in body

    saved = set_variables(
        "FLOW_SUBSCRIPTION",
        {"X-Test": "1", "username": "u@example.com"},
    )
    assert saved["variables"].get("X-Test") == "1"

    prev = suite_preview(group="subscription")
    assert prev["count"] >= 1
    ids = [f["id"] for f in prev["flows"] if not str(f["id"]).startswith("pack:")]
    assert ids

    rows = ex_store.list_executions(limit=5)
    assert isinstance(rows, list)
