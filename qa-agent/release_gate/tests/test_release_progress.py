"""Unit tests for release progress enrichment + first-check skip path."""

from __future__ import annotations

import asyncio

import pytest

from intelligence.release_progress import build_progress_from_ledger, enrich_release_view
from orchestrator.activities.release_ops import activity_release_ops_wait_deploy_healthy
from stores import get_ledger


def test_build_progress_empty():
    out = build_progress_from_ledger("missing-tid")
    assert out["phase"] == "unknown"
    assert out["pending"] == []


def test_enrich_after_init_and_wait(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_AGENT_ARTIFACT_DIR", str(tmp_path))
    tid = "qa-progress-test"
    get_ledger().create_run(tracking_id=tid, workflow_id="wf-1")
    get_ledger().upsert_step(tid, "release_ops_init", {"status": "INITIALIZED"})
    get_ledger().upsert_step(
        tid,
        "release_ops_wait_deploy_healthy",
        {"ok": True, "pending": [], "blockers": []},
    )
    view = enrich_release_view({"request_id": "r1", "tracking_id": tid, "status": "started"})
    assert view["phase"] == "release_ops_wait_deploy_healthy"
    assert view["first_check_ok"] is True
    assert view["ui_pct"] == 0


@pytest.mark.asyncio
async def test_wait_deploy_healthy_fixtures_skip():
    out = await activity_release_ops_wait_deploy_healthy(
        {"tracking_id": "qa-wait-skip", "fixtures": True}
    )
    assert out["ok"] is True
    assert out["skipped"] is True
