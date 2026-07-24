"""Phase 0 classify: CI conclusion → dev-route vs qa-route."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Route = Literal["dev-route", "qa-route"]


@dataclass(frozen=True)
class ClassifyResult:
    route: Route
    reason: str
    ci_conclusion: str | None
    repo: str
    branch: str
    head_sha: str
    base_sha: str | None = None


def _conclusion_from_payload(payload: dict[str, Any]) -> str | None:
    """Accept normalized or GitHub workflow_run shapes."""
    if payload.get("ci_conclusion"):
        return str(payload["ci_conclusion"]).lower()
    wr = payload.get("workflow_run") or {}
    if isinstance(wr, dict) and wr.get("conclusion"):
        return str(wr["conclusion"]).lower()
    check = payload.get("check_suite") or payload.get("check_run") or {}
    if isinstance(check, dict) and check.get("conclusion"):
        return str(check["conclusion"]).lower()
    # Explicit override for manual POST
    if payload.get("force_route") in {"dev-route", "qa-route"}:
        return "success" if payload["force_route"] == "qa-route" else "failure"
    return None


def classify_trigger(payload: dict[str, Any]) -> ClassifyResult:
    repo = str(
        payload.get("repo")
        or (payload.get("repository") or {}).get("full_name")
        or (payload.get("repository") or {}).get("name")
        or "unknown"
    )
    branch = str(
        payload.get("branch")
        or payload.get("ref", "").removeprefix("refs/heads/")
        or (payload.get("pull_request") or {}).get("head", {}).get("ref")
        or "unknown"
    )
    head_sha = str(
        payload.get("head_sha")
        or payload.get("after")
        or (payload.get("pull_request") or {}).get("head", {}).get("sha")
        or (payload.get("workflow_run") or {}).get("head_sha")
        or ""
    )
    base_sha = payload.get("base_sha") or payload.get("before")
    if isinstance(base_sha, str) and base_sha.startswith("0" * 8):
        base_sha = None

    conclusion = _conclusion_from_payload(payload)

    if conclusion is None:
        # Push/PR without CI yet — queue as qa-route smoke only if explicitly allowed
        if payload.get("assume_ci_success"):
            return ClassifyResult(
                route="qa-route",
                reason="assume_ci_success",
                ci_conclusion=None,
                repo=repo,
                branch=branch,
                head_sha=head_sha,
                base_sha=str(base_sha) if base_sha else None,
            )
        return ClassifyResult(
            route="dev-route",
            reason="ci_conclusion_missing",
            ci_conclusion=None,
            repo=repo,
            branch=branch,
            head_sha=head_sha,
            base_sha=str(base_sha) if base_sha else None,
        )

    if conclusion == "success":
        return ClassifyResult(
            route="qa-route",
            reason="ci_success",
            ci_conclusion=conclusion,
            repo=repo,
            branch=branch,
            head_sha=head_sha,
            base_sha=str(base_sha) if base_sha else None,
        )

    return ClassifyResult(
        route="dev-route",
        reason=f"ci_{conclusion}",
        ci_conclusion=conclusion,
        repo=repo,
        branch=branch,
        head_sha=head_sha,
        base_sha=str(base_sha) if base_sha else None,
    )


def idempotency_key(payload: dict[str, Any], *, env: str = "preprod") -> str:
    c = classify_trigger(payload)
    trigger = str(payload.get("trigger_kind") or payload.get("action") or "manual")
    return f"{c.repo}:{c.head_sha or 'nosha'}:{env}:{trigger}"
