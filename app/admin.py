from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings
from app.queue import SQLiteTaskQueue
from app.registry import InstanceRegistry, require_webhook_secret

router = APIRouter(prefix="/admin")


@router.post("/deploy")
async def deploy_instance(request: Request) -> dict[str, Any]:
    require_webhook_secret(request)
    settings = get_settings()
    payload = await request.json()

    instance_id = payload.get("instance_id") or f"instance_{uuid.uuid4().hex[:12]}"
    instance_name = payload.get("instance_name") or f"instance-{instance_id}"
    host = payload.get("host") or settings.host
    port = int(payload.get("port") or settings.port)

    queue_path = payload.get("queue_path") or f"./data/instances/{instance_id}/queue.db"
    memory_path = payload.get("memory_path") or f"./data/instances/{instance_id}/chroma"

    registry = InstanceRegistry()
    registry.register_instance(
        instance_id=instance_id,
        instance_name=instance_name,
        host=host,
        port=port,
        queue_path=queue_path,
        memory_path=memory_path,
        metadata={"operator_deployed": True}
    )

    SQLiteTaskQueue(queue_path).init_db()

    return {
        "status": "deployed",
        "operator_deployed": True,
        "instance_id": instance_id,
        "instance_name": instance_name,
        "host": host,
        "port": port,
        "queue_path": queue_path,
        "memory_path": memory_path,
        "autonomous_self_replication": False,
    }


@router.post("/message")
async def send_message(request: Request) -> dict[str, Any]:
    require_webhook_secret(request)
    payload = await request.json()
    from_instance = payload.get("from_instance")
    to_instance = payload.get("to_instance")
    scope = payload.get("scope") or "default"
    body = payload.get("body") or {}

    if not from_instance or not to_instance:
        raise HTTPException(status_code=400, detail="from_instance and to_instance are required")

    registry = InstanceRegistry()
    result = registry.send_message(from_instance, to_instance, scope, body)
    return {"status": "sent", "message": result}
