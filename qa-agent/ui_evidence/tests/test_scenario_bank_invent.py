"""Phase 5 — invent grounding + warm skip + typed prompt registry (mocked chat)."""
from __future__ import annotations

import json
from unittest.mock import patch

from prompts.loader import load_prompt_type, load_registry
from ui_evidence.plugins import loader as plugin_loader
from ui_evidence.plugins import onboard as onboard_mod
from ui_evidence.scenario_bank import scenario_planner as planner
from ui_evidence.scenario_bank.bank_store import list_scenarios, set_flags
from ui_evidence.scenario_bank.feature_export import export_features_from_bank
from ui_evidence.scenario_bank.invent_context import ban_patterns, build_invent_pack


def test_prompt_registry_lists_types_and_invent_playbooks():
    reg = load_registry()
    assert reg.get("apiVersion") == "am.qa.prompts/v1"
    types = reg.get("types") or {}
    assert "invent" in types
    assert "select" in types
    skills = planner.load_invent_skill_ids()
    bundle = load_prompt_type("invent", skill_ids=skills, require_playbooks=True)
    assert bundle.schema_version == "invent-scenario/v2"
    assert "security" in bundle.playbooks
    assert "Intent" in bundle.playbooks["security"]
    assert "gpt-4o-mini" in bundle.preferred_models


def test_unknown_prompt_type_fails_closed():
    try:
        load_prompt_type("not_a_real_type")
        assert False, "expected KeyError"
    except KeyError as exc:
        assert "not_a_real_type" in str(exc)


def test_invent_pack_includes_security_playbook_intent(tmp_path, monkeypatch):
    from ui_evidence.scenario_bank.repo import reset_repo_for_tests
    from ui_evidence.scenario_bank.spec_derive import derive_and_store

    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path))
    reset_repo_for_tests()
    tools = [{"name": "t.me", "path": "/subscriptions/me", "method": "get"}]
    derive_and_store("am-subscription", "dev", tools)
    pack = build_invent_pack(
        "am-subscription",
        "dev",
        tools=tools,
        skill_ids=["security", "happy_flow"],
        scenarios_per_skill=2,
    )
    assert "Intent" in pack["user"]
    assert "security" in pack["user"]
    assert "expected_status" in pack["system"]
    assert "Service invent profile" in pack["user"]
    assert "Auto-derived invent profile" in pack["user"]
    assert "skill_overlay: security" in pack["user"]
    assert "/subscriptions/me" in pack["user"]


def test_identity_invent_profile_is_service_specific(tmp_path, monkeypatch):
    from ui_evidence.scenario_bank.repo import reset_repo_for_tests
    from ui_evidence.scenario_bank.spec_derive import derive_and_store

    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path))
    reset_repo_for_tests()
    tools = [{"name": "t.login", "path": "/auth/login", "method": "post"}]
    derive_and_store("am-identity", "dev", tools)
    pack = build_invent_pack(
        "am-identity",
        "dev",
        tools=tools,
        skill_ids=["happy_flow", "validation"],
        scenarios_per_skill=2,
    )
    assert "am-identity" in pack["user"]
    assert "Auto-derived invent profile" in pack["user"]
    assert "skill_overlay: happy_flow" in pack["user"]
    assert "/auth/login" in pack["user"]


def test_ground_ungrounded_becomes_draft():
    row = planner.ground_row(
        {
            "skill": "happy_flow",
            "kind": "api",
            "steps": [
                {"path": "/no-such-path", "method": "get", "expected_status": 200}
            ],
        },
        tool_paths={"/plans", "/me"},
        tool_names=set(),
    )
    assert row["grounded"] is False
    assert row["status"] == "draft"


def test_ground_missing_expected_status_is_draft():
    row = planner.ground_row(
        {
            "skill": "happy_flow",
            "kind": "api",
            "steps": [{"path": "/plans", "method": "get"}],
        },
        tool_paths={"/plans"},
        tool_names=set(),
    )
    assert row["status"] == "draft"
    assert "missing_expected_status" in str(row.get("ground_reason"))


def test_ground_security_without_negative_non2xx_is_draft():
    row = planner.ground_row(
        {
            "skill": "security",
            "kind": "api",
            "negative": False,
            "steps": [{"path": "/me", "method": "get", "expected_status": 200}],
        },
        tool_paths={"/me"},
        tool_names=set(),
    )
    assert row["status"] == "draft"


def test_ground_ban_path_is_draft():
    from prompts.loader import load_prompt_type

    bundle = load_prompt_type("invent", skill_ids=["security"], require_playbooks=True)
    pats = ban_patterns(bundle)
    row = planner.ground_row(
        {
            "skill": "security",
            "kind": "api",
            "negative": True,
            "steps": [
                {
                    "path": "/realms/foo/protocol/openid-connect/token",
                    "method": "post",
                    "expected_status": 401,
                }
            ],
        },
        tool_paths={"/realms/foo/protocol/openid-connect/token"},
        tool_names=set(),
        ban_patterns=pats,
    )
    assert row["status"] == "draft"
    assert "banned_path" in str(row.get("ground_reason"))


def test_ground_ui_is_draft_ui():
    row = planner.ground_row(
        {
            "skill": "happy_flow",
            "kind": "ui",
            "steps": [{"path": "/x", "expected_status": 200}],
        },
        tool_paths={"/x"},
        tool_names=set(),
    )
    assert row["status"] == "draft_ui"


def test_feature_export_includes_auth_and_status(tmp_path):
    out = tmp_path / "out.feature"
    export_features_from_bank(
        [
            {
                "skill": "security",
                "title": "me without auth",
                "status": "runnable",
                "auth": "none",
                "negative": True,
                "llm_invented": True,
                "steps": [{"method": "get", "path": "/me", "expected_status": 401}],
            }
        ],
        out,
    )
    text = out.read_text(encoding="utf-8")
    assert "Given auth is none" in text
    assert "Then status is 401" in text


def test_cold_invent_max_two_calls(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path))
    calls: list[str] = []

    def chat(system: str, user: str) -> str:
        calls.append(user)
        assert "Platform skill playbooks" in user or "skill playbooks" in user.lower()
        assert "expected_status" in system
        assert "service=" in user
        skill = "happy_flow"
        for sid in planner.load_invent_skill_ids():
            if f'"{sid}"' in user or sid in user:
                skill = sid
                break
        return json.dumps(
            [
                {
                    "skill": skill,
                    "kind": "api",
                    "dedupe_key": f"invent:{skill}",
                    "auth": "user_jwt",
                    "negative": skill in {"validation", "security", "level5_abuse"},
                    "steps": [
                        {
                            "path": "/plans",
                            "method": "get",
                            "expected_status": 401
                            if skill == "security"
                            else 200,
                        }
                    ],
                }
            ]
        )

    tools = [{"name": "t.plans", "path": "/plans", "method": "get"}]
    out = planner.invent_for_service(
        "am-subscription",
        "dev",
        tools=tools,
        force_llm=True,
        chat_fn=chat,
        owner="test-invent",
    )
    assert out["llm_invoked"] is True
    assert out["call_count"] <= planner.MAX_INVENT_CALLS
    assert out["call_count"] == 2
    assert out["invent_complete"] is True
    assert out.get("prompt_type") == "invent"
    assert len(calls) == 2
    assert any("security" in c and "Intent" in c for c in calls)


def test_warm_skips_llm(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path))
    set_flags("am-subscription", "dev", invent_complete=True, needs_reinvent=False)
    calls = []

    def chat(system: str, user: str) -> str:
        calls.append(1)
        return "[]"

    out = planner.invent_for_service(
        "am-subscription",
        "dev",
        tools=[{"path": "/plans", "method": "get"}],
        force_llm=False,
        chat_fn=chat,
    )
    assert out["skipped"] is True
    assert out["reason"] == "warm_invent_complete"
    assert out["llm_invoked"] is False
    assert calls == []


def test_onboard_blocks_invent_when_llm_down(tmp_path, monkeypatch):
    plugin_loader.reload_plugins()
    monkeypatch.setattr(onboard_mod, "_knowledge_dir", lambda: tmp_path / "k")
    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path / "bank"))
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
        return_value={"available": False, "error": "offline"},
    ), patch(
        "ui_evidence.plugins.loader.run_data_prep",
        return_value={"ok": True, "skipped": True},
    ):
        result = onboard_mod.onboard_plugin("am-subscription", "dev", skip_prep=True)
    assert result["llm_invoked"] is False
    assert result["invent"]["reason"] == "litellm_unavailable"
    assert result["bank"]["count"] >= 1


def test_onboard_warm_second_pass(tmp_path, monkeypatch):
    plugin_loader.reload_plugins()
    monkeypatch.setattr(onboard_mod, "_knowledge_dir", lambda: tmp_path / "k")
    monkeypatch.setenv("QA_SCENARIO_BANK_DIR", str(tmp_path / "bank"))
    tools = [
        {"path": "/plans", "method": "get"},
        {"path": "/me", "method": "get"},
        {"path": "/health", "method": "get"},
    ]

    def chat(system: str, user: str) -> str:
        import re

        m = re.search(r"skills=(\[[^\]]+\])", user)
        chunk_skills = json.loads(m.group(1)) if m else ["happy_flow"]
        return json.dumps(
            [
                {
                    "skill": sid,
                    "kind": "api",
                    "dedupe_key": f"invent:{sid}",
                    "auth": "none" if sid == "security" else "user_jwt",
                    "negative": sid
                    in {"validation", "security", "level5_abuse", "null_point"},
                    "steps": [
                        {
                            "path": "/plans",
                            "method": "get",
                            "expected_status": 401 if sid == "security" else 200,
                        }
                    ],
                }
                for sid in chunk_skills
            ]
        )

    with patch(
        "specs.openapi_tools.registry.refresh_tools_from_prod",
        return_value={},
    ), patch(
        "specs.openapi_tools.registry.list_tools",
        return_value={"tools": tools},
    ), patch(
        "ui_evidence.scenario_bank.llm_status.probe_litellm",
        return_value={"available": True, "model": "gpt-4o-mini"},
    ), patch(
        "ui_evidence.plugins.loader.run_data_prep",
        return_value={"ok": True, "skipped": True},
    ), patch(
        "ui_evidence.scenario_bank.scenario_planner._default_chat",
        chat,
    ):
        first = onboard_mod.onboard_plugin(
            "am-subscription", "dev", skip_prep=True, force_llm=True
        )
        second = onboard_mod.onboard_plugin(
            "am-subscription", "dev", skip_prep=True, force_llm=False
        )
    assert first["llm_invoked"] is True
    assert first["invent"]["call_count"] <= 2
    assert second["llm_invoked"] is False
    assert second["invent"].get("reason") == "warm_invent_complete"
    assert list_scenarios("am-subscription", "dev")
