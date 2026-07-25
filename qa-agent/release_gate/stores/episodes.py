"""QA episode store — Phase 3 (in-memory; Postgres later)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class QaEpisode:
    episode_id: str
    tracking_id: str
    repo: str | None = None
    head_sha: str | None = None
    route: str | None = None
    outcome: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    learning_score: float | None = None
    created_at: str = field(default_factory=_now)


class InMemoryEpisodeStore:
    def __init__(self) -> None:
        self._eps: dict[str, QaEpisode] = {}
        self._by_tracking: dict[str, str] = {}
        self._lock = Lock()

    def persist(self, episode: QaEpisode) -> QaEpisode:
        with self._lock:
            self._eps[episode.episode_id] = episode
            self._by_tracking[episode.tracking_id] = episode.episode_id
        # Best-effort durable mirror
        try:
            import os

            store = (os.getenv("QA_AGENT_STORE") or "").lower()
            if store in {"postgres", "postgresql", "pg"} or os.getenv(
                "QA_AGENT_DATABASE_URL"
            ):
                from stores.postgres_store import get_postgres_ledger

                get_postgres_ledger().persist_episode(episode)
            elif store == "sqlite" or os.getenv("QA_AGENT_SQLITE_PATH"):
                from stores.sqlite_store import get_sqlite_ledger

                get_sqlite_ledger().persist_episode(episode)
        except Exception:  # noqa: BLE001
            pass
        return episode

    def get(self, episode_id: str) -> QaEpisode | None:
        with self._lock:
            return self._eps.get(episode_id)

    def by_tracking(self, tracking_id: str) -> QaEpisode | None:
        with self._lock:
            eid = self._by_tracking.get(tracking_id)
            return self._eps.get(eid) if eid else None

    def list_recent(self, limit: int = 20) -> list[QaEpisode]:
        with self._lock:
            items = sorted(self._eps.values(), key=lambda e: e.created_at, reverse=True)
            return items[:limit]


_STORE = InMemoryEpisodeStore()


def get_episode_store() -> InMemoryEpisodeStore:
    return _STORE


def evaluate_learning(episode_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Lightweight episode scoring (Phase 3 stub).

    Full offline job in Phase 4 — here we only compute a heuristic score.
    """
    verification = episode_payload.get("verification") or {}
    matrix = episode_payload.get("matrix") or {}
    route = episode_payload.get("route") or ""
    score = 0.5
    if route == "dev-route":
        score = 0.4 if episode_payload.get("handoff") else 0.2
    else:
        if verification.get("releasable"):
            score += 0.3
        if verification.get("feature_clean"):
            score += 0.1
        if (matrix.get("summary") or {}).get("p0", 0) > 0:
            score += 0.05
        if episode_payload.get("change_intent"):
            score += 0.05
    score = min(1.0, round(score, 3))
    return {
        "score": score,
        "policy_candidate": score >= 0.7,
        "mode": "heuristic_stub",
    }
