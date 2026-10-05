"""AsraxReleaseOpsWorkflow activities — phase order + ledger tracing."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

pytest.importorskip("temporalio")

from common.observability.domain_flow import domain_for_activity, domain_for_step
from orchestrator.activities.release_ops import (
    activity_release_ops_cliq_final,
    activity_release_ops_complete,
    activity_release_ops_init,
    activity_release_ops_pack_t0,
    activity_release_ops_publish_drive,
    activity_release_ops_publish_sheet,
    activity_release_ops_stability_score,
    activity_release_ops_ui_suite,
    activity_release_ops_wait_deploy_healthy,
)
from stores import get_ledger


RELEASE_OPS_STEPS = (
    "release_ops_init",
    "release_ops_wait_deploy_healthy",
    "release_ops_ui_suite",
    "release_ops_pack_t0",
    "release_ops_stability_score",
    "release_ops_publish_sheet",
    "release_ops_publish_drive",
    "release_ops_cliq_final",
    "release_ops_complete",
)


def test_release_ops_domain_mapping():
    for step in RELEASE_OPS_STEPS:
        assert domain_for_step(step) == "release_ops"
        assert domain_for_activity(f"activity_{step}") == "release_ops"


@pytest.mark.asyncio
async def test_release_ops_inline_skip_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_AGENT_ARTIFACT_DIR", str(tmp_path))
    result = await asyncio.wait_for(
        _run_skip_path(),
        timeout=60,
    )
    assert result["complete"]["status"] == "COMPLETED"
    assert result["ui"]["decision"] == "SKIPPED"
    assert result["stability"]["band"] == "STABLE"
    assert Path(result["pack_path"]).is_dir()
    summary = json.loads((Path(result["pack_path"]) / "summary.json").read_text(encoding="utf-8"))
    assert summary["phase"] == "FINAL"
    assert summary["workflow"] == "AsraxReleaseOpsWorkflow"
    assert summary.get("artifact_store") == "minio"
    assert "triggered_at" in summary
    assert "workflow_started_at" in summary
    # local pack is under {artifact_dir}/{YYYY-MM-DD}/{release_id}
    assert Path(result["pack_path"]).name == "asrax-r01-wf-test"
    assert "Asrax/Releases" not in str(result["pack_path"])

    run = get_ledger().get(result["tracking_id"])
    assert run is not None
    for step in RELEASE_OPS_STEPS:
        assert step in run.steps, f"missing ledger step {step}"


async def _run_skip_path() -> dict:
    from orchestrator.temporal_api import run_asrax_release_ops_inline

    return await run_asrax_release_ops_inline(
        {
            "release_id": "asrax-r01-wf-test",
            "skip_ui": True,
            "skip_soak": True,
            "skip_sheet": True,
            "skip_drive": True,
            "skip_cliq": True,
            "fixtures": True,
            "soak_min": 0,
            "env": "test",
        }
    )


def test_activity_names_stable():
    """Temporal UI filters by these exact activity names — do not rename lightly."""
    from temporalio.activity import _Definition

    expected = {
        "activity_release_ops_init": activity_release_ops_init,
        "activity_release_ops_wait_deploy_healthy": activity_release_ops_wait_deploy_healthy,
        "activity_release_ops_ui_suite": activity_release_ops_ui_suite,
        "activity_release_ops_pack_t0": activity_release_ops_pack_t0,
        "activity_release_ops_stability_score": activity_release_ops_stability_score,
        "activity_release_ops_publish_sheet": activity_release_ops_publish_sheet,
        "activity_release_ops_publish_drive": activity_release_ops_publish_drive,
        "activity_release_ops_cliq_final": activity_release_ops_cliq_final,
        "activity_release_ops_complete": activity_release_ops_complete,
    }
    for name, fn in expected.items():
        defn = _Definition.must_from_callable(fn)
        assert defn.name == name


def test_workflow_registered_name():
    from orchestrator.workflows.asrax_release_ops import AsraxReleaseOpsWorkflow
    from temporalio.workflow import _Definition as WfDef

    defn = WfDef.must_from_class(AsraxReleaseOpsWorkflow)
    assert defn.name == "AsraxReleaseOpsWorkflow"
