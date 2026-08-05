"""Catalog load tests for am-infra release catalogs."""
from __future__ import annotations

import sys
from pathlib import Path

INFRA_SCRIPTS = Path(__file__).resolve().parents[4] / "am-infra" / "scripts"
# parents: tests -> release_gate -> qa-agent -> am-qa-agents -> AM-Portfolio-grp
# Wait: test file is at am-qa-agents/qa-agent/release_gate/tests/
# parents[0]=tests, [1]=release_gate, [2]=qa-agent, [3]=am-qa-agents, [4]=AM-Portfolio-grp
sys.path.insert(0, str(INFRA_SCRIPTS))

from lib.asrax_release_sheet import (  # noqa: E402
    in_release_service_ids,
    load_business_slis,
    load_namespaces,
    load_risks,
    load_services,
    namespace_sheet_rows,
    risks_sheet_rows,
)


def test_namespaces_loaded():
    ns = load_namespaces()
    names = {n["name"] for n in ns}
    assert "am-apps-prod" in names
    assert "am-apps-dev" in names
    rows = namespace_sheet_rows()
    assert rows[0][0] == "Namespace"
    assert len(rows) > 3


def test_risks_and_services():
    risks = load_risks()
    assert any(r["id"] == "vault-frozen-dev" for r in risks)
    services = load_services()
    assert any(s["id"] == "am-modern-ui" and s["default_in_release"] for s in services)
    assert "am-modern-ui" in in_release_service_ids()
    assert risks_sheet_rows()[0][0] == "id"


def test_business_slis():
    slis = load_business_slis()
    assert any(s["id"] == "login_success_rate" for s in slis)
    assert all("promql" in s for s in slis)
