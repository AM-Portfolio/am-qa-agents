"""HITL release signals — Phase 4 (§3.6)."""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any


SIGNAL_APPROVE_RELEASE = "approve.release"
SIGNAL_REJECT_RELEASE = "reject.release"
SIGNAL_FEEDBACK = "release.feedback"

HITL_SIGNAL_NAMES: frozenset[str] = frozenset(
    {
        SIGNAL_APPROVE_RELEASE,
        SIGNAL_REJECT_RELEASE,
        SIGNAL_FEEDBACK,
    }
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class HitlDecision:
    decision: str  # approved | rejected | timed_out | skipped | pending
    signal: str | None = None
    actor: str = ""
    notes: str = ""
    pdf_docs_ref: str | None = None
    degraded_banner: bool = False
    at: str = field(default_factory=_now)
    meta: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "signal": self.signal,
            "actor": self.actor,
            "notes": self.notes,
            "pdf_docs_ref": self.pdf_docs_ref,
            "degraded_banner": self.degraded_banner,
            "at": self.at,
            "meta": self.meta,
        }


@dataclass
class ReleaseHitlState:
    """Mutable HITL state for Temporal workflow signals."""

    decision: str | None = None  # approved | rejected
    actor: str = ""
    notes: str = ""
    feedback: dict[str, Any] | None = None

    def apply_signal(self, name: str, payload: dict[str, Any] | None = None) -> None:
        body = dict(payload or {})
        if name == SIGNAL_APPROVE_RELEASE:
            self.decision = "approved"
            self.actor = str(body.get("actor") or "")
            self.notes = str(body.get("notes") or "")
        elif name == SIGNAL_REJECT_RELEASE:
            self.decision = "rejected"
            self.actor = str(body.get("actor") or "")
            self.notes = str(body.get("notes") or "")
        elif name == SIGNAL_FEEDBACK:
            self.feedback = body

    def satisfied(self) -> bool:
        return self.decision in {"approved", "rejected"}


class InMemoryHitlStore:
    """Inline / gateway path: pollable decisions keyed by tracking_id."""

    def __init__(self) -> None:
        self._pending: dict[str, dict[str, Any]] = {}
        self._decisions: dict[str, HitlDecision] = {}
        self._lock = Lock()

    def register_awaiting(
        self,
        tracking_id: str,
        *,
        pdf_docs_ref: str | None,
        recommendation: str | None,
        gnx_mode: str | None,
        releasable: bool,
        workflow_id: str | None = None,
    ) -> None:
        with self._lock:
            self._pending[tracking_id] = {
                "pdf_docs_ref": pdf_docs_ref,
                "recommendation": recommendation,
                "gnx_mode": gnx_mode,
                "releasable": releasable,
                "workflow_id": workflow_id,
                "degraded_banner": gnx_mode == "degraded",
                "registered_at": _now(),
            }

    def signal(
        self,
        tracking_id: str,
        signal_name: str,
        payload: dict[str, Any] | None = None,
    ) -> HitlDecision:
        body = dict(payload or {})
        if signal_name == SIGNAL_APPROVE_RELEASE:
            decision = "approved"
        elif signal_name == SIGNAL_REJECT_RELEASE:
            decision = "rejected"
        else:
            raise ValueError(f"unsupported hitl signal: {signal_name}")
        pending = {}
        with self._lock:
            pending = dict(self._pending.get(tracking_id) or {})
            hitl = HitlDecision(
                decision=decision,
                signal=signal_name,
                actor=str(body.get("actor") or ""),
                notes=str(body.get("notes") or ""),
                pdf_docs_ref=pending.get("pdf_docs_ref"),
                degraded_banner=bool(pending.get("degraded_banner")),
                meta={"payload": body},
            )
            self._decisions[tracking_id] = hitl
            self._pending.pop(tracking_id, None)
            return hitl

    def set_decision(self, tracking_id: str, decision: HitlDecision) -> HitlDecision:
        with self._lock:
            self._decisions[tracking_id] = decision
            self._pending.pop(tracking_id, None)
            return decision

    def get_decision(self, tracking_id: str) -> HitlDecision | None:
        with self._lock:
            return self._decisions.get(tracking_id)

    def get_pending(self, tracking_id: str) -> dict[str, Any] | None:
        with self._lock:
            return dict(self._pending[tracking_id]) if tracking_id in self._pending else None


_HITL = InMemoryHitlStore()


def get_hitl_store() -> InMemoryHitlStore:
    return _HITL


def resolve_auto_hitl(
    *,
    releasable: bool,
    gnx_mode: str | None,
    pdf_docs_ref: str | None = None,
) -> HitlDecision | None:
    """
    Local/test auto path. Never auto-approves when degraded.
    Env QA_AGENT_HITL_AUTO_APPROVE=true enables; QA_AGENT_SKIP_HITL skips gate.
    """
    auto = os.getenv("QA_AGENT_HITL_AUTO_APPROVE", "").lower() in {"1", "true", "yes"}
    skip = os.getenv("QA_AGENT_SKIP_HITL", "").lower() in {"1", "true", "yes"}
    if skip:
        return HitlDecision(
            decision="skipped",
            signal=None,
            notes="QA_AGENT_SKIP_HITL",
            pdf_docs_ref=pdf_docs_ref,
            degraded_banner=gnx_mode == "degraded",
        )
    if not auto:
        return None
    if gnx_mode == "degraded":
        return HitlDecision(
            decision="rejected",
            signal=SIGNAL_REJECT_RELEASE,
            actor="auto",
            notes="auto_approve disabled when gnx_mode=degraded",
            pdf_docs_ref=pdf_docs_ref,
            degraded_banner=True,
        )
    if releasable:
        return HitlDecision(
            decision="approved",
            signal=SIGNAL_APPROVE_RELEASE,
            actor="auto",
            notes="QA_AGENT_HITL_AUTO_APPROVE",
            pdf_docs_ref=pdf_docs_ref,
            degraded_banner=False,
        )
    return HitlDecision(
        decision="rejected",
        signal=SIGNAL_REJECT_RELEASE,
        actor="auto",
        notes="auto_reject: not releasable",
        pdf_docs_ref=pdf_docs_ref,
        degraded_banner=False,
    )


async def await_inline_hitl(
    tracking_id: str,
    *,
    pdf_docs_ref: str | None,
    recommendation: str | None,
    gnx_mode: str | None,
    releasable: bool,
    workflow_id: str | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Poll HitlStore until signal or timeout (inline mode)."""
    store = get_hitl_store()
    auto = resolve_auto_hitl(
        releasable=releasable, gnx_mode=gnx_mode, pdf_docs_ref=pdf_docs_ref
    )
    if auto is not None:
        return store.set_decision(tracking_id, auto).as_dict()

    store.register_awaiting(
        tracking_id,
        pdf_docs_ref=pdf_docs_ref,
        recommendation=recommendation,
        gnx_mode=gnx_mode,
        releasable=releasable,
        workflow_id=workflow_id,
    )
    if timeout_seconds is None:
        timeout_seconds = float(os.getenv("QA_AGENT_HITL_TIMEOUT_SECONDS", "1"))
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while time.monotonic() < deadline:
        dec = store.get_decision(tracking_id)
        if dec:
            return dec.as_dict()
        await asyncio.sleep(0.05)
    timed = HitlDecision(
        decision="timed_out",
        notes=f"HITL SLA exceeded ({timeout_seconds}s)",
        pdf_docs_ref=pdf_docs_ref,
        degraded_banner=gnx_mode == "degraded",
    )
    return store.set_decision(tracking_id, timed).as_dict()
