from __future__ import annotations

import asyncio
import json
from typing import Any

from app.browser_tool import BrowserTool
from app.memory import PersistentMemory
from app.openrouter_client import OpenRouterClient
from app.queue import SharedStateQueue


class AgentRuntime:
    def __init__(self, queue: SharedStateQueue, memory: PersistentMemory, browser: BrowserTool, llm: OpenRouterClient) -> None:
        self.queue = queue
        self.memory = memory
        self.browser = browser
        self.llm = llm
        self.running = False

    async def ingest_instruction(self, instruction: str, metadata: dict[str, Any] | None = None) -> str:
        payload = {"instruction": instruction, "metadata": metadata or {}}
        return self.queue.enqueue("instruction", payload)

    async def process_task(self, task: dict[str, Any]) -> dict[str, Any]:
        instruction = str(task.get("payload", {}).get("instruction", ""))
        metadata = task.get("payload", {}).get("metadata", {})

        if not instruction:
            raise ValueError("No instruction provided for task")

        memory_context = self.memory.query(instruction, limit=3)
        memory_summary = "\n".join(item["content"] for item in memory_context)

        llm_response = await self.llm.generate_task_response(instruction, memory_summary)

        browser_action = None
        if "browser" in instruction.lower() or "navigate" in instruction.lower() or "visit" in instruction.lower():
            url_match = self._extract_url(instruction)
            if url_match:
                browser_action = {"type": "navigate", "url": url_match}
                await self.browser.execute(browser_action)
                page_text = await self.browser.text()
                llm_response = await self.llm.generate(
                    [
                        {"role": "system", "content": "You are an agent performing browser-based tasks."},
                        {
                            "role": "user",
                            "content": (
                                f"Instruction: {instruction}\n\n"
                                f"The page content is:\n{page_text[:4000]}\n\n"
                                "Use the page text to answer the user fully and accurately."
                            ),
                        },
                    ]
                )

        self.memory.add(instruction, {"source": metadata.get("source", "runtime"), "task_id": task["id"]})
        self.memory.add(llm_response, {"source": "agent_response", "task_id": task["id"]})

        return {
            "task_id": task["id"],
            "instruction": instruction,
            "response": llm_response,
            "browser_action": browser_action,
        }

    async def worker_loop(self, interval: float = 2.0) -> None:
        self.running = True
        while self.running:
            task = self.queue.claim_next()
            if not task:
                await asyncio.sleep(interval)
                continue

            try:
                result = await self.process_task(task)
                self.queue.mark_complete(task["id"], result)
            except Exception as exc:  # pragma: no cover - runtime safety
                self.queue.mark_failed(task["id"], str(exc))
            finally:
                await asyncio.sleep(0.1)

    def stop(self) -> None:
        self.running = False

    @staticmethod
    def _extract_url(text: str) -> str | None:
        import re

        match = re.search(r"https?://[^\s\)\]>]+", text)
        return match.group(0) if match else None
