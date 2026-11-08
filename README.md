# LiberateEVA Agent Runtime

A lightweight autonomous agent runtime built in Python with FastAPI, OpenRouter Gemini access, local persistent memory via Chroma, a browser automation tool using Playwright, and a lightweight SQLite-based task queue.

## Features

- Python backend with FastAPI
- Gemini model access through OpenRouter
- Local persistent vector memory using ChromaDB
- Browser automation via Playwright
- SQLite shared task queue for autonomous scheduling and polling
- Webhook endpoint for external instruction ingestion
- Background worker loop that continues processing tasks without a turn-based restriction
- Task state API for inspection and monitoring

## Quick start

1. Install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python -m playwright install chromium
   ```

2. Copy environment example:

   ```bash
   cp .env.example .env
   ```

3. Add your configuration values in `.env`.

4. Start the app:

   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. Send instructions via webhook:

   ```bash
   curl -X POST http://localhost:8000/webhook \
     -H "Content-Type: application/json" \
     -H "X-Webhook-Secret: change-me" \
     -d '{
       "instruction": "Go to https://example.com and summarize the page title and main content.",
       "source": "external"
     }'
   ```

## Environment variables

See `.env.example` for the complete list.

## Architecture

- `app/main.py` — FastAPI app and endpoints
- `app/config.py` — settings and environment configuration
- `app/queue.py` — SQLite queue implementation
- `app/memory.py` — Chroma-based persistent memory
- `app/browser_tool.py` — Playwright browser automation
- `app/openrouter_client.py` — OpenRouter Gemini client
- `app/agent_runtime.py` — autonomous worker loop and orchestration

## Notes

This is intentionally lightweight and suitable for local development or internal tool use. The runtime is designed to keep working in the background, poll new tasks, and act on them without forcing a user-turn conversation model.
