"""Phase 4 — bank store cap, dedupe, invent lock (no LLM)."""
from __future__ import annotations

from ui_evidence.scenario_bank import bank_store as bs


def test_seed_and_dedupe(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path))
    r1 = bs.seed_default_rows(
        "am-subscription", "dev", ["data_generator", "happy_flow"]
    )
    assert r1["ok"] is True
    assert r1["count"] == 2
    r2 = bs.seed_default_rows(
        "am-subscription", "dev", ["data_generator", "happy_flow"]
    )
    assert r2["count"] == 2
    rows = bs.list_scenarios("am-subscription", "dev")
    keys = sorted(r["dedupe_key"] for r in rows)
    assert keys == ["seed:data_generator", "seed:happy_flow"]


def test_cap_evicts_non_seed_first(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path))
    bs.upsert_scenario(
        "am-subscription",
        "dev",
        {"dedupe_key": "seed:keep", "seed": True, "skill": "data_generator"},
        cap=3,
    )
    for i in range(5):
        bs.upsert_scenario(
            "am-subscription",
            "dev",
            {"dedupe_key": f"gen:{i}", "seed": False, "skill": "happy_flow"},
            cap=3,
        )
    rows = bs.list_scenarios("am-subscription", "dev")
    assert len(rows) == 3
    assert any(r.get("dedupe_key") == "seed:keep" for r in rows)


def test_invent_lock_single_winner(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path))
    a = bs.acquire_invent_lock("am-subscription", "dev", owner="owner-a", ttl=60)
    assert a["ok"] is True
    b = bs.acquire_invent_lock("am-subscription", "dev", owner="owner-b", ttl=60)
    assert b["ok"] is False
    assert b["held"] is True
    assert b["owner"] == "owner-a"
    rel = bs.release_invent_lock("am-subscription", "dev", owner="owner-b")
    assert rel["ok"] is False
    rel2 = bs.release_invent_lock("am-subscription", "dev", owner="owner-a")
    assert rel2["released"] is True
    c = bs.acquire_invent_lock("am-subscription", "dev", owner="owner-c", ttl=60)
    assert c["ok"] is True


def test_dedupe_key_collapses(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path))
    bs.upsert_scenario(
        "am-subscription",
        "dev",
        {"dedupe_key": "x", "skill": "happy_flow", "status": "draft"},
    )
    bs.upsert_scenario(
        "am-subscription",
        "dev",
        {"dedupe_key": "x", "skill": "happy_flow", "status": "runnable"},
    )
    rows = bs.list_scenarios("am-subscription", "dev")
    assert len(rows) == 1
    assert rows[0]["status"] == "runnable"


def test_dig_maps_to_dev_bank_path(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path))
    from ui_evidence.scenario_bank.repo import norm_env

    bs.seed_default_rows("am-subscription", "dig", ["data_generator"])
    assert norm_env("dig") == "dev"
    assert len(bs.list_scenarios("am-subscription", "dev")) == 1
    assert len(bs.list_scenarios("am-subscription", "dig")) == 1
