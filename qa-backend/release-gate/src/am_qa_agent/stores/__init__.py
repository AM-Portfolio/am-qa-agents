"""Store factory — memory (default) or sqlite durable."""

from __future__ import annotations

import os
from typing import Any

from am_qa_agent.stores.ledger import InMemoryWorkflowLedger, WorkflowRun, get_ledger as _memory_ledger
from am_qa_agent.stores.episodes import (
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


def get_ledger() -> Any:
    global _LEDGER
    if _LEDGER is not None:
        return _LEDGER
    mode = (os.getenv("QA_AGENT_STORE") or "memory").lower()
    if mode == "sqlite" or os.getenv("QA_AGENT_SQLITE_PATH"):
        from am_qa_agent.stores.sqlite_store import get_sqlite_ledger

        _LEDGER = get_sqlite_ledger()
    else:
        _LEDGER = _memory_ledger()
    return _LEDGER


def get_episode_store() -> InMemoryEpisodeStore:
    from am_qa_agent.stores.episodes import get_episode_store as _ep

    return _ep()
