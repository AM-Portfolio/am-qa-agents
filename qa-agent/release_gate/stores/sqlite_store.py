"""Durable SQLite ledger — default when QA_AGENT_STORE=sqlite."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from stores.ledger import WorkflowRun


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteWorkflowLedger:
    def __init__(self, path: str | None = None) -> None:
        self._path = path or os.getenv("QA_AGENT_SQLITE_PATH") or "artifacts/qa-agent.db"
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._lock:
            conn = self._conn()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS runs (
                      tracking_id TEXT PRIMARY KEY,
                      workflow_id TEXT NOT NULL,
                      status TEXT NOT NULL,
                      route TEXT,
                      steps_json TEXT NOT NULL DEFAULT '{}',
                      meta_json TEXT NOT NULL DEFAULT '{}',
                      created_at TEXT NOT NULL,
                      updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS idem (
                      idem_key TEXT PRIMARY KEY,
                      tracking_id TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS episodes (
                      episode_id TEXT PRIMARY KEY,
                      tracking_id TEXT NOT NULL,
                      repo TEXT,
                      head_sha TEXT,
                      route TEXT,
                      outcome TEXT,
                      payload_json TEXT NOT NULL DEFAULT '{}',
                      learning_score REAL,
                      created_at TEXT NOT NULL
                    );
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def create_run(
        self,
        *,
        tracking_id: str,
        workflow_id: str,
        idempotency_key: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        with self._lock:
            conn = self._conn()
            try:
                if idempotency_key:
                    row = conn.execute(
                        "SELECT tracking_id FROM idem WHERE idem_key=?", (idempotency_key,)
                    ).fetchone()
                    if row:
                        existing = self._load(conn, row["tracking_id"])
                        if existing:
                            return existing
                # Gateway + activity_release_ops_init both call create_run; stay idempotent.
                existing = self._load(conn, tracking_id)
                if existing:
                    return existing
                now = _now()
                conn.execute(
                    "INSERT OR IGNORE INTO runs(tracking_id,workflow_id,status,route,steps_json,meta_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                    (
                        tracking_id,
                        workflow_id,
                        "running",
                        None,
                        "{}",
                        json.dumps(meta or {}),
                        now,
                        now,
                    ),
                )
                if idempotency_key:
                    conn.execute(
                        "INSERT OR REPLACE INTO idem(idem_key,tracking_id) VALUES(?,?)",
                        (idempotency_key, tracking_id),
                    )
                conn.commit()
                loaded = self._load(conn, tracking_id)
                if loaded:
                    return loaded
                return WorkflowRun(
                    tracking_id=tracking_id,
                    workflow_id=workflow_id,
                    meta=meta or {},
                    created_at=now,
                    updated_at=now,
                )
            finally:
                conn.close()

    def _load(self, conn: sqlite3.Connection, tracking_id: str) -> WorkflowRun | None:
        row = conn.execute("SELECT * FROM runs WHERE tracking_id=?", (tracking_id,)).fetchone()
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
            conn = self._conn()
            try:
                run = self._load(conn, tracking_id)
                if not run:
                    return
                workflow_id = run.workflow_id
                run.steps[step] = {**payload, "at": _now()}
                conn.execute(
                    "UPDATE runs SET steps_json=?, updated_at=? WHERE tracking_id=?",
                    (json.dumps(run.steps), _now(), tracking_id),
                )
                conn.commit()
            finally:
                conn.close()
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
            conn = self._conn()
            try:
                conn.execute(
                    "UPDATE runs SET route=?, updated_at=? WHERE tracking_id=?",
                    (route, _now(), tracking_id),
                )
                conn.commit()
            finally:
                conn.close()

    def complete(self, tracking_id: str, status: str = "completed") -> None:
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    "UPDATE runs SET status=?, updated_at=? WHERE tracking_id=?",
                    (status, _now(), tracking_id),
                )
                conn.commit()
            finally:
                conn.close()

    def get(self, tracking_id: str) -> WorkflowRun | None:
        with self._lock:
            conn = self._conn()
            try:
                return self._load(conn, tracking_id)
            finally:
                conn.close()

    def find_by_idempotency(self, key: str) -> WorkflowRun | None:
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT tracking_id FROM idem WHERE idem_key=?", (key,)
                ).fetchone()
                return self._load(conn, row["tracking_id"]) if row else None
            finally:
                conn.close()

    def persist_episode(self, episode: Any) -> None:
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO episodes
                    (episode_id,tracking_id,repo,head_sha,route,outcome,payload_json,learning_score,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?)""",
                    (
                        episode.episode_id,
                        episode.tracking_id,
                        episode.repo,
                        episode.head_sha,
                        episode.route,
                        episode.outcome,
                        json.dumps(episode.payload or {}),
                        episode.learning_score,
                        episode.created_at,
                    ),
                )
                conn.commit()
            finally:
                conn.close()


_INSTANCE: SqliteWorkflowLedger | None = None


def get_sqlite_ledger(path: str | None = None) -> SqliteWorkflowLedger:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = SqliteWorkflowLedger(path)
    return _INSTANCE
