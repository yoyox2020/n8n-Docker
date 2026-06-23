# Phase 2 — MST Agent Service (Dev Agent Workflow)

## Overview

Phase 2 introduces a standalone **Agent Service** that bridges the n8n Chat Hub frontend with an intelligent workflow planner powered by Mistika-AI. The service runs as a separate Docker container and connects to the existing n8n instance via the shared `mstworkflow` Docker network.

```
User (Chat Hub UI)
        │
        ▼
  n8n Chat Hub  ──────► Mistika-AI (LLM)
        │
        ▼
  Agent Service  (this repo)
  ┌─────────────────────┐
  │  POST /plan         │  ← Generates workflow Task Graph
  │  GET  /memory/:uid  │  ← Retrieves conversation history
  │  POST /memory/save  │  ← Persists conversation turns
  │  DELETE /memory/:uid│  ← Clears user memory
  │  GET  /tools        │  ← Lists all n8n nodes as tools
  │  POST /tools/refresh│  ← Reloads node cache from n8n
  └─────────────────────┘
        │
        ├─── PostgreSQL (agent_memory table)
        └─── n8n API (/types/nodes.json)
```

## Folder Structure

```
n8n-mst-Agent/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app, lifespan, CORS, router registration
│   ├── config.py         # Pydantic Settings — all env vars
│   ├── database.py       # SQLAlchemy async engine + session factory
│   ├── models/
│   │   ├── __init__.py
│   │   └── memory.py     # AgentMemory ORM model
│   └── routers/
│       ├── __init__.py
│       ├── memory.py     # /memory endpoints
│       ├── plan.py       # /plan endpoint (main planner)
│       └── tools.py      # /tools endpoints
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── phase-2-dev-agent-workflow.md  (this file)
```

## API Endpoints

### `POST /plan/`

Generates a structured **Task Graph** — a step-by-step list of n8n nodes that automate the user's request.

**Request:**
```json
{
  "prompt": "Kirim email ke tim jika ada pesan Slack masuk ke channel #alerts",
  "user_id": "user-123",
  "session_id": "sess-abc"
}
```

**Response:**
```json
{
  "summary": "Monitors Slack channel and forwards alert messages to team email",
  "intent": "slack_to_email_alert",
  "task_graph": [
    {
      "step": 1,
      "node_type": "n8n-nodes-base.slackTrigger",
      "display_name": "Slack Trigger",
      "description": "Listens for new messages in #alerts channel"
    },
    {
      "step": 2,
      "node_type": "n8n-nodes-base.emailSend",
      "display_name": "Send Email",
      "description": "Sends notification email to the team"
    }
  ]
}
```

**Internal flow:**
1. Fetches all n8n nodes from `/types/nodes.json` (cached in memory)
2. Loads recent conversation history from PostgreSQL (last 10 turns)
3. Calls Mistika-AI `/chat/completions` with system prompt + history + user message
4. Parses JSON response (strips markdown code block if present)
5. Saves user and assistant turns to memory
6. Returns `PlanResponse`

---

### `GET /memory/{user_id}`

Returns conversation history for a user. Supports optional `session_id` and `limit` query params.

### `POST /memory/save`

Manually saves a conversation turn. `/plan` calls this automatically.

### `DELETE /memory/{user_id}`

Clears all stored turns for a user.

---

### `GET /tools/`

Returns all available n8n nodes filtered from `/types/nodes.json`. Supports `?category=` and `?search=` query params.

### `POST /tools/refresh`

Clears the in-memory tool cache and reloads from n8n. Use after installing new nodes.

---

## Configuration (`.env`)

| Variable | Description | Default |
|---|---|---|
| `MISTIKA_BASE_URL` | Mistika AI base URL | `https://misstika.mst.co.id/llm-router` |
| `MISTIKA_API_KEY` | **Required** — Bearer token | — |
| `MISTIKA_MODEL` | Model ID to use | `mistika-default` |
| `MISTIKA_CHAT_PATH` | Chat completions path | `/chat/completions` |
| `DATABASE_URL` | `postgresql+asyncpg://...` | — |
| `N8N_BASE_URL` | n8n instance URL (internal) | `http://n8n:5678` |
| `N8N_API_KEY` | Optional n8n API key | `""` |
| `AGENT_PORT` | Listening port | `8000` |
| `DEBUG` | Enable debug mode | `false` |

Copy `.env.example` to `.env` and fill in `MISTIKA_API_KEY` and `DATABASE_URL`.

---

## Network Architecture

This service joins the **external** Docker network `mstworkflow`. This is the same network used by the n8n stack in `c:\Users\Acer\n8n-Docker\deploy\phase-0\docker-compose.yml`.

```yaml
networks:
  mstworkflow:
    external: true
    name: mstworkflow
```

The Agent Service container can reach `http://n8n:5678` directly by container name. Port `8001` is exposed to the host.

---

## Startup

### Prerequisites

1. The n8n stack must be running first:
   ```bash
   cd C:\Users\Acer\n8n-Docker\deploy\phase-0
   docker compose up -d
   ```

2. The `mstworkflow` network must exist (created by the n8n stack).

### Start Agent Service

```bash
cd C:\Users\Acer\n8n-mst-Agent

# Copy and fill in credentials
copy .env.example .env
# Edit .env: set MISTIKA_API_KEY

# Build and start
docker compose up -d --build

# Verify
docker compose logs -f agent-service
```

### API Docs (Swagger UI)

Available at `http://localhost:8001/docs` once running.

### Health Check

```bash
curl http://localhost:8001/health
# {"status":"ok","service":"mst-agent-service","version":"2.0.0"}
```

---

## Database

The service uses its own **PostgreSQL 16** container (`mst-agent-db`). Tables are created automatically on first startup via SQLAlchemy `create_all`.

**`agent_memory` table:**

| Column | Type | Description |
|---|---|---|
| `id` | SERIAL PK | Auto-increment |
| `user_id` | VARCHAR(255) | n8n user identifier |
| `session_id` | VARCHAR(255) | Optional session grouping |
| `role` | VARCHAR(50) | `user` or `assistant` |
| `content` | TEXT | Message text |
| `meta` | JSONB | Optional metadata |
| `created_at` | TIMESTAMPTZ | Auto-set by server |

---

## What Changed vs Phase 1

Phase 1 modified the **n8n monorepo** (`c:\Users\Acer\n8n-Docker`) to:
- Add Mistika-AI as the only LLM provider in Chat Hub
- Add type-safe DTOs
- Fix the `disabled` field in user types
- Add `ToggleUserDisabledRequestDto`

Phase 2 **does not touch the n8n monorepo**. It adds a separate microservice that extends the platform with AI planning capabilities without requiring a rebuild of n8n.

---

## Development (without Docker)

```bash
cd C:\Users\Acer\n8n-mst-Agent

# Install dependencies
pip install -r requirements.txt

# Set env vars (or use .env file with python-dotenv)
set DATABASE_URL=postgresql+asyncpg://agentuser:agentpass@localhost:5432/agentdb
set MISTIKA_API_KEY=your-key

# Run dev server
uvicorn app.main:app --reload --port 8000
```

