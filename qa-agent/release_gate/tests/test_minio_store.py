"""MinIO release pack path naming (separate from am-infra Drive)."""

from __future__ import annotations

from datetime import datetime, timezone

from adapters.minio_store import dated_object_name, object_prefix


def test_object_prefix_and_dated_name():
    triggered = datetime(2026, 8, 5, 19, 40, tzinfo=timezone.utc)
    wf = datetime(2026, 8, 5, 19, 42, tzinfo=timezone.utc)
    prefix = object_prefix(triggered_at=triggered, release_id="asrax-r01-20260805-abc")
    assert prefix == "asrax-release-ops/2026/2026-08-05/asrax-r01-20260805-abc"
    name = dated_object_name(
        release_id="asrax-r01-20260805-abc",
        triggered_stamp="20260805T1940Z",
        workflow_stamp="20260805T1942Z",
        stem="master-release-report",
        suffix=".pdf",
    )
    assert name.startswith("asrax-r01-20260805-abc_triggered-20260805T1940Z_workflow-")
    assert name.endswith("_master-release-report.pdf")
    assert "Asrax/Releases" not in prefix
