"""Learning pipeline — Phase 4 (§3.7 / §17). Never auto-promote."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from am_qa_agent.stores.episodes import evaluate_learning, get_episode_store


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FeedbackEvent:
    event_id: str
    tracking_id: str
    episode_id: str | None
    kind: str  # approve.release | reject.release | flaky | false_positive | engineer_rating
    actor: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    at: str = field(default_factory=_now)


@dataclass
class PromotionRecord:
    candidate_id: str
    episode_id: str
    score: float
    human_approved: bool = False
    offline_eval_passed: bool = False
    promoted: bool = False
    blocked_reason: str | None = None
    at: str = field(default_factory=_now)


class LearningStore:
    def __init__(self) -> None:
        self._feedback: list[FeedbackEvent] = []
        self._candidates: dict[str, dict[str, Any]] = {}
        self._promotions: list[PromotionRecord] = []
        self._lock = Lock()

    def ingest(self, event: FeedbackEvent) -> FeedbackEvent:
        with self._lock:
            self._feedback.append(event)
            return event

    def list_feedback(self, tracking_id: str | None = None) -> list[FeedbackEvent]:
        with self._lock:
            if tracking_id:
                return [e for e in self._feedback if e.tracking_id == tracking_id]
            return list(self._feedback)

    def put_candidate(self, candidate_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self._candidates[candidate_id] = payload

    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._candidates.get(candidate_id)

    def record_promotion(self, rec: PromotionRecord) -> PromotionRecord:
        with self._lock:
            self._promotions.append(rec)
            return rec


_LEARNING = LearningStore()


def get_learning_store() -> LearningStore:
    return _LEARNING


def ingest_feedback_event(
    *,
    tracking_id: str,
    kind: str,
    actor: str = "",
    episode_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import uuid

    ev = FeedbackEvent(
        event_id=f"fb-{uuid.uuid4().hex[:10]}",
        tracking_id=tracking_id,
        episode_id=episode_id,
        kind=kind,
        actor=actor,
        payload=payload or {},
    )
    get_learning_store().ingest(ev)
    return {
        "event_id": ev.event_id,
        "tracking_id": tracking_id,
        "kind": kind,
        "actor": actor,
        "episode_id": episode_id,
    }


def evaluate_learning_offline(
    *,
    tracking_id: str,
    episode_payload: dict[str, Any] | None = None,
    hitl: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Offline-style evaluation after HITL.

    score >= 0.7 → policy_candidate (still requires human promotion).
    """
    store = get_episode_store()
    ep = store.by_tracking(tracking_id)
    payload = dict(episode_payload or {})
    if ep:
        payload.setdefault("route", ep.route)
        payload.setdefault("verification", (ep.payload or {}).get("verification"))
        payload.setdefault("matrix", {"summary": (ep.payload or {}).get("matrix_summary")})
        payload.setdefault(
            "change_intent",
            {"change_intent_id": (ep.payload or {}).get("change_intent_id")},
        )
        payload.setdefault("handoff", (ep.payload or {}).get("handoff"))
    if hitl:
        payload["hitl"] = hitl
        if hitl.get("decision") == "approved":
            payload.setdefault("verification", {})
            # bump via evaluate_learning heuristic by marking releasable if approved
            ver = dict(payload.get("verification") or {})
            ver["releasable"] = True
            payload["verification"] = ver
        elif hitl.get("decision") == "rejected":
            ver = dict(payload.get("verification") or {})
            ver["releasable"] = False
            payload["verification"] = ver

    result = evaluate_learning(payload)
    candidate_id = None
    if result.get("policy_candidate"):
        import uuid

        candidate_id = f"pc-{uuid.uuid4().hex[:10]}"
        get_learning_store().put_candidate(
            candidate_id,
            {
                "tracking_id": tracking_id,
                "episode_id": ep.episode_id if ep else None,
                "score": result["score"],
                "hitl": hitl,
                "created_at": _now(),
                "promoted": False,
            },
        )
        result["candidate_id"] = candidate_id
    result["tracking_id"] = tracking_id
    result["episode_id"] = ep.episode_id if ep else None
    return result


def record_promotion(
    *,
    candidate_id: str,
    human_approved: bool,
    offline_eval_passed: bool | None = None,
    actor: str = "",
) -> dict[str, Any]:
    """Dual gate: human AND offline_eval must both be true. Never auto-promote."""
    store = get_learning_store()
    cand = store.get_candidate(candidate_id)
    if not cand:
        return {"promoted": False, "blocked_reason": "unknown_candidate", "candidate_id": candidate_id}

    offline_ok = (
        offline_eval_passed
        if offline_eval_passed is not None
        else float(cand.get("score") or 0) >= 0.7
    )
    promoted = bool(human_approved and offline_ok)
    blocked = None if promoted else (
        "human_gate" if not human_approved else "offline_eval_gate"
    )
    rec = PromotionRecord(
        candidate_id=candidate_id,
        episode_id=str(cand.get("episode_id") or ""),
        score=float(cand.get("score") or 0),
        human_approved=human_approved,
        offline_eval_passed=offline_ok,
        promoted=promoted,
        blocked_reason=blocked,
    )
    store.record_promotion(rec)
    if promoted:
        cand["promoted"] = True
        cand["promoted_by"] = actor
        cand["promoted_at"] = _now()
        store.put_candidate(candidate_id, cand)
    return {
        "candidate_id": candidate_id,
        "promoted": promoted,
        "blocked_reason": blocked,
        "human_approved": human_approved,
        "offline_eval_passed": offline_ok,
        "score": rec.score,
        "note": "catalog SPT write is manual follow-up; gate never bypassed",
    }
