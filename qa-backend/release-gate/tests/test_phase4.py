"""Phase 4 HITL / SAST / learning tests."""

import os

os.environ["QA_AGENT_SKIP_SAST"] = "false"


def test_sast_blocks_pem():
    from am_qa_agent.intelligence.security import run_sast_hook

    r = run_sast_hook(
        repo="am/am-market",
        head_sha="abc",
        changed_paths=["deploy/prod.pem", "src/main.py"],
    )
    assert r["status"] == "FAILED"
    assert r["blockers"]


def test_sast_detects_secret_snippet():
    from am_qa_agent.intelligence.security import run_sast_hook

    r = run_sast_hook(
        repo="am/x",
        head_sha="abc",
        file_snippets={"cfg.py": 'API_KEY = "supersecretvalue123"'},
    )
    assert any(f["rule"] == "generic_api_key" for f in r["findings"])


def test_hitl_auto_approve(monkeypatch):
    import asyncio

    monkeypatch.setenv("QA_AGENT_HITL_AUTO_APPROVE", "true")
    monkeypatch.delenv("QA_AGENT_SKIP_HITL", raising=False)
    from am_qa_agent.orchestrator.hitl import await_inline_hitl

    out = asyncio.get_event_loop().run_until_complete(
        await_inline_hitl(
            "qa-hitl-1",
            pdf_docs_ref="artifacts/x.html",
            recommendation="proceed",
            gnx_mode="full",
            releasable=True,
        )
    )
    assert out["decision"] == "approved"


def test_hitl_never_auto_when_degraded(monkeypatch):
    import asyncio

    monkeypatch.setenv("QA_AGENT_HITL_AUTO_APPROVE", "true")
    monkeypatch.delenv("QA_AGENT_SKIP_HITL", raising=False)
    from am_qa_agent.orchestrator.hitl import await_inline_hitl

    out = asyncio.get_event_loop().run_until_complete(
        await_inline_hitl(
            "qa-hitl-2",
            pdf_docs_ref="artifacts/x.html",
            recommendation="proceed_with_warnings",
            gnx_mode="degraded",
            releasable=True,
        )
    )
    assert out["decision"] == "rejected"
    assert out["degraded_banner"] is True


def test_learning_promotion_dual_gate():
    from am_qa_agent.learning import evaluate_learning_offline, ingest_feedback_event, record_promotion
    from am_qa_agent.stores.episodes import QaEpisode, get_episode_store

    get_episode_store().persist(
        QaEpisode(
            episode_id="ep-learn-1",
            tracking_id="qa-learn-1",
            route="qa-route",
            outcome="release_approved",
            payload={
                "verification": {"releasable": True, "feature_clean": True},
                "matrix_summary": {"p0": 1},
                "change_intent_id": "ci-1",
            },
        )
    )
    ingest_feedback_event(
        tracking_id="qa-learn-1",
        kind="approve.release",
        actor="alice",
        episode_id="ep-learn-1",
    )
    ev = evaluate_learning_offline(
        tracking_id="qa-learn-1",
        hitl={"decision": "approved", "actor": "alice"},
    )
    assert ev["policy_candidate"] is True
    assert ev.get("candidate_id")
    blocked = record_promotion(
        candidate_id=ev["candidate_id"],
        human_approved=False,
        actor="alice",
    )
    assert blocked["promoted"] is False
    assert blocked["blocked_reason"] == "human_gate"
    ok = record_promotion(
        candidate_id=ev["candidate_id"],
        human_approved=True,
        offline_eval_passed=True,
        actor="alice",
    )
    assert ok["promoted"] is True
