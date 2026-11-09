from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SQLiteTaskQueue:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or "./data/runtime.db"
        self._ensure_parent()
        self.init_db()

    def _ensure_parent(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    run_after TEXT NOT NULL,
                    last_error TEXT
                )
                """
            )
            conn.commit()

    def enqueue(self, task_type: str, payload: dict[str, Any], task_id: str | None = None) -> str:
        task_id = task_id or f"task_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks (id, task_type, payload, status, created_at, updated_at, run_after)
                VALUES (?, ?, ?, 'queued', ?, ?, ?)
                """,
                (task_id, task_type, json.dumps(payload), now, now, now),
            )
            conn.commit()
        return task_id

    def claim_next(self) -> dict[str, Any] | None:
        now = _now_iso()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status = 'queued' AND run_after <= ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (now,),
            ).fetchone()

            if row is None:
                return None

            conn.execute(
                "UPDATE tasks SET status = 'running', updated_at = ? WHERE id = ?",
                (_now_iso(), row["id"]),
            )
            conn.commit()
            return {**dict(row), "payload": json.loads(row["payload"])}

    def mark_complete(self, task_id: str, result: dict[str, Any] | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = 'completed', updated_at = ?, payload = ?, last_error = NULL
                WHERE id = ?
                """,
                (_now_iso(), json.dumps(result or {}), task_id),
            )
            conn.commit()

    def mark_failed(self, task_id: str, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = 'failed', updated_at = ?, last_error = ?
                WHERE id = ?
                """,
                (_now_iso(), error, task_id),
            )
            conn.commit()

    def list_tasks(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
