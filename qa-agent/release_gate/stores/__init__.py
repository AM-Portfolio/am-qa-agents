"""Store factory — memory | sqlite | postgres (shared infra DB)."""

from __future__ import annotations

import os
from typing import Any

from stores.ledger import InMemoryWorkflowLedger, WorkflowRun, get_ledger as _memory_ledger
from stores.episodes import (
    InMemoryEpisodeStore,
    QaEpisode,
    evaluate_learning,
)

__all__ = [
    "InMemoryWorkflowLedger",
    "WorkflowRun",
    "get_ledger",
    "InMemoryEpisodeStore",
    "QaEpisode",
    "evaluate_learning",
    "get_episode_store",
]

_LEDGER: Any = None


def _store_mode() -> str:
    mode = (os.getenv("QA_AGENT_STORE") or "").strip().lower()
    if mode:
        return mode
    if os.getenv("QA_AGENT_DATABASE_URL") or os.getenv("SPT_DATABASE_URL"):
        return "postgres"
    if os.getenv("QA_AGENT_SQLITE_PATH"):
        return "sqlite"
    return "memory"


def get_ledger() -> Any:
    global _LEDGER
    if _LEDGER is not None:
        return _LEDGER
    mode = _store_mode()
    if mode in {"postgres", "postgresql", "pg"}:
        from stores.postgres_store import get_postgres_ledger

        _LEDGER = get_postgres_ledger()
    elif mode == "sqlite" or os.getenv("QA_AGENT_SQLITE_PATH"):
        from stores.sqlite_store import get_sqlite_ledger

        _LEDGER = get_sqlite_ledger()
    else:
        _LEDGER = _memory_ledger()
    return _LEDGER


def get_episode_store() -> InMemoryEpisodeStore:
    from stores.episodes import get_episode_store as _ep

    return _ep()
