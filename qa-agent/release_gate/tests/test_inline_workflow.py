"""Inline release readiness path (no Temporal) — Phase 4."""

import os

import pytest

os.environ["QA_AGENT_SKIP_UI_TEST"] = "true"
os.environ["QA_AGENT_SKIP_NOTIFY"] = "true"
os.environ["QA_AGENT_SKIP_INDEX_AWAIT"] = "true"
os.environ["QA_AGENT_SKIP_FIN_AGENT"] = "true"
os.environ["QA_AGENT_SKIP_OBSERVE"] = "true"
os.environ["QA_AGENT_SKIP_WORK_ITEM"] = "true"
os.environ["QA_AGENT_HITL_AUTO_APPROVE"] = "true"
os.environ["QA_AGENT_ENV"] = "test"


@pytest.mark.asyncio
async def test_inline_qa_route(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_AGENT_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setenv("QA_AGENT_HITL_AUTO_APPROVE", "true")
    from orchestrator.temporal_api import run_release_readiness_inline
    from stores import get_episode_store, get_ledger

    tracking_id = "qa-test-inline-p4"
    get_ledger().create_run(tracking_id=tracking_id, workflow_id="wf-test-p4")
    out = await run_release_readiness_inline(
        {
            "tracking_id": tracking_id,
            "repo": "am/am-market",
            "branch": "feature/movers",
            "head_sha": "abc123def456",
            "ci_conclusion": "success",
            "trigger_kind": "manual",
            "pr_title": "Add market movers smoke coverage",
        }
    )
    assert out["route"] == "qa-route"
    assert out["security"]["status"] in {"PASSED", "WARN", "SKIPPED", "FAILED"}
    assert out["change_intent"]["change_intent_id"]
    assert out["matrix"]["summary"]["total"] >= 1
    assert out["hitl"]["decision"] == "approved"
    assert out["status"] == "release_approved"
    assert out["publication"]["pdf_docs_ref"]
    assert out["episode"]["episode_id"]
    assert out["learning"].get("score") is not None
    run = get_ledger().get(tracking_id)
    assert "security_scan" in run.steps
    assert "release_hitl" in run.steps
    assert "evaluate_learning" in run.steps
    assert get_episode_store().by_tracking(tracking_id) is not None


@pytest.mark.asyncio
async def test_inline_dev_route():
    from orchestrator.temporal_api import run_release_readiness_inline
    from stores import get_ledger

    tracking_id = "qa-test-inline-dev-p4"
    get_ledger().create_run(tracking_id=tracking_id, workflow_id="wf-test-dev-p4")
    out = await run_release_readiness_inline(
        {
            "tracking_id": tracking_id,
            "repo": "am/am-market",
            "branch": "feature/movers",
            "head_sha": "fff111",
            "ci_conclusion": "failure",
        }
    )
    assert out["route"] == "dev-route"
    assert out["handoff"]["kind"] == "dev_handoff_ticket"
    assert out["handoff"]["mode"] == "ticket_only"
    assert out["episode"]["episode_id"]
    assert out["comparisons"] == {}
