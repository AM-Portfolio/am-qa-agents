"""Phase 1 — plugin loader discovery, detach, env normalize."""
from __future__ import annotations

from pathlib import Path

import yaml

from ui_evidence.plugins import loader as plugin_loader


def test_list_enabled_plugins():
    plugin_loader.reload_plugins()
    rows = plugin_loader.list_plugins()
    ids = {r["id"] for r in rows}
    assert "am-subscription" in ids
    assert "am-identity" in ids
    sub = plugin_loader.get_plugin(plugin_id="am-subscription")
    assert sub is not None
    assert sub.suite == "subscription_module"
    assert sub.api_pack == "subscription"


def test_resolve_api_pack_from_suite():
    plugin_loader.reload_plugins()
    assert plugin_loader.resolve_api_pack_default("subscription_module") == "subscription"
    assert plugin_loader.resolve_api_pack_default("auth_api_module") == "identity"
    assert plugin_loader.resolve_api_pack_default("unknown_suite") == ""


def test_subscription_ui_catalog_matches_legacy():
    plugin_loader.reload_plugins()
    p = plugin_loader.get_plugin(plugin_id="am-subscription")
    assert p is not None
    profiles = plugin_loader.load_ui_profiles(p)
    assert profiles == [
        "SUB_UI_OPEN",
        "SUB_UI_PLANS",
        "SUB_UI_TIME_LEFT",
        "SUBSCRIPTION_SMOKE_FLOW",
    ]
    legacy = (
        Path(__file__).resolve().parents[1] / "catalog" / "subscription_module.yaml"
    )
    data = yaml.safe_load(legacy.read_text(encoding="utf-8"))
    assert tuple(data["ui_profiles"]) == tuple(profiles)


def test_set_enabled_detach_reattach(tmp_path, monkeypatch):
    # Use real plugins root — write state sidecar then restore
    plugin_loader.reload_plugins()
    before = {r["id"] for r in plugin_loader.list_plugins()}
    assert "am-subscription" in before
    out = plugin_loader.set_plugin_enabled("am-subscription", False)
    assert out["ok"] is True
    ids = {r["id"] for r in plugin_loader.list_plugins()}
    assert "am-subscription" not in ids
    out2 = plugin_loader.set_plugin_enabled("am-subscription", True)
    assert out2["ok"] is True
    ids2 = {r["id"] for r in plugin_loader.list_plugins()}
    assert "am-subscription" in ids2


def test_data_prep_dig_normalize_and_fail_closed(monkeypatch):
    """dig→dev; without SPT auth, prep fails closed on dev (Phase 3)."""
    monkeypatch.delenv("SPT_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("SPT_AUTH_PASSWORD", raising=False)
    plugin_loader.reload_plugins()
    p = plugin_loader.get_plugin(plugin_id="am-subscription")
    assert p is not None
    result = plugin_loader.run_data_prep(p, "dig", ctx={"smoke": {}})
    assert result.get("env") == "dev"
    assert result.get("ok") is False
    assert result.get("fail_closed") is True


def test_catalog_bundle():
    plugin_loader.reload_plugins()
    p = plugin_loader.get_plugin(plugin_id="am-subscription")
    assert p is not None
    bundle = plugin_loader.catalog_bundle(p)
    assert "apis" in bundle
    assert "FLOW_SUBSCRIPTION" in str(bundle["apis"])
