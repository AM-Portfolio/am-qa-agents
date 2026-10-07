"""DB-backed invent: memory repo, spec_derive, features, quality rating."""
from __future__ import annotations

import json
import os

from ui_evidence.scenario_bank import bank_store as bs
from ui_evidence.scenario_bank.feature_export import persist_features_from_bank
from ui_evidence.scenario_bank.invent_context import build_invent_pack
from ui_evidence.scenario_bank.quality import rate_invent_bank
from ui_evidence.scenario_bank.repo import get_repo, reset_repo_for_tests
from ui_evidence.scenario_bank.spec_derive import derive_and_store


def test_build_dev_mongo_uri_and_resolve(monkeypatch, tmp_path):
    from ui_evidence.scenario_bank.mongo_resolve import (
        build_mongo_uri,
        resolve_dev_mongo,
    )

    uri = build_mongo_uri(
        host="mongodb-dev.asrax.in",
        port="8895",
        user="admin",
        password="p@ss/word",
    )
    assert "mongodb-dev.asrax.in:8895" in uri
    assert "authSource=admin" in uri
    assert "directConnection=true" in uri

    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
    monkeypatch.delenv("MONGO_URI", raising=False)
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.setenv("MONGO_PASSWORD", "secret")
    monkeypatch.setenv("MONGO_USER", "admin")
    monkeypatch.setenv("QA_MONGO_HOST", "mongodb-dev.asrax.in")
    monkeypatch.setenv("QA_MONGO_PORT", "8895")
    # Avoid reading real asrax home
    monkeypatch.setenv("ASRAX_HOME", str(tmp_path))
    out = resolve_dev_mongo(force=True)
    assert out["ok"] is True
    assert out["host_hint"] == "mongodb-dev.asrax.in:8895"
    assert "mongodb-dev.asrax.in:8895" in os.environ["MONGO_URI"]
    assert os.environ["MONGO_DATABASE"] == "am_qa_agent_dev"


def test_memory_repo_isolates_by_bank_dir(tmp_path, monkeypatch):

    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path / "a"))
    reset_repo_for_tests()
    bs.seed_default_rows("svc", "dev", ["data_generator"])
    assert len(bs.list_scenarios("svc", "dev")) == 1

    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path / "b"))
    # token change resets memory
    assert len(bs.list_scenarios("svc", "dev")) == 0


def test_derive_and_store_builds_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path))
    reset_repo_for_tests()
    tools = [
        {"method": "get", "path": "/subscriptions/plans", "title": "plans"},
        {"method": "get", "path": "/subscriptions/me", "title": "me"},
        {"method": "post", "path": "/subscriptions/me/pause", "title": "pause"},
        {"method": "get", "path": "/health", "title": "health"},
    ]
    out = derive_and_store("am-subscription", "dev", tools)
    assert out["ok"] is True
    assert out["surface_count"] == 4
    repo = get_repo()
    surface = repo.get_surface("am-subscription", "dev")
    profile = repo.get_profile("am-subscription", "dev")
    assert surface.get("count") == 4
    assert profile.get("derived") is True
    assert any("plans" in p for p in (profile.get("primary_reads") or []))
    assert "pause" in (profile.get("lifecycle") or [])
    assert "skill_overlays" in profile


def test_invent_pack_uses_db_profile_not_plugin_files(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path))
    reset_repo_for_tests()
    tools = [
        {"method": "get", "path": "/subscriptions/me", "name": "t.me"},
        {"method": "get", "path": "/subscriptions/plans", "name": "t.plans"},
    ]
    derive_and_store("am-subscription", "dev", tools)
    pack = build_invent_pack(
        "am-subscription",
        "dev",
        tools=tools,
        skill_ids=["security", "happy_flow"],
        scenarios_per_skill=2,
        plugin_root=None,
    )
    assert "Service invent profile" in pack["user"]
    assert "Auto-derived invent profile" in pack["user"]
    assert "skill_overlay: security" in pack["user"]
    assert "/subscriptions/me" in pack["user"]


def test_features_and_quality_in_db(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path))
    reset_repo_for_tests()
    tools = [
        {"method": "get", "path": "/me", "name": "t.me"},
        {"method": "get", "path": "/plans", "name": "t.plans"},
    ]
    derive_and_store("am-subscription", "dev", tools)
    bs.upsert_scenario(
        "am-subscription",
        "dev",
        {
            "skill": "security",
            "title": "me no auth",
            "status": "runnable",
            "auth": "none",
            "negative": True,
            "llm_invented": True,
            "dedupe_key": "invent:security:me",
            "steps": [{"method": "get", "path": "/me", "expected_status": 401}],
        },
    )
    bs.upsert_scenario(
        "am-subscription",
        "dev",
        {
            "skill": "happy_flow",
            "title": "plans me",
            "status": "runnable",
            "auth": "user_jwt",
            "negative": False,
            "llm_invented": True,
            "dedupe_key": "invent:happy_flow:plans",
            "steps": [
                {"method": "get", "path": "/plans", "expected_status": 200},
                {"method": "get", "path": "/me", "expected_status": 200},
            ],
        },
    )
    feats = persist_features_from_bank("am-subscription", "dev")
    assert feats["count"] == 2
    listed = get_repo().list_features("am-subscription", "dev")
    assert len(listed) == 2
    assert any("Given auth is none" in "\n".join(f.get("gherkin_lines") or []) for f in listed)

    rating = rate_invent_bank("am-subscription", "dev")
    assert 1.0 <= float(rating["quality_score"]) <= 10.0
    kn = get_repo().get_knowledge("am-subscription", "dev")
    assert kn.get("quality_score") == rating["quality_score"]


def test_cold_invent_persists_to_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path))
    reset_repo_for_tests()
    from ui_evidence.scenario_bank import scenario_planner as planner

    def chat(system: str, user: str) -> str:
        import re

        m = re.search(r"skills=(\[[^\]]+\])", user)
        chunk = json.loads(m.group(1)) if m else ["happy_flow"]
        return json.dumps(
            [
                {
                    "skill": sid,
                    "kind": "api",
                    "dedupe_key": f"invent:{sid}:x",
                    "auth": "none" if sid == "security" else "user_jwt",
                    "negative": sid in {"validation", "security", "level5_abuse"},
                    "steps": [
                        {
                            "path": "/plans",
                            "method": "get",
                            "expected_status": 401 if sid == "security" else 200,
                        }
                    ],
                }
                for sid in chunk
            ]
        )

    tools = [{"path": "/plans", "method": "get", "name": "t.plans"}]
    out = planner.invent_for_service(
        "am-subscription",
        "dev",
        tools=tools,
        force_llm=True,
        chat_fn=chat,
        owner="repo-test",
    )
    assert out["invent_complete"] is True
    assert get_repo().get_surface("am-subscription", "dev").get("count", 0) >= 1
    assert get_repo().get_profile("am-subscription", "dev").get("derived") is True
    assert len(bs.list_scenarios("am-subscription", "dev")) >= 1
