"""CI role capped multi-load ACL."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from specs.security.acl import (
    CI_MAX_ITERATIONS,
    CI_MAX_VUS,
    allows_multi_load,
    enforce_execute_load,
)


def test_allows_multi_load_developer_and_ci():
    assert allows_multi_load("developer", "developer") is True
    assert allows_multi_load("ci", "developer") is True
    assert allows_multi_load("agent", "developer") is False
    assert allows_multi_load("ci", "shared") is False


def test_ci_within_caps_ok():
    enforce_execute_load(
        role="ci",
        audience="developer",
        vus=CI_MAX_VUS,
        iterations=CI_MAX_ITERATIONS,
        duration=None,
        preset="ci-load",
    )


def test_ci_rejects_over_caps():
    with pytest.raises(HTTPException) as exc:
        enforce_execute_load(
            role="ci",
            audience="developer",
            vus=CI_MAX_VUS + 1,
            iterations=1,
            duration=None,
            preset=None,
        )
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc2:
        enforce_execute_load(
            role="ci",
            audience="developer",
            vus=1,
            iterations=CI_MAX_ITERATIONS + 1,
            duration=None,
            preset=None,
        )
    assert exc2.value.status_code == 403


def test_ci_rejects_stress_preset():
    with pytest.raises(HTTPException) as exc:
        enforce_execute_load(
            role="ci",
            audience="developer",
            vus=1,
            iterations=1,
            duration=None,
            preset="stress",
        )
    assert exc.value.status_code == 403


def test_agent_still_blocked_from_multi():
    with pytest.raises(HTTPException) as exc:
        enforce_execute_load(
            role="agent",
            audience="developer",
            vus=1,
            iterations=100,
            duration=None,
            preset=None,
        )
    assert exc.value.status_code == 403
