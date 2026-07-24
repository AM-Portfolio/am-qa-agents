"""LoadContext + load-rules tests."""

from am_qa_agent.intelligence.load_context import apply_load_rules, resolve_load_profile


def test_resolve_feature_branch_inherits_preprod():
    lc = resolve_load_profile(
        tracking_id="qa-t1",
        repo="am/am-market",
        branch="feature/movers",
        head_sha="abc123",
    )
    assert lc["environment"] == "feature"
    assert lc["fin"]["services"]
    names = [s["name"] for s in lc["fin"]["services"]]
    assert "Market Data" in names
    assert lc["routing"]["gnx_index_mode"] == "job"
    assert "credential_refs" in lc


def test_am_modern_ui_selects_auth_flow():
    lc = resolve_load_profile(
        tracking_id="qa-t2",
        repo="am-modern-ui",
        branch="feature/nav",
        head_sha="def",
    )
    assert lc["ui"]["profile"] in {"AUTH_FLOW_MAIN", "AUTH_FLOW_PORTFOLIO", "SMOKE", "RELEASE_GATE"}
    assert lc["ui"]["target_url"]


def test_load_rules_docs_only():
    from am_qa_agent.intelligence.load_context import resolve_env_block

    _, block = resolve_env_block("feature/x")
    applied = apply_load_rules(
        repo="am-market",
        changed_paths=["README.md"],
        env_block=block,
    )
    assert applied.get("docs_only") is True or applied["ui_profile"] == "SMOKE"
