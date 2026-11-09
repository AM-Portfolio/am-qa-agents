"""Hand-seeded prep for am-identity (login JWT)."""
from __future__ import annotations

from typing import Any


def prepare(
    *,
    env: str,
    ctx: dict[str, Any] | None = None,
    assert_only: bool = False,
) -> dict[str, Any]:
    from ui_evidence.scenario_bank.data_prep import prepare_identity

    return prepare_identity(env=env, ctx=ctx, assert_only=assert_only, refresh=True)
