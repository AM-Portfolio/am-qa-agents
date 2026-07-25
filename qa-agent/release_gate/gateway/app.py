"""qa-agent gateway — GitHub webhook + manual release-readiness start."""

from __future__ import annotations

from composition.env_bootstrap import load_env

load_env()

import hashlib
import hmac
import os
import uuid
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from composition.identity import AGENT_ID, DISPLAY_NAME, __version__
from common.observability.logging_setup import bind_tracking_id, get_logger, tracking_context
from common.observability.tracing import current_trace_ids, set_span_tracking_id
from intelligence import classify_trigger, idempotency_key
from intelligence.trigger_policy import evaluate_ci_merge
from learning import record_promotion
from orchestrator import temporal_api as tapi
from orchestrator.hitl import HITL_SIGNAL_NAMES, get_hitl_store
from orchestrator.rbac import authorize_hitl_actor
from observability.metrics import render_metrics
from stores import get_episode_store, get_ledger

app = FastAPI(title=DISPLAY_NAME, version=__version__)
LOG = get_logger("qa.release")


def _require_token(authorization: str | None) -> None:
    expected = (os.getenv("QA_AGENT_GATEWAY_TOKEN") or "").strip()
    if not expected:
        # local/dev: allow if unset
        if (os.getenv("QA_AGENT_ENV") or "local").lower() in {"local", "dev", "test"}:
            return
        raise HTTPException(503, "QA_AGENT_GATEWAY_TOKEN not configured")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Bearer token required")
    token = authorization.split(" ", 1)[1].strip()
    if token != expected:
        raise HTTPException(403, "invalid token")


def _verify_github_signature(body: bytes, signature: str | None) -> None:
    secret = (os.getenv("GITHUB_WEBHOOK_SECRET") or "").encode()
    if not secret:
        return
    if not signature or not signature.startswith("sha256="):
        raise HTTPException(401, "missing X-Hub-Signature-256")
    digest = hmac.new(secret, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(f"sha256={digest}", signature):
        raise HTTPException(403, "bad signature")


class ReleaseReadinessBody(BaseModel):
    repo: str
    branch: str
    head_sha: str
    base_sha: str | None = None
    ci_conclusion: str | None = "success"
    trigger_kind: str = "manual"
    environment: str = "preprod"
    service: str | None = None
    target_url: str | None = None
    profile: str | None = None
    callback_url: str | None = None
    assume_ci_success: bool = False
    force_route: str | None = None
    use_temporal: bool = Field(
        default=True,
        description="If false, run activities inline (no Temporal worker required)",
    )


class HitlSignalBody(BaseModel):
    actor: str = "operator"
    notes: str = ""
    request_id: str | None = None
    roles: list[str] = Field(default_factory=list)


class PromotionBody(BaseModel):
    candidate_id: str
    human_approved: bool
    offline_eval_passed: bool | None = None
    actor: str = "operator"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": AGENT_ID, "version": __version__}


@app.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    return PlainTextResponse(render_metrics(), media_type="text/plain; version=0.0.4")


@app.post("/v2/workflows/release-readiness")
async def start_release_readiness(
    body: ReleaseReadinessBody,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_token(authorization)
    if body.trigger_kind == "ci_master_merge":
        allowed, reason = evaluate_ci_merge(
            repo=body.repo,
            branch=body.branch,
            service=body.service,
        )
        if not allowed:
            return {
                "skipped": True,
                "reason": reason,
                "repo": body.repo,
                "branch": body.branch,
                "service": body.service,
            }
    payload = body.model_dump()
    key = idempotency_key(payload, env=body.environment)
    ledger = get_ledger()
    existing = ledger.find_by_idempotency(key)
    if existing:
        return {
            "tracking_id": existing.tracking_id,
            "workflow_id": existing.workflow_id,
            "deduplicated": True,
            "status": existing.status,
        }

    tracking_id = f"qa-{uuid.uuid4().hex[:12]}"
    workflow_id = f"release-readiness-{body.repo.replace('/', '-')}-{body.head_sha[:12]}-{body.environment}"
    with tracking_context(tracking_id):
        bind_tracking_id(tracking_id)
        set_span_tracking_id(tracking_id)
        ledger.create_run(
            tracking_id=tracking_id,
            workflow_id=workflow_id,
            idempotency_key=key,
            meta={"env": body.environment, "trigger_kind": body.trigger_kind},
        )
        args = {
            "tracking_id": tracking_id,
            "trigger": payload,
            **payload,
        }
        LOG.info(
            "release.start service=%s env=%s repo=%s sha=%s workflow_id=%s",
            body.service,
            body.environment,
            body.repo,
            body.head_sha[:12],
            workflow_id,
            extra={"event": "release.start", "workflow_id": workflow_id},
        )

        def _response(body_dict: dict[str, Any], *, status_code: int = 200) -> JSONResponse:
            tid, sid = current_trace_ids()
            headers = {
                "X-Correlation-Id": tracking_id,
                "X-Tracking-Id": tracking_id,
            }
            if tid:
                headers["X-Trace-Id"] = tid
            if sid:
                headers["X-Span-Id"] = sid
            return JSONResponse(body_dict, status_code=status_code, headers=headers)

        if body.use_temporal and os.getenv("QA_AGENT_FORCE_INLINE", "").lower() not in {"1", "true"}:
            try:
                wf_id = await tapi.start_release_readiness(
                    tracking_id=tracking_id,
                    workflow_id=workflow_id,
                    args=args,
                )
                LOG.info(
                    "release.temporal_started workflow_id=%s",
                    wf_id,
                    extra={"event": "release.temporal_started", "workflow_id": wf_id},
                )
                return _response(
                    {
                        "tracking_id": tracking_id,
                        "workflow_id": wf_id,
                        "mode": "temporal",
                        "classify_preview": classify_trigger(payload).__dict__,
                    }
                )
            except Exception as exc:  # noqa: BLE001 — fall back for local MVP
                LOG.warning(
                    "release.temporal_fallback error=%s",
                    exc,
                    extra={"event": "release.temporal_fallback"},
                )
                outcome = await tapi.run_release_readiness_inline(args)
                return _response(
                    {
                        "tracking_id": tracking_id,
                        "workflow_id": workflow_id,
                        "mode": "inline_fallback",
                        "temporal_error": str(exc),
                        "outcome": outcome,
                    }
                )

        outcome = await tapi.run_release_readiness_inline(args)
        LOG.info(
            "release.inline_complete status=%s",
            (outcome or {}).get("status"),
            extra={"event": "release.inline_complete"},
        )
        return _response(
            {
                "tracking_id": tracking_id,
                "workflow_id": workflow_id,
                "mode": "inline",
                "outcome": outcome,
            }
        )


@app.post("/webhooks/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
) -> dict[str, Any]:
    body = await request.body()
    _verify_github_signature(body, x_hub_signature_256)
    data = await request.json()
    event = (x_github_event or "").lower()

    # Normalize to release-readiness fields
    repo = (data.get("repository") or {}).get("full_name") or "unknown"
    branch = "unknown"
    head_sha = ""
    ci_conclusion = None
    trigger_kind = event or "github"

    if event == "workflow_run":
        wr = data.get("workflow_run") or {}
        head_sha = str(wr.get("head_sha") or "")
        branch = str(wr.get("head_branch") or "")
        ci_conclusion = wr.get("conclusion")
        # Only act on completed runs
        if wr.get("status") and wr.get("status") != "completed":
            return {"ignored": True, "reason": "workflow_run_not_completed"}
    elif event in {"push"}:
        head_sha = str(data.get("after") or "")
        ref = str(data.get("ref") or "")
        branch = ref.removeprefix("refs/heads/")
    elif event == "pull_request":
        pr = data.get("pull_request") or {}
        head_sha = str((pr.get("head") or {}).get("sha") or "")
        branch = str((pr.get("head") or {}).get("ref") or "")
    else:
        return {"ignored": True, "reason": f"unsupported_event:{event}"}

    normalized = ReleaseReadinessBody(
        repo=repo,
        branch=branch,
        head_sha=head_sha,
        ci_conclusion=ci_conclusion,
        trigger_kind=trigger_kind,
        assume_ci_success=event in {"push", "pull_request"} and ci_conclusion is None,
        use_temporal=True,
    )
    # Webhook is already authenticated via HMAC; reuse gateway token for internal call
    token = (os.getenv("QA_AGENT_GATEWAY_TOKEN") or "").strip()
    auth = f"Bearer {token}" if token else None
    return await start_release_readiness(normalized, authorization=auth)


@app.get("/v2/runs/{tracking_id}")
def get_run(tracking_id: str) -> dict[str, Any]:
    run = get_ledger().get(tracking_id)
    if not run:
        raise HTTPException(404, "not found")
    pending = get_hitl_store().get_pending(tracking_id)
    decision = get_hitl_store().get_decision(tracking_id)
    episode = get_episode_store().by_tracking(tracking_id)
    return {
        "tracking_id": run.tracking_id,
        "workflow_id": run.workflow_id,
        "status": run.status,
        "route": run.route,
        "steps": run.steps,
        "meta": run.meta,
        "hitl_pending": pending,
        "hitl_decision": decision.as_dict() if decision else None,
        "episode_id": episode.episode_id if episode else None,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


@app.post("/v2/runs/{tracking_id}/signals/{signal_name}")
async def signal_run(
    tracking_id: str,
    signal_name: str,
    body: HitlSignalBody,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Send approve.release / reject.release (or release.feedback)."""
    _require_token(authorization)
    if signal_name not in HITL_SIGNAL_NAMES:
        raise HTTPException(400, f"unsupported signal: {signal_name}")
    authz = authorize_hitl_actor(body.actor, body.roles)
    if not authz.get("allowed"):
        raise HTTPException(403, f"HITL RBAC denied: {authz}")
    run = get_ledger().get(tracking_id)
    if not run:
        raise HTTPException(404, "not found")
    payload = body.model_dump()
    # Inline store always records; Temporal signal best-effort when worker up
    decision = None
    if signal_name in {"approve.release", "reject.release"}:
        decision = get_hitl_store().signal(tracking_id, signal_name, payload)
    temporal_ok = False
    temporal_error = None
    try:
        await tapi.signal_release_hitl(
            workflow_id=run.workflow_id,
            signal_name=signal_name,
            payload=payload,
        )
        temporal_ok = True
    except Exception as exc:  # noqa: BLE001
        temporal_error = str(exc)
    get_ledger().upsert_step(
        tracking_id,
        f"signal:{signal_name}",
        {"payload": payload, "temporal_ok": temporal_ok, "temporal_error": temporal_error},
    )
    return {
        "tracking_id": tracking_id,
        "signal": signal_name,
        "decision": decision.as_dict() if decision else None,
        "temporal_ok": temporal_ok,
        "temporal_error": temporal_error,
    }


@app.post("/v2/learning/promote")
async def promote_candidate(
    body: PromotionBody,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Dual-gate promotion — human + offline eval; never auto."""
    _require_token(authorization)
    return record_promotion(
        candidate_id=body.candidate_id,
        human_approved=body.human_approved,
        offline_eval_passed=body.offline_eval_passed,
        actor=body.actor,
    )


def main() -> None:
    import uvicorn

    host = os.getenv("QA_AGENT_HOST", "0.0.0.0")
    port = int(os.getenv("QA_AGENT_PORT", "8150"))
    uvicorn.run("gateway.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
