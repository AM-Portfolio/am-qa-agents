"""Hand-seeded data_generator for am-subscription."""
from __future__ import annotations

from typing import Any


def prepare(
    *,
    env: str,
    ctx: dict[str, Any] | None = None,
    assert_only: bool = False,
) -> dict[str, Any]:
    from ui_evidence.scenario_bank.data_prep import prepare_subscription

    return prepare_subscription(
        env=env, ctx=ctx, assert_only=assert_only, refresh=True
    )
