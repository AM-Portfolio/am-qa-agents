"""API tests for report JSON / Playwright trace download endpoints."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import test_runner as tr
from app.config import settings
from app.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "REPORT_DIR", str(tmp_path))
    tr.test_runs.clear()
    return TestClient(app)


def test_report_json_and_trace_endpoints(client: TestClient, tmp_path: Path):
    test_id = "tid-report-1"
    html = tmp_path / f"{test_id}.html"
    js = tmp_path / f"{test_id}.json"
    pdf = tmp_path / f"{test_id}.pdf"
    trace_dir = tmp_path / "traces" / test_id
    trace_dir.mkdir(parents=True)
    trace = trace_dir / "trace.zip"
    html.write_text("<html>ok</html>", encoding="utf-8")
    js.write_text(json.dumps({"schema": "am-ui-test-report/v2", "test_id": test_id}), encoding="utf-8")
    pdf.write_bytes(b"%PDF-1.4 demo")
    trace.write_bytes(b"PK\x03\x04fake")

    tr.test_runs[test_id] = {
        "status": "COMPLETED",
        "report": str(html),
        "trace": str(trace),
    }

    st = client.get(f"/api/v1/test/status/{test_id}")
    assert st.status_code == 200
    body = st.json()
    assert body["reportUrl"] == f"/api/v1/test/report/{test_id}"
    assert body["reportJsonUrl"] == f"/api/v1/test/report/{test_id}/json"
    assert body["reportPdfUrl"] == f"/api/v1/test/report/{test_id}/pdf"
    assert body["traceUrl"] == f"/api/v1/test/trace/{test_id}"

    rjson = client.get(f"/api/v1/test/report/{test_id}/json")
    assert rjson.status_code == 200
    assert rjson.json()["test_id"] == test_id

    rpdf = client.get(f"/api/v1/test/report/{test_id}/pdf")
    assert rpdf.status_code == 200
    assert rpdf.content.startswith(b"%PDF")

    rtr = client.get(f"/api/v1/test/trace/{test_id}")
    assert rtr.status_code == 200
    assert rtr.content.startswith(b"PK")


def test_trace_404_when_missing(client: TestClient):
    test_id = "missing"
    tr.test_runs[test_id] = {"status": "COMPLETED"}
    assert client.get(f"/api/v1/test/trace/{test_id}").status_code == 404
    assert client.get(f"/api/v1/test/report/{test_id}/json").status_code == 404
