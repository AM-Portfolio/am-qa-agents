"""Contract / backlog coverage tests."""

import os

os.environ["QA_AGENT_SKIP_GITHUB_CHECKS"] = "true"
os.environ["QA_AGENT_SKIP_GROWTHBOOK"] = "true"


def test_redact_secrets():
    from intelligence.llm import redact_secrets

    raw = 'password = "hunter2secret" and AKIAIOSFODNN7EXAMPLE'
    out = redact_secrets(raw)
    assert "hunter2" not in out
    assert "AKIA" not in out or "REDACTED" in out


def test_spt_catalog_loads():
    from intelligence.catalog import load_spt_playbooks, playbook_candidates_for_repo

    pbs = load_spt_playbooks()
    assert len(pbs) >= 3
    market = playbook_candidates_for_repo("am/am-market")
    assert any("market" in (p.get("id") or "") for p in market)


def test_rbac_denies_when_enabled(monkeypatch):
    monkeypatch.setenv("QA_AGENT_HITL_RBAC", "true")
    monkeypatch.setenv("QA_AGENT_HITL_ROLES", "release-approver")
    from orchestrator.rbac import authorize_hitl_actor

    assert authorize_hitl_actor("alice", roles=["release-approver"])["allowed"] is True
    assert authorize_hitl_actor("bob", roles=["viewer"])["allowed"] is False


def test_metrics_render():
    from observability.metrics import mark_run, render_metrics

    mark_run(route="qa-route", status="release_approved", gnx_mode="full")
    text = render_metrics()
    assert "qa_agent_runs_total" in text


def test_sqlite_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_AGENT_STORE", "sqlite")
    monkeypatch.setenv("QA_AGENT_SQLITE_PATH", str(tmp_path / "t.db"))
    monkeypatch.delenv("QA_AGENT_DATABASE_URL", raising=False)
    # Reset singleton
    import stores as stores
    import stores.sqlite_store as ss

    stores._LEDGER = None
    ss._INSTANCE = None
    from stores import get_ledger

    ledger = get_ledger()
    run = ledger.create_run(tracking_id="qa-sql-1", workflow_id="wf-1", idempotency_key="idem-1")
    ledger.upsert_step("qa-sql-1", "classify", {"route": "qa-route"})
    again = ledger.find_by_idempotency("idem-1")
    assert again is not None
    assert again.tracking_id == run.tracking_id
    got = ledger.get("qa-sql-1")
    assert "classify" in got.steps


def test_postgres_url_normalize():
    from stores.postgres_store import resolve_database_url

    os.environ["QA_AGENT_DATABASE_URL"] = (
        "postgresql://u:p@postgresql.infra.svc.cluster.local:5432/am_qa_agent_dev"
    )
    try:
        assert resolve_database_url().startswith("postgresql+psycopg://")
    finally:
        os.environ.pop("QA_AGENT_DATABASE_URL", None)


def test_dast_disabled_by_default():
    from intelligence.security import run_dast_hook

    r = run_dast_hook(target_url="https://app.example")
    assert r["skipped"] is True
