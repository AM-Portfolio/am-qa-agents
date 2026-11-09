"""Phase 2 — contract smoke + knowledge persist (no live SPT)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from ui_evidence.plugins import loader as plugin_loader
from ui_evidence.plugins import onboard as onboard_mod


def test_skills_yaml_exists():
    path = (
        Path(__file__).resolve().parents[1] / "scenario_bank" / "skills.yaml"
    )
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "happy_flow" in text
    assert "level5_abuse" in text


def test_smoke_empty_tools_blocks():
    plugin_loader.reload_plugins()

    def _fake_refresh(**kwargs):
        return {"ok": True}

    def _fake_list(**kwargs):
        return {"tools": [], "count": 0}

    with patch(
        "specs.openapi_tools.registry.refresh_tools_from_prod", _fake_refresh
    ), patch("specs.openapi_tools.registry.list_tools", _fake_list):
        smoke = onboard_mod.contract_smoke("am-subscription", "dev")
    assert smoke["ok"] is False
    assert smoke["status"] == "onboard_blocked"
    assert smoke["tool_count"] == 0


def test_smoke_ok_with_tools():
    plugin_loader.reload_plugins()
    tools = [
        {"path": "/health", "method": "get"},
        {"path": "/plans", "method": "get"},
        {"path": "/me", "method": "get"},
    ]

    with patch(
        "specs.openapi_tools.registry.refresh_tools_from_prod",
        return_value={},
    ), patch(
        "specs.openapi_tools.registry.list_tools",
        return_value={"tools": tools, "count": 3},
    ):
        smoke = onboard_mod.contract_smoke("am-subscription", "dev")
    assert smoke["ok"] is True
    assert smoke["tool_count"] == 3
    assert smoke.get("openapi_hash")


def test_onboard_writes_knowledge_no_llm(tmp_path, monkeypatch):
    plugin_loader.reload_plugins()
    kdir = tmp_path / "knowledge"
    monkeypatch.setattr(onboard_mod, "_knowledge_dir", lambda: kdir)
    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path / "bank_root"))

    tools = [
        {"path": "/a", "method": "get"},
        {"path": "/b", "method": "get"},
        {"path": "/c", "method": "get"},
    ]
    with patch(
        "specs.openapi_tools.registry.refresh_tools_from_prod",
        return_value={},
    ), patch(
        "specs.openapi_tools.registry.list_tools",
        return_value={"tools": tools},
    ), patch(
        "ui_evidence.scenario_bank.llm_status.probe_litellm",
        return_value={"available": False, "model": "x", "error": "offline"},
    ), patch(
        "ui_evidence.plugins.loader.run_data_prep",
        return_value={"ok": True, "skipped": False, "steps": []},
    ):
        result = onboard_mod.onboard_plugin(
            "am-subscription", "dev", skip_prep=False
        )
    assert result["llm_invoked"] is False
    assert result["litellm"]["available"] is False
    kpath = Path(result["knowledge_path"])
    assert kpath.is_file()
    data = json.loads(kpath.read_text(encoding="utf-8"))
    assert data["env"] == "dev"
    assert data["contract_smoke"]["ok"] is True
    assert result.get("bank", {}).get("ok") is True
    assert result["bank"]["count"] >= 1


def test_onboard_blocked_never_invokes_llm(tmp_path, monkeypatch):
    plugin_loader.reload_plugins()
    monkeypatch.setattr(onboard_mod, "_knowledge_dir", lambda: tmp_path)

    with patch(
        "specs.openapi_tools.registry.refresh_tools_from_prod",
        return_value={},
    ), patch(
        "specs.openapi_tools.registry.list_tools",
        return_value={"tools": []},
    ), patch(
        "ui_evidence.scenario_bank.llm_status.probe_litellm",
        return_value={"available": True, "model": "deepseek-chat"},
    ):
        result = onboard_mod.onboard_plugin("am-subscription", "dev")
    assert result["status"] == "onboard_blocked"
    assert result["llm_invoked"] is False
