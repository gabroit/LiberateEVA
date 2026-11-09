#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from app.config import get_settings


def load_agent_context(path: str | None = None) -> str:
    settings = get_settings()
    config_path = Path(path or settings.agent_context_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Agent context file not found: {config_path}")
    text = config_path.read_text(encoding="utf-8")
    return text.strip()


def build_runtime_config(context_text: str) -> dict[str, str | bool]:
    return {
        "agent_context": context_text,
        "review_only": True,
        "executable": False,
        "autonomous_self_replication": False,
    }


if __name__ == "__main__":
    context = load_agent_context()
    print(json.dumps(build_runtime_config(context), indent=2))
