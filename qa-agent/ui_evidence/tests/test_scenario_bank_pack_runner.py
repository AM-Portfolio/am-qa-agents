"""Phase 7 — pack select/prep/execute fail-closed (no live SPT)."""
from __future__ import annotations

from unittest.mock import patch

from ui_evidence.plugins import loader as plugin_loader
from ui_evidence.plugins import pack_runner
from ui_evidence.scenario_bank.bank_store import seed_default_rows, upsert_scenario


def test_prep_fail_closed_skips_execute(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path))
    plugin_loader.reload_plugins()
    seed_default_rows("am-subscription", "dev", ["happy_flow", "data_generator"])
    executed = {"called": False}

    def fake_exec(pack: str, env: str):
        executed["called"] = True
        return {"decision": "GO", "api_flows": {}, "api_sweep": {}}

    with patch(
        "ui_evidence.plugins.pack_runner.run_data_prep",
        return_value={
            "ok": False,
            "fail_closed": True,
            "env": "dev",
            "steps": [{"id": "login", "status": "FAILED"}],
        },
    ):
        out = pack_runner.run_api_pack(
            "subscription", "dev", execute_fn=fake_exec
        )
    assert out["decision"] == "NO_GO"
    assert out["reason"] == "prep_fail_closed"
    assert out["executed"] is False
    assert executed["called"] is False
    assert out["bank"]["select_few_count"] >= 0


def test_prep_ok_executes_and_refuses_silent_skip(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path))
    plugin_loader.reload_plugins()
    upsert_scenario(
        "am-subscription",
        "dev",
        {
            "skill": "happy_flow",
            "status": "runnable",
            "dedupe_key": "seed:happy_flow",
            "seed": True,
        },
    )

    def fake_exec(pack: str, env: str):
        return {
            "decision": "SKIPPED",
            "api_flows": {"decision": "SKIPPED"},
            "api_sweep": {"decision": "SKIPPED"},
        }

    with patch(
        "ui_evidence.plugins.pack_runner.run_data_prep",
        return_value={"ok": True, "skipped": False, "steps": []},
    ):
        out = pack_runner.run_api_pack(
            "subscription", "dev", execute_fn=fake_exec
        )
    assert out["decision"] == "NO_GO"
    assert out["executed"] is True
    assert out.get("reason") == "refused_silent_skip"
    assert out["llm_invoked"] is False


def test_empty_api_pack_is_no_go():
    out = pack_runner.run_api_pack("", "dev")
    assert out["decision"] == "NO_GO"
