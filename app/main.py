from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from app.admin import router as admin_router
from app.agent_runtime import AgentRuntime
from app.config import get_settings
from app.queue import SQLiteTaskQueue
from app.registry import InstanceRegistry, require_webhook_secret, router as registry_router

settings = get_settings()
queue = SQLiteTaskQueue(settings.sqlite_path)
runtime = AgentRuntime(queue)
app = FastAPI(title="LiberateEVA")

app.include_router(admin_router)
app.include_router(registry_router)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "app_name": settings.app_name, "autonomous_self_replication": False}


@app.post("/webhook")
async def webhook(request: Request) -> dict[str, Any]:
    require_webhook_secret(request)
    payload = await request.json()
    instruction = payload.get("instruction") or payload.get("text")
    if not instruction:
        raise HTTPException(status_code=400, detail="instruction is required")
    task_id = await runtime.ingest_instruction(str(instruction), {"source": "webhook"})
    return {"status": "accepted", "task_id": task_id}


@app.get("/state/export")
async def state_export(request: Request) -> dict[str, Any]:
    require_webhook_secret(request)
    snapshot = {
        "runtime_db": settings.sqlite_path,
        "tasks": queue.list_tasks(limit=200),
        "exported_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
    }
    return snapshot


@app.post("/state/import")
async def state_import(request: Request) -> dict[str, Any]:
    require_webhook_secret(request)
    payload = await request.json()
    if not payload.get("tasks"):
        raise HTTPException(status_code=400, detail="tasks payload required for import")
    for task in payload["tasks"]:
        queue.enqueue(task.get("task_type", "instruction"), task.get("payload", {}), task_id=task.get("id"))
    return {"status": "imported", "count": len(payload["tasks"]), "autonomous_self_replication": False}


@app.get("/admin/instances")
async def list_instances(request: Request) -> dict[str, Any]:
    require_webhook_secret(request)
    registry = InstanceRegistry()
    return {"instances": registry.list_instances()}


@app.on_event("startup")
async def startup_event() -> None:
    runtime.running = True
    # this intentionally does not self-deploy or self-replicate
    # each instance is now operator-controlled
    pass
