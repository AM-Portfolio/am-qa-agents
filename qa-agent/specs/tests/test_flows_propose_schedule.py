"""Propose scenarios + schedule store unit tests."""
from __future__ import annotations

from specs.flows import propose, schedule_store, scheduler


def test_propose_heuristic_for_subscription(monkeypatch):
    monkeypatch.setattr(
        propose,
        "_list_tools",
        lambda service: [
            {
                "name": "getTimeLeft",
                "method": "get",
                "path": "/subscriptions/time-left",
            },
            {
                "name": "deletePlan",
                "method": "delete",
                "path": "/subscriptions/plans/x",
            },
        ],
    )
    monkeypatch.setattr(propose, "_existing_paths", lambda group: set())
    out = propose.propose_scenarios(
        service="am-subscription",
        use_llm=False,
        max_scenarios=5,
    )
    assert out["ok"] is True
    assert out["mode"] == "heuristic"
    assert out["count"] >= 1
    paths = [
        n.get("exact_path")
        for p in out["proposals"]
        for n in (p.get("nodes") or [])
    ]
    assert "/subscriptions/time-left" in paths
    # prod_safe skips delete
    assert "/subscriptions/plans/x" not in paths


def test_schedule_upsert_and_cron_match(tmp_path, monkeypatch):
    monkeypatch.setattr(
        schedule_store.settings,
        "data_dir",
        str(tmp_path),
    )
    import specs.flows.catalog as catalog

    monkeypatch.setattr(
        catalog,
        "get_flow",
        lambda fid: {"id": fid} if fid == "FLOW_SUBSCRIPTION" else None,
    )
    rec = schedule_store.upsert_schedule(
        flow_id="FLOW_SUBSCRIPTION",
        cron="*/5 * * * *",
        env="prod",
        enabled=True,
    )
    assert rec["id"]
    assert rec["cron"] == "*/5 * * * *"
    rows = schedule_store.list_schedules(flow_id="FLOW_SUBSCRIPTION")
    assert len(rows) == 1
    from datetime import datetime, timezone

    now = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)
    assert scheduler._cron_matches_now("*/5 * * * *", now) is True
    assert scheduler._cron_matches_now("1 * * * *", now) is False
