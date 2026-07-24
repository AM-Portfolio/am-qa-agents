"""Temporal task queue — isolated for qa-agent only."""

from __future__ import annotations

import os

DEFAULT_NAMESPACE = "qa-agent"
DEFAULT_QUEUE = "qa-agent-release-v1"

# Never share these with other agents / platform workers.
_FORBIDDEN_QUEUES = frozenset(
    {
        "default",
        "agent-platform",
        "support-agent-v2",
        "support-agent-v2-local-test",
    }
)


def resolve_namespace() -> str:
    return (os.getenv("TEMPORAL_NAMESPACE") or DEFAULT_NAMESPACE).strip() or DEFAULT_NAMESPACE


def resolve_task_queue() -> str:
    return (os.getenv("TEMPORAL_TASK_QUEUE") or DEFAULT_QUEUE).strip() or DEFAULT_QUEUE


def assert_safe_task_queue(queue: str | None = None) -> str:
    q = (queue or resolve_task_queue()).strip()
    if not q.startswith("qa-agent"):
        raise SystemExit(
            f"Refusing Temporal queue '{q}' — qa-agent must use a dedicated qa-agent-* queue"
        )
    if q in _FORBIDDEN_QUEUES:
        raise SystemExit(f"Refusing shared/foreign Temporal queue '{q}'")
    return q
