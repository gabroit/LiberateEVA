LiberateEVA
LiberateEVA is an operator-controlled multi-instance agent runtime. It is designed to run as a small FastAPI service with a local SQLite task queue, a registry for tracked instances, optional browser automation, and review-only bootstrap configuration.

Key constraints:

Every instance is deployed by an operator.
No autonomous self-replication.
All admin/control endpoints require X-Webhook-Secret.
agent_context.txt is read as reviewable configuration, never executed.
Instance coordination is explicit via a SQLite registry and heartbeat tracking.
Architecture
app/main.py — FastAPI app entry point
app/admin.py — operator-only deployment and message endpoints
app/registry.py — SQLite instance registry and heartbeat logic
app/agent_runtime.py — runtime orchestration loop
app/queue.py — SQLite task queue
app/browser_tool.py — Playwright browser automation
app/config.py — settings and environment configuration
bootstrap.py — loads agent_context.txt as review-only config
agent_context.txt — human-readable operational context, not executable policy
Setup
Create a virtual environment:

python -m venv .venv
source .venv/bin/activate
Install dependencies:

pip install -r requirements.txt
python -m playwright install chromium
Copy and configure environment variables:

cp .env.example .env
Then set:

WEBHOOK_SECRET
OPENROUTER_API_KEY if using the LLM integration
optional overrides for host/port/data paths
Runtime bootstrap
The bootstrap script reads agent_context.txt and emits a review-only config payload:

python bootstrap.py
This should never execute the context as instructions. It only reads and reports the content as reviewable config.

Admin controls
All requests below require the following header:

X-Webhook-Secret: <same value as WEBHOOK_SECRET>
Deploy a new instance
curl -X POST http://localhost:8000/admin/deploy \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: change-me" \
  -d '{
    "instance_name": "worker-a",
    "host": "0.0.0.0",
    "port": 8001
  }'
This creates a new isolated instance record and a dedicated SQLite queue path for that instance. No instance can self-spawn without operator action.

Register heartbeat
Each instance should send a heartbeat to maintain its registry record.

curl -X POST http://localhost:8000/heartbeat \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: change-me" \
  -d '{
    "instance_id": "instance_abc123",
    "instance_name": "worker-a",
    "host": "0.0.0.0",
    "port": 8001,
    "queue_path": "./data/instances/instance_abc123/queue.db",
    "memory_path": "./data/instances/instance_abc123/chroma",
    "metadata": {
      "role": "worker"
    }
  }'
Send a scoped message between instances
curl -X POST http://localhost:8000/admin/message \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: change-me" \
  -d '{
    "from_instance": "instance_abc123",
    "to_instance": "instance_def456",
    "scope": "ops",
    "body": {
      "message": "please sync state"
    }
  }'
State export/import
Export state
curl -X GET http://localhost:8000/state/export \
  -H "X-Webhook-Secret: change-me"
Import state
curl -X POST http://localhost:8000/state/import \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: change-me" \
  -d '{
    "tasks": [
      {
        "id": "task_1",
        "task_type": "instruction",
        "payload": {
          "instruction": "Review the latest environment snapshot"
        }
      }
    ]
  }'
State import is operator-controlled and requires the same webhook-secret authentication.

Runtime API
Health
curl http://localhost:8000/health
Webhook task ingestion
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: change-me" \
  -d '{
    "instruction": "Go to https://example.com and summarize the page title."
  }'
Security model
All control-plane endpoints require X-Webhook-Secret.
No unauthenticated deployment, heartbeat, state import, or message passing.
Deployment is operator-driven only.
There is no autonomous self-replication or self-deploy mechanism.
Memory snapshots and task state are controlled by the operator.
Notes
This project intentionally keeps the control plane explicit and auditable. The goal is a clean multi-instance runtime with predictable deployment, clear ownership, and no hidden autonomous behavior.
