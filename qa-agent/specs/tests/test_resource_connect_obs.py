"""Resource connect apps + observability link builders + obs-logs soft-fail."""
from __future__ import annotations

from pathlib import Path

import pytest

from specs.observability import grafana_links as gl
from specs.observability.obs_logs import fetch_obs_logs
from specs.observability.run_correlation import capture_run_correlation, attach_obs_to_row
from specs.security import credential_store as cs


@pytest.fixture()
def cred_tmpdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(cs.settings, "data_dir", str(tmp_path))
    monkeypatch.setenv("QA_CREDENTIALS_KEY", "test-key-resource-connect")
    monkeypatch.setattr(cs.settings, "grafana_public_url", "https://grafana.example.test")
    monkeypatch.setattr(cs.settings, "grafana_k6_dashboard_uid", "spt-load-testing")
    return tmp_path


def test_credential_apps_include_resources(cred_tmpdir):
    apps = {a["id"]: a for a in cs.list_credential_apps()}
    assert "grafana" in apps
    assert "prometheus" in apps
    assert "zoho-cliq" in apps
    assert "temporal" in apps
    assert apps["grafana"]["kind"] == "grafana_token"
    assert apps["grafana"]["group"] == "resource"


def test_upsert_resolve_app_credential(cred_tmpdir):
    pub = cs.upsert_credential(
        id="cred_graf1",
        name="Grafana dev",
        kind="grafana_token",
        env="dev",
        app_id="grafana",
        base_url="https://grafana.dev.example",
        token="glsa_test_token",
    )
    assert pub["app_id"] == "grafana"
    assert "token" not in pub
    resolved = cs.resolve_app_credential("grafana", env="dev")
    assert resolved is not None
    assert resolved["base_url"] == "https://grafana.dev.example"
    assert resolved["token"] == "glsa_test_token"
    assert cs.resolve_grafana_base(env="dev") == "https://grafana.dev.example"


def test_prometheus_optional_token(cred_tmpdir):
    pub = cs.upsert_credential(
        id="cred_prom1",
        name="Prom",
        kind="prometheus_endpoint",
        env="dev",
        app_id="prometheus",
        base_url="http://prometheus:9090",
        token="",
    )
    assert pub["has_secret"] is False
    assert cs.resolve_prometheus_base(env="dev") == "http://prometheus:9090"


def test_cliq_and_temporal_resolve(cred_tmpdir, monkeypatch: pytest.MonkeyPatch):
    cs.upsert_credential(
        id="cred_cliq1",
        name="Cliq",
        kind="cliq_webhook",
        env="dev",
        app_id="zoho-cliq",
        token="https://cliq.example/hook",
    )
    assert cs.resolve_cliq_webhook(env="dev") == "https://cliq.example/hook"

    cs.upsert_credential(
        id="cred_temp1",
        name="Temporal",
        kind="temporal_endpoint",
        env="dev",
        app_id="temporal",
        base_url="temporal.example:7233",
        username="qa-agent",
        token="",
    )
    ep = cs.resolve_temporal_endpoint(env="dev")
    assert ep["address"] == "temporal.example:7233"
    assert ep["namespace"] == "qa-agent"

    monkeypatch.delenv("ZOHO_CLIQ_WEBHOOK_URL", raising=False)
    # Missing env falls back after delete — still have store
    assert cs.resolve_cliq_webhook(env="dev").startswith("https://cliq")


def test_link_builders_include_trace(cred_tmpdir):
    cs.upsert_credential(
        id="cred_graf2",
        name="Grafana",
        kind="grafana_token",
        env="dev",
        app_id="grafana",
        base_url="https://grafana.example.test",
        token="t",
    )
    tid = "abc123def456"
    tempo = gl.grafana_tempo_explore_url(tid, env="dev")
    loki = gl.grafana_loki_explore_url(tid, env="dev")
    assert "explore" in tempo
    assert tid in tempo
    assert "explore" in loki
    assert "abc123def456" in loki

    obs = gl.build_observability_resources(
        run_id="run1",
        trace_id=tid,
        correlation_id="qa-corr1",
        environment="dev",
        env="dev",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:05:00Z",
    )
    assert obs["trace_id"] == tid
    assert obs["grafana_tempo_explore_url"]
    assert obs["grafana_loki_explore_url"]
    assert obs["connected"]["grafana"] is True


def test_capture_and_attach_row(cred_tmpdir):
    corr = capture_run_correlation()
    assert corr["trace_id"]
    assert corr["correlation_id"].startswith("qa-")
    row = {
        "id": "r1",
        "environment": "dev",
        "trace_id": corr["trace_id"],
        "correlation_id": corr["correlation_id"],
        "started_at": "2026-01-01T00:00:00Z",
    }
    out = attach_obs_to_row(row)
    assert "observability_resources" in out


@pytest.mark.asyncio
async def test_obs_logs_soft_fail_no_trace():
    out = await fetch_obs_logs(trace_id="", correlation_id="")
    assert out["available"] is False
    assert out["reason"] == "no_trace_id"


@pytest.mark.asyncio
async def test_obs_logs_skip_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_AGENT_SKIP_OBSERVE", "1")
    out = await fetch_obs_logs(trace_id="abcd")
    assert out["available"] is False
    assert out["reason"] == "observe_skipped"
