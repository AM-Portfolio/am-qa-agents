from orchestrator.commit_spt_matrix import push_touches_market_data, resolve_commit_spt_matrix


def test_feature_smoke():
    m = resolve_commit_spt_matrix("feature/spt-smoke")
    assert m["dataset_profile"] == "working"
    assert m["preset"] == "ci-smoke"
    assert m["fail_on_unexpected"] is False


def test_main_load():
    m = resolve_commit_spt_matrix("main")
    assert m["dataset_profile"] == "full"
    assert m["preset"] == "ci-load"
    assert m["fail_on_unexpected"] is True


def test_push_touches_market_data():
    assert push_touches_market_data(
        {"commits": [{"modified": ["am-market-data/helm/README.md"]}]}
    )
    assert not push_touches_market_data(
        {"commits": [{"modified": ["am-news/foo.py"]}]}
    )
