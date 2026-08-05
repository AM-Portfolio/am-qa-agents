"""Cliq single-admin release gate."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from intelligence.cliq_release_gate import (
    PendingReleaseStore,
    build_cliq_approval_body,
    is_release_admin,
    parse_cliq_chat_message,
    release_admin,
    sign_request,
    verify_token,
)


def test_sign_and_verify_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_AGENT_CLIQ_RELEASE_SECRET", "test-secret")
    tok = sign_request("relreq-abc", "approve")
    assert verify_token("relreq-abc", "approve", tok)
    assert not verify_token("relreq-abc", "reject", tok)
    assert not verify_token("relreq-other", "approve", tok)


def test_single_admin_gate(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_AGENT_RELEASE_ADMIN", "release.admin@asrax.in")
    monkeypatch.setenv("QA_AGENT_ENV", "prod")
    assert is_release_admin("release.admin@asrax.in")
    assert is_release_admin("Release.Admin@Asrax.in")
    assert is_release_admin("release.admin")  # local-part
    assert not is_release_admin("other@asrax.in")
    assert not is_release_admin("")


def test_parse_cliq_chat_approve():
    parsed = parse_cliq_chat_message(
        {
            "text": "please approve relreq-deadbeef1234 now",
            "user": {"email": "release.admin@asrax.in"},
        }
    )
    assert parsed["action"] == "approve"
    assert parsed["request_id"] == "relreq-deadbeef1234"
    assert parsed["actor"] == "release.admin@asrax.in"


def test_parse_cliq_chat_reject():
    parsed = parse_cliq_chat_message({"message": "reject relreq-aabbccdd", "actor": "admin@x.com"})
    assert parsed["action"] == "reject"
    assert parsed["request_id"] == "relreq-aabbccdd"


def test_approval_body_contains_links(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_AGENT_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setenv("QA_AGENT_RELEASE_ADMIN", "admin@asrax.in")
    monkeypatch.setenv("QA_AGENT_PUBLIC_BASE_URL", "https://qa.example.com")
    monkeypatch.setenv("QA_AGENT_CLIQ_RELEASE_SECRET", "sec")
    store = PendingReleaseStore(path=tmp_path / "pending.json")
    req = store.create(release_name="R01", env="prod", suite="prod_ui_full", soak_min=30)
    body = build_cliq_approval_body(req)
    assert "APPROVE" in body
    assert "REJECT" in body
    assert req.request_id in body
    assert "admin@asrax.in" in body
    assert f"/v2/releases/{req.request_id}/approve" in body
    assert release_admin() == "admin@asrax.in"


@pytest.mark.asyncio
async def test_request_then_admin_approve_starts_inline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("temporalio")
    monkeypatch.setenv("QA_AGENT_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setenv("QA_AGENT_RELEASE_ADMIN", "admin@asrax.in")
    monkeypatch.setenv("QA_AGENT_ENV", "test")
    monkeypatch.setenv("QA_AGENT_SKIP_NOTIFY", "1")
    monkeypatch.setenv("QA_AGENT_CLIQ_RELEASE_SECRET", "sec")
    monkeypatch.setenv("QA_AGENT_FORCE_INLINE", "1")
    # Reset store singleton
    import intelligence.cliq_release_gate as gate

    gate._STORE = PendingReleaseStore(path=tmp_path / "pending.json")

    from gateway.app import ReleaseOpsRequestBody, _apply_release_decision, request_release_ops

    out = await request_release_ops(
        ReleaseOpsRequestBody(
            release_id="asrax-r01-cliq-test",
            release_name="cliq-test",
            soak_min=0,
            skip_ui=True,
            skip_sheet=True,
            skip_drive=True,
            skip_cliq=True,
            fixtures=True,
            use_temporal=False,
            post_cliq=False,
            requested_by="tester",
        ),
        authorization=None,
    )
    assert out["status"] == "pending"
    rid = out["request_id"]
    tok = gate.sign_request(rid, "approve")
    started = await _apply_release_decision(
        request_id=rid,
        action="approve",
        actor="admin@asrax.in",
        token=tok,
        notes="test",
        require_token=True,
    )
    assert started["status"] == "started"
    assert started.get("tracking_id")
    req = gate.get_pending_store().get(rid)
    assert req is not None
    assert req.status == "started"


@pytest.mark.asyncio
async def test_non_admin_cannot_approve(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_AGENT_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setenv("QA_AGENT_RELEASE_ADMIN", "admin@asrax.in")
    monkeypatch.setenv("QA_AGENT_ENV", "prod")
    monkeypatch.setenv("QA_AGENT_CLIQ_RELEASE_SECRET", "sec")
    import intelligence.cliq_release_gate as gate

    gate._STORE = PendingReleaseStore(path=tmp_path / "pending.json")
    req = gate.get_pending_store().create(release_id="x")
    tok = gate.sign_request(req.request_id, "approve")
    from fastapi import HTTPException

    from gateway.app import _apply_release_decision

    with pytest.raises(HTTPException) as ei:
        await _apply_release_decision(
            request_id=req.request_id,
            action="approve",
            actor="intruder@asrax.in",
            token=tok,
            require_token=True,
        )
    assert ei.value.status_code == 403
