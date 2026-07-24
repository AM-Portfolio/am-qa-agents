"""Phase 3 matrix / ChangeIntent / episode / ticket tests."""

import os

os.environ["QA_AGENT_SKIP_UI_TEST"] = "true"
os.environ["QA_AGENT_SKIP_WORK_ITEM"] = "true"


def test_matrix_ranker_assigns_tiers():
    from am_qa_agent.intelligence.matrix import matrix_execution_plan, rank_matrix

    lc = {
        "load_context_id": "lc-test",
        "docs_only": False,
        "webhook": {"repo": "am/am-market"},
        "fin": {
            "services": [{"name": "Market Data"}],
            "scenarios": ["movers_smoke"],
        },
        "ui": {"profile": "SMOKE", "target_url": "http://localhost"},
    }
    intent = {
        "suggested_test_focus": [{"ui_profile": "SMOKE", "fin_scenarios": ["movers_smoke"]}],
        "affected_user_flows": ["market_movers"],
    }
    mx = rank_matrix(load_context=lc, index={"gnx_mode": "full"}, change_intent=intent)
    assert mx["summary"]["total"] >= 3
    assert any(i["tier"] in {"P0", "P1", "P2"} for i in mx["items"])
    plan = matrix_execution_plan(mx, lc)
    assert plan["ui_profile"]
    # Advisory cannot be sole source of P0 for change_intent_flow-only items
    for item in mx["items"]:
        if item.get("demoted_from_p0"):
            assert item["tier"] != "P0"


def test_change_intent_template():
    from am_qa_agent.intelligence.change_intent import interpret_change_intent

    intent = interpret_change_intent(
        load_context={
            "webhook": {"repo": "am/am-modern-ui", "branch": "feature/portfolio"},
            "fin": {"services": [{"name": "Auth Tokens"}], "scenarios": []},
            "ui": {"profile": "AUTH_FLOW_PORTFOLIO"},
        },
        index={"gnx_mode": "full"},
        pr_title="Add movers widget to portfolio dashboard",
        pr_body="UI only; no API contract change",
    )
    assert intent["advisory_only"] is True
    assert "portfolio" in intent["user_goal"].lower() or "movers" in intent["user_goal"].lower()
    assert intent["confidence"] in {"low", "medium", "high"}
    assert intent["suggested_test_focus"]


def test_verify_blocks_matrix_p0():
    from am_qa_agent.intelligence.verify import post_test_verify

    v = post_test_verify(
        smoke={"skipped": True, "status": "COMPLETED"},
        comparisons={"endpoints": [], "resources": [], "users": {}},
        gnx_mode="full",
        matrix_results={"p0_failed": ["ui:SMOKE"]},
    )
    assert v["verified"] is False
    assert any(b.startswith("matrix_p0_fail:") for b in v["blockers"])


def test_verify_blocks_open_p0_work_item():
    from am_qa_agent.intelligence.verify import post_test_verify

    v = post_test_verify(
        smoke={"skipped": True},
        comparisons={"endpoints": [], "resources": [], "users": {}},
        open_work_items=[{"id": "OP-1", "severity": "P0"}],
    )
    assert v["releasable"] is False
    assert any("open_work_item_p0" in b for b in v["blockers"])


def test_episode_persist_and_score():
    from am_qa_agent.stores.episodes import QaEpisode, evaluate_learning, get_episode_store

    learning = evaluate_learning(
        {
            "route": "qa-route",
            "verification": {"releasable": True, "feature_clean": True},
            "matrix": {"summary": {"p0": 2}},
            "change_intent": {"change_intent_id": "ci-x"},
        }
    )
    assert learning["score"] >= 0.7
    assert learning["policy_candidate"] is True
    store = get_episode_store()
    ep = QaEpisode(
        episode_id="ep-unit-1",
        tracking_id="qa-ep-1",
        repo="am/am-market",
        head_sha="abc",
        route="qa-route",
        outcome="completed",
        learning_score=learning["score"],
    )
    store.persist(ep)
    assert store.by_tracking("qa-ep-1") is not None
