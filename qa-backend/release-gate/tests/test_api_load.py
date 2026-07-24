"""API load runner unit tests (mocked HTTP)."""

from __future__ import annotations

import pytest

from am_qa_agent.adapters import api_load


class _Resp:
    def __init__(self, status_code: int):
        self.status_code = status_code


@pytest.mark.asyncio
async def test_prepare_and_run_analysis_health(monkeypatch):
    calls: list[str] = []

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def get(self, url):
            calls.append(url)
            if "actuator/health" in url:
                return _Resp(200)
            if "api-docs" in url:
                return _Resp(401)
            return _Resp(404)

    monkeypatch.setattr(api_load.httpx, "AsyncClient", _Client)
    monkeypatch.setenv("QA_AGENT_SKIP_SPT", "true")
    monkeypatch.setenv("QA_AGENT_API_LOAD_VUS", "2")
    monkeypatch.setenv("QA_AGENT_API_LOAD_ITERATIONS", "3")

    services = [
        {
            "name": "Analysis Service",
            "base_url": "https://am-dev.asrax.in/analysis",
            "spec_url": "https://am-dev.asrax.in/analysis/v3/api-docs",
        }
    ]
    prep = await api_load.prepare_services(services, tracking_id="t1")
    assert prep["status"] in {"OK", "PARTIAL"}
    assert prep["ready_count"] == 1
    assert prep["services"][0]["health_url"]

    run = await api_load.run_api_scenarios(
        services=services,
        scenarios=["health_smoke", "contract_smoke"],
        tracking_id="t1",
        prefer_spt=False,
    )
    assert run["status"] == "PASSED"
    assert run["passed"] == ["Analysis Service"]
    health = run["services"][0]["scenarios"]["health_smoke"]
    assert health["ok"] is True
    assert health["iterations"] == 3
    assert health["latency_ms"]["p50"] is not None
    contract = run["services"][0]["scenarios"]["contract_smoke"]
    assert contract["auth_gated"] is True
    assert contract["ok"] is True


def test_resolve_load_profile_am_analysis():
    from am_qa_agent.intelligence.load_context import resolve_load_profile

    lc = resolve_load_profile(
        tracking_id="t",
        repo="ssd2658/am-core-services",
        branch="master",
        head_sha="abc",
        environment="dev",
        service="am-analysis",
    )
    names = [s["name"] for s in lc["fin"]["services"]]
    assert names == ["Analysis Service"]
    assert "health_smoke" in lc["fin"]["scenarios"]
    assert lc["fin"]["services"][0]["base_url"].endswith("/analysis")
