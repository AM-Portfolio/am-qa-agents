"""Phase 6 — env filter, select-few, hash drift."""
from __future__ import annotations

import json

from ui_evidence.scenario_bank import env_policy as ep
from ui_evidence.scenario_bank import hash_drift as hd
from ui_evidence.scenario_bank.bank_store import load_bank, seed_default_rows


def test_contabo_blocks_l5():
    rows = [
        {"skill": "happy_flow", "status": "runnable", "dedupe_key": "a"},
        {"skill": "level5_abuse", "status": "runnable", "dedupe_key": "b"},
        {"skill": "security", "status": "runnable", "dedupe_key": "c"},
        {"skill": "level2_alt_path", "status": "runnable", "dedupe_key": "d"},
    ]
    out = ep.filter_scenarios_for_env(rows, "contabo_prod")
    skills = {r["skill"] for r in out["selected"]}
    skipped = {r["skill"] for r in out["skipped"]}
    assert "happy_flow" in skills
    assert "level2_alt_path" in skills
    assert "level5_abuse" in skipped
    assert "security" in skipped
    assert all(r.get("skip_reason") == "block" for r in out["skipped"] if r["skill"] in {"level5_abuse", "security"})


def test_select_few_never_picks_blocked_l5():
    rows = [
        {"skill": "happy_flow", "status": "runnable", "dedupe_key": "h"},
        {"skill": "validation", "status": "runnable", "dedupe_key": "v"},
        {"skill": "security", "status": "runnable", "dedupe_key": "s"},
        {"skill": "null_point", "status": "runnable", "dedupe_key": "n"},
    ]
    out = ep.select_few(rows, "prod", limit=6)
    picked_skills = {r["skill"] for r in out["select_few"]}
    assert "security" not in picked_skills
    assert "happy_flow" in picked_skills


def test_hash_drift_sets_needs_reinvent(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path / "bank"))
    kroot = tmp_path / "knowledge"
    kroot.mkdir()
    (kroot / "am-subscription_dev.json").write_text(
        json.dumps(
            {
                "plugin_id": "am-subscription",
                "contract_smoke": {"openapi_hash": "aaa111"},
            }
        ),
        encoding="utf-8",
    )
    seed_default_rows("am-subscription", "dev", ["happy_flow"])
    out = hd.apply_hash_drift(
        "am-subscription",
        "dev",
        plugin_id="am-subscription",
        new_openapi_hash="bbb222",
        knowledge_root=kroot,
    )
    assert out["drift"] is True
    assert out["needs_reinvent"] is True
    bank = load_bank("am-subscription", "dev")
    assert bank["needs_reinvent"] is True
    assert bank["invent_complete"] is False


def test_hash_match_no_drift(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path / "bank"))
    kroot = tmp_path / "knowledge"
    kroot.mkdir()
    (kroot / "am-subscription_dev.json").write_text(
        json.dumps({"contract_smoke": {"openapi_hash": "same"}}),
        encoding="utf-8",
    )
    out = hd.apply_hash_drift(
        "am-subscription",
        "dev",
        plugin_id="am-subscription",
        new_openapi_hash="same",
        knowledge_root=kroot,
    )
    assert out["drift"] is False
    assert out["reason"] == "hash_match"


def test_draft_rows_not_selected():
    rows = [
        {"skill": "happy_flow", "status": "draft", "dedupe_key": "d"},
        {"skill": "validation", "status": "runnable", "dedupe_key": "v"},
    ]
    out = ep.select_few(rows, "dev", limit=3)
    assert all(r["skill"] != "happy_flow" for r in out["select_few"])
    assert any(r["skill"] == "validation" for r in out["select_few"])
