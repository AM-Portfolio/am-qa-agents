"""Durable Postgres ledger — QA_AGENT_STORE=postgres (+ QA_AGENT_DATABASE_URL).

Shares infra Postgres with Specs (SPT). Tables are prefixed `qa_agent_*` so they
never collide with SPT `runs` / `idempotency_keys` in the same database.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from stores.ledger import WorkflowRun


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_database_url() -> str:
    url = (
        os.getenv("QA_AGENT_DATABASE_URL")
        or os.getenv("SPT_DATABASE_URL")
        or os.getenv("SUPPORT_AGENT_DATABASE_URL")
        or ""
    ).strip()
    if not url:
        raise RuntimeError(
            "QA_AGENT_DATABASE_URL (or SPT_DATABASE_URL) required when QA_AGENT_STORE=postgres"
        )
    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    return url


class PostgresWorkflowLedger:
    def __init__(self, url: str | None = None) -> None:
        self._url = url or resolve_database_url()
        self._engine: Engine = create_engine(
            self._url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            future=True,
        )
        self._lock = Lock()
        self._init()

    def _init(self) -> None:
        with self._lock:
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS qa_agent_runs (
                          tracking_id TEXT PRIMARY KEY,
                          workflow_id TEXT NOT NULL,
                          status TEXT NOT NULL,
                          route TEXT,
                          steps_json TEXT NOT NULL DEFAULT '{}',
                          meta_json TEXT NOT NULL DEFAULT '{}',
                          created_at TEXT NOT NULL,
                          updated_at TEXT NOT NULL
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS qa_agent_idem (
                          idem_key TEXT PRIMARY KEY,
                          tracking_id TEXT NOT NULL
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS qa_agent_episodes (
                          episode_id TEXT PRIMARY KEY,
                          tracking_id TEXT NOT NULL,
                          repo TEXT,
                          head_sha TEXT,
                          route TEXT,
                          outcome TEXT,
                          payload_json TEXT NOT NULL DEFAULT '{}',
                          learning_score DOUBLE PRECISION,
                          created_at TEXT NOT NULL
                        )
                        """
                    )
                )

    def create_run(
        self,
        *,
        tracking_id: str,
        workflow_id: str,
        idempotency_key: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        with self._lock:
            with self._engine.begin() as conn:
                if idempotency_key:
                    row = conn.execute(
                        text(
                            "SELECT tracking_id FROM qa_agent_idem WHERE idem_key=:k"
                        ),
                        {"k": idempotency_key},
                    ).mappings().first()
                    if row:
                        existing = self._load(conn, row["tracking_id"])
                        if existing:
                            return existing
                now = _now()
                # Gateway + activity_release_ops_init both call create_run; stay idempotent.
                conn.execute(
                    text(
                        """
                        INSERT INTO qa_agent_runs
                          (tracking_id,workflow_id,status,route,steps_json,meta_json,created_at,updated_at)
                        VALUES
                          (:tid,:wid,'running',NULL,'{}',:meta,:now,:now)
                        ON CONFLICT (tracking_id) DO NOTHING
                        """
                    ),
                    {
                        "tid": tracking_id,
                        "wid": workflow_id,
                        "meta": json.dumps(meta or {}),
                        "now": now,
                    },
                )
                if idempotency_key:
                    conn.execute(
                        text(
                            """
                            INSERT INTO qa_agent_idem(idem_key,tracking_id)
                            VALUES (:k,:tid)
                            ON CONFLICT (idem_key) DO UPDATE SET tracking_id=EXCLUDED.tracking_id
                            """
                        ),
                        {"k": idempotency_key, "tid": tracking_id},
                    )
                existing = self._load(conn, tracking_id)
                if existing:
                    return existing
                return WorkflowRun(
                    tracking_id=tracking_id,
                    workflow_id=workflow_id,
                    meta=meta or {},
                    created_at=now,
                    updated_at=now,
                )

    def _load(self, conn: Any, tracking_id: str) -> WorkflowRun | None:
        row = conn.execute(
            text("SELECT * FROM qa_agent_runs WHERE tracking_id=:tid"),
            {"tid": tracking_id},
        ).mappings().first()
        if not row:
            return None
        return WorkflowRun(
            tracking_id=row["tracking_id"],
            workflow_id=row["workflow_id"],
            status=row["status"],
            route=row["route"],
            steps=json.loads(row["steps_json"] or "{}"),
            meta=json.loads(row["meta_json"] or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def upsert_step(self, tracking_id: str, step: str, payload: dict[str, Any]) -> None:
        workflow_id = ""
        with self._lock:
            with self._engine.begin() as conn:
                run = self._load(conn, tracking_id)
                if not run:
                    return
                workflow_id = run.workflow_id
                run.steps[step] = {**payload, "at": _now()}
                conn.execute(
                    text(
                        """
                        UPDATE qa_agent_runs
                        SET steps_json=:steps, updated_at=:now
                        WHERE tracking_id=:tid
                        """
                    ),
                    {
                        "steps": json.dumps(run.steps),
                        "now": _now(),
                        "tid": tracking_id,
                    },
                )
        try:
            from common.observability.domain_flow import emit_step_log

            emit_step_log(
                tracking_id=tracking_id,
                step=step,
                payload=payload,
                workflow_id=workflow_id,
            )
        except Exception:  # noqa: BLE001
            pass

    def set_route(self, tracking_id: str, route: str) -> None:
        with self._lock:
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE qa_agent_runs
                        SET route=:route, updated_at=:now
                        WHERE tracking_id=:tid
                        """
                    ),
                    {"route": route, "now": _now(), "tid": tracking_id},
                )

    def complete(self, tracking_id: str, status: str = "completed") -> None:
        with self._lock:
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE qa_agent_runs
                        SET status=:status, updated_at=:now
                        WHERE tracking_id=:tid
                        """
                    ),
                    {"status": status, "now": _now(), "tid": tracking_id},
                )

    def get(self, tracking_id: str) -> WorkflowRun | None:
        with self._lock:
            with self._engine.connect() as conn:
                return self._load(conn, tracking_id)

    def find_by_workflow_id(self, workflow_id: str) -> WorkflowRun | None:
        wid = (workflow_id or "").strip()
        if not wid:
            return None
        with self._lock:
            with self._engine.connect() as conn:
                row = conn.execute(
                    text(
                        """
                        SELECT tracking_id FROM qa_agent_runs
                        WHERE workflow_id=:wid
                        ORDER BY updated_at DESC
                        LIMIT 1
                        """
                    ),
                    {"wid": wid},
                ).mappings().first()
                return self._load(conn, row["tracking_id"]) if row else None

    def find_by_idempotency(self, key: str) -> WorkflowRun | None:
        with self._lock:
            with self._engine.connect() as conn:
                row = conn.execute(
                    text("SELECT tracking_id FROM qa_agent_idem WHERE idem_key=:k"),
                    {"k": key},
                ).mappings().first()
                return self._load(conn, row["tracking_id"]) if row else None

    def persist_episode(self, episode: Any) -> None:
        with self._lock:
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO qa_agent_episodes
                          (episode_id,tracking_id,repo,head_sha,route,outcome,payload_json,learning_score,created_at)
                        VALUES
                          (:eid,:tid,:repo,:sha,:route,:outcome,:payload,:score,:created)
                        ON CONFLICT (episode_id) DO UPDATE SET
                          tracking_id=EXCLUDED.tracking_id,
                          repo=EXCLUDED.repo,
                          head_sha=EXCLUDED.head_sha,
                          route=EXCLUDED.route,
                          outcome=EXCLUDED.outcome,
                          payload_json=EXCLUDED.payload_json,
                          learning_score=EXCLUDED.learning_score,
                          created_at=EXCLUDED.created_at
                        """
                    ),
                    {
                        "eid": episode.episode_id,
                        "tid": episode.tracking_id,
                        "repo": episode.repo,
                        "sha": episode.head_sha,
                        "route": episode.route,
                        "outcome": episode.outcome,
                        "payload": json.dumps(episode.payload or {}),
                        "score": episode.learning_score,
                        "created": episode.created_at,
                    },
                )


_INSTANCE: PostgresWorkflowLedger | None = None


def get_postgres_ledger(url: str | None = None) -> PostgresWorkflowLedger:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = PostgresWorkflowLedger(url)
    return _INSTANCE
