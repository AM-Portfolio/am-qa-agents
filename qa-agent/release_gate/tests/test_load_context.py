"""LoadContext + load-rules tests."""

from intelligence.load_context import apply_load_rules, resolve_load_profile


def test_resolve_feature_branch_inherits_preprod():
    lc = resolve_load_profile(
        tracking_id="qa-t1",
        repo="am/am-market",
        branch="feature/movers",
        head_sha="abc123",
    )
    assert lc["environment"] == "feature"
    # Product service_map is external — empty by default in-repo
    assert lc["fin"]["services"] == []
    assert lc["routing"]["gnx_index_mode"] == "job"
    assert "credential_refs" in lc


def test_service_hint_uses_spt_registration(tmp_path, monkeypatch):
    """When CI passes service=, LoadContext hydrates from sibling-style spt.yaml catalog."""
    import yaml

    cat = tmp_path / "am-gateway"
    cat.mkdir()
    (cat / "spt.yaml").write_text(
        yaml.dump(
            {
                "apiVersion": "am.spt/v1",
                "kind": "ServiceLoadTest",
                "service": "am-gateway",
                "enabled": True,
                "runtime": "java",
                "targets": {"dev": "https://am-dev.asrax.in/gateway"},
                "openapi": {"path": "/v3/api-docs"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SPT_CATALOG_EXTERNAL", str(tmp_path))
    lc = resolve_load_profile(
        tracking_id="qa-spt",
        repo="am-core-services",
        branch="main",
        head_sha="abc",
        environment="dev",
        service="am-gateway",
    )
    assert lc["service"] == "am-gateway"
    assert lc["fin"]["services"]
    gw = lc["fin"]["services"][0]
    assert gw["name"] == "am-gateway"
    assert gw["base_url"] == "https://am-dev.asrax.in/gateway"
    assert gw["spec_url"].endswith("/v3/api-docs")
    assert gw.get("source") == "spt_registration"

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
    from intelligence.load_context import resolve_env_block

    _, block = resolve_env_block("feature/x")
    applied = apply_load_rules(
        repo="am-market",
        changed_paths=["README.md"],
        env_block=block,
    )
    assert applied.get("docs_only") is True or applied["ui_profile"] == "SMOKE"
