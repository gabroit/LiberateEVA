from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TaskEnvelope(BaseModel):
    task_id: str | None = None
    task_type: str = "instruction"
    payload: dict[str, Any] = Field(default_factory=dict)
    instructions: str | None = None


class AgentMessage(BaseModel):
    role: str
    content: str


class MemoryItem(BaseModel):
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
