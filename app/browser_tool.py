from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

from app.config import get_settings


class BrowserTool:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.browser = None
        self.context = None
        self.page = None
        self._lock = asyncio.Lock()

    async def ensure_started(self) -> None:
        if self.page is not None and not self.page.is_closed():
            return

        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=self.settings.browser_headless)
        self.context = await self.browser.new_context(viewport={"width": 1440, "height": 1100})
        self.page = await self.context.new_page()

    async def navigate(self, url: str) -> str:
        await self.ensure_started()
        response = await self.page.goto(url, wait_until="networkidle", timeout=self.settings.browser_timeout)
        return response.status if response else "unknown"

    async def fill(self, selector: str, value: str) -> None:
        await self.ensure_started()
        await self.page.fill(selector, value)

    async def click(self, selector: str) -> None:
        await self.ensure_started()
        await self.page.click(selector, timeout=self.settings.browser_timeout)

    async def text(self, selector: str | None = None) -> str:
        await self.ensure_started()
        if selector:
            return await self.page.locator(selector).inner_text()
        return await self.page.inner_text("body")

    async def screenshot(self, path: str) -> str:
        await self.ensure_started()
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        await self.page.screenshot(path=str(output), full_page=True)
        return str(output)

    async def close(self) -> None:
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        self.page = None
        self.context = None
        self.browser = None

    async def execute(self, action: dict[str, Any]) -> str:
        kind = action.get("type", "navigate")
        if kind == "navigate":
            return await self.navigate(str(action.get("url", "https://example.com")))
        if kind == "fill":
            await self.fill(str(action.get("selector", "input")), str(action.get("value", "")))
            return "filled"
        if kind == "click":
            await self.click(str(action.get("selector", "button")))
            return "clicked"
        if kind == "text":
            return await self.text(str(action.get("selector")) if action.get("selector") else None)
        if kind == "screenshot":
            return await self.screenshot(str(action.get("path", "./data/screenshot.png")))
        raise ValueError(f"Unsupported browser action: {kind}")
