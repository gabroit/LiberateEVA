from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class InstanceRegistry:
    def __init__(self, db_path: str | None = None) -> None:
        self.settings = get_settings()
        self.db_path = db_path or self.settings.instance_registry_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS instance_registry (
                    instance_id TEXT PRIMARY KEY,
                    instance_name TEXT NOT NULL,
                    host TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'online',
                    queue_path TEXT,
                    memory_path TEXT,
                    last_heartbeat TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS instance_messages (
                    id TEXT PRIMARY KEY,
                    from_instance TEXT NOT NULL,
                    to_instance TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def register_instance(
        self,
        instance_id: str,
        instance_name: str,
        host: str,
        port: int,
        queue_path: str | None = None,
        memory_path: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = json.dumps(metadata or {})
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO instance_registry (
                    instance_id, instance_name, host, port, queue_path, memory_path,
                    last_heartbeat, created_at, metadata, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'online')
                ON CONFLICT(instance_id) DO UPDATE SET
                    instance_name = excluded.instance_name,
                    host = excluded.host,
                    port = excluded.port,
                    queue_path = excluded.queue_path,
                    memory_path = excluded.memory_path,
                    last_heartbeat = excluded.last_heartbeat,
                    metadata = excluded.metadata,
                    status = 'online'
                """,
                (
                    instance_id,
                    instance_name,
                    host,
                    port,
                    queue_path,
                    memory_path,
                    now,
                    now,
                    payload,
                ),
            )
            conn.commit()

        return {
            "instance_id": instance_id,
            "instance_name": instance_name,
            "host": host,
            "port": port,
            "status": "online",
            "last_heartbeat": now,
        }

    def heartbeat(
        self,
        instance_id: str,
        *,
        instance_name: str | None = None,
        host: str | None = None,
        port: int | None = None,
        queue_path: str | None = None,
        memory_path: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = _now_iso()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM instance_registry WHERE instance_id = ?",
                (instance_id,),
            ).fetchone()

            if row is None:
                raise HTTPException(status_code=404, detail="Instance not registered")

            conn.execute(
                """
                UPDATE instance_registry
                SET last_heartbeat = ?, status = 'online', instance_name = COALESCE(?, instance_name),
                    host = COALESCE(?, host), port = COALESCE(?, port),
                    queue_path = COALESCE(?, queue_path), memory_path = COALESCE(?, memory_path),
                    metadata = COALESCE(?, metadata)
                WHERE instance_id = ?
                """,
                (
                    now,
                    instance_name,
                    host,
                    port,
                    queue_path,
                    memory_path,
                    json.dumps(metadata or json.loads(row["metadata"] or "{}")),
                    instance_id,
                ),
            )
            conn.commit()

        return {"instance_id": instance_id, "last_heartbeat": now, "status": "online"}

    def list_instances(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM instance_registry ORDER BY last_heartbeat DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def send_message(self, from_instance: str, to_instance: str, scope: str, body: dict[str, Any]) -> dict[str, Any]:
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        payload = json.dumps(body)
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO instance_messages (id, from_instance, to_instance, scope, body, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (msg_id, from_instance, to_instance, scope, payload, now),
            )
            conn.commit()
        return {"message_id": msg_id, "from_instance": from_instance, "to_instance": to_instance, "scope": scope}

    def list_messages(self, instance_id: str, scope: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if scope:
                rows = conn.execute(
                    "SELECT * FROM instance_messages WHERE to_instance = ? AND scope = ? ORDER BY created_at DESC LIMIT ?",
                    (instance_id, scope, limit),
                )
            else:
                rows = conn.execute(
                    "SELECT * FROM instance_messages WHERE to_instance = ? ORDER BY created_at DESC LIMIT ?",
                    (instance_id, limit),
                )
        return [
            {
                "id": row["id"],
                "from_instance": row["from_instance"],
                "to_instance": row["to_instance"],
                "scope": row["scope"],
                "body": json.loads(row["body"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]


router = APIRouter()

def require_webhook_secret(request: Request) -> None:
    settings = get_settings()
    header_value = request.headers.get("X-Webhook-Secret") or request.headers.get("x-webhook-secret")
    if header_value != settings.webhook_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")

@router.post("/heartbeat")
async def heartbeat_endpoint(request: Request) -> dict[str, Any]:
    require_webhook_secret(request)
    payload = await request.json()
    instance_id = payload.get("instance_id")
    if not instance_id:
        raise HTTPException(status_code=400, detail="Missing instance_id")
    registry = InstanceRegistry()
    return registry.heartbeat(
        instance_id=instance_id,
        instance_name=payload.get("instance_name"),
        host=payload.get("host"),
        port=payload.get("port"),
        queue_path=payload.get("queue_path"),
        memory_path=payload.get("memory_path"),
        metadata=payload.get("metadata"),
    )
