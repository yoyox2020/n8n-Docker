import json

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.memory import AgentMemory
from app.nodes_catalog import NODES_CATALOG
from sqlalchemy import select

router = APIRouter(prefix="/plan", tags=["plan"])

PLANNER_SYSTEM_PROMPT = """You are a workflow planning assistant for MST Workflow platform (built on n8n).

Your job is to analyze user requests and produce a structured Task Graph — a step-by-step list of n8n nodes that, when connected, will automate the user's described process.

Available n8n nodes:
{tools_summary}

Rules:
- Use only node types from the list above.
- Return ONLY valid JSON — no explanation, no markdown, no extra text.
- Each step must have: step number, node_type, display_name, description.

Response format (JSON only):
{{
  "summary": "One sentence describing what this workflow does",
  "intent": "short_snake_case_label",
  "task_graph": [
    {{
      "step": 1,
      "node_type": "n8n-nodes-base.emailReadImap",
      "display_name": "Email Trigger",
      "description": "Triggers when a new email arrives in the inbox"
    }}
  ]
}}"""


class PlanRequest(BaseModel):
    prompt: str
    user_id: str | None = None
    session_id: str | None = None


class TaskStep(BaseModel):
    step: int
    node_type: str
    display_name: str
    description: str


class PlanResponse(BaseModel):
    summary: str
    intent: str
    task_graph: list[TaskStep]


async def _get_history(user_id: str, session_id: str | None, db: AsyncSession) -> list[dict]:
    query = (
        select(AgentMemory)
        .where(AgentMemory.user_id == user_id)
        .order_by(AgentMemory.created_at.desc())
        .limit(10)
    )
    if session_id:
        query = query.where(AgentMemory.session_id == session_id)

    result = await db.execute(query)
    entries = result.scalars().all()
    return [{"role": e.role, "content": e.content} for e in reversed(entries)]


async def _call_mistika(messages: list[dict]) -> str:
    url = f"{settings.mistika_base_url}{settings.mistika_chat_path}"
    headers = {
        # Mistika pakai x-api-key, OpenRouter pakai Authorization Bearer
        settings.mistika_auth_header: (
            f"Bearer {settings.mistika_api_key}"
            if settings.mistika_auth_header == "Authorization"
            else settings.mistika_api_key
        ),
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.mistika_model,
        "messages": messages,
        "temperature": 0.2,
        "top_p": 1.0,
        "max_tokens": 4096,
        "stream": False,  # non-streaming lebih stabil untuk request panjang
    }

    async with httpx.AsyncClient(timeout=120) as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=502,
                    detail=f"LLM error {resp.status_code}: {resp.text[:300]}",
                )
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Failed to reach LLM: {type(exc).__name__}: {exc}")


async def _save_turn(user_id: str, session_id: str | None, role: str, content: str, db: AsyncSession):
    entry = AgentMemory(user_id=user_id, session_id=session_id, role=role, content=content)
    db.add(entry)
    await db.commit()


@router.post("/", response_model=PlanResponse, summary="Generate a workflow Task Graph from a prompt")
async def create_plan(payload: PlanRequest, db: AsyncSession = Depends(get_db)):
    # 1. Get available tools from local catalog
    tools_summary = "\n".join(
        f"- {t['node_type']} ({t['display_name']}): {t['description'][:80]}"
        for t in NODES_CATALOG
    )

    system_prompt = PLANNER_SYSTEM_PROMPT.format(tools_summary=tools_summary)

    # 2. Build message list (with history if user_id provided)
    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    if payload.user_id:
        history = await _get_history(payload.user_id, payload.session_id, db)
        messages.extend(history)

    messages.append({"role": "user", "content": payload.prompt})

    # 3. Call Mistika AI
    raw_response = await _call_mistika(messages)

    # 4. Parse JSON response
    try:
        # Strip markdown code block if present
        clean = raw_response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        result = json.loads(clean.strip())
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=422,
            detail=f"Mistika AI returned non-JSON response: {raw_response[:200]}",
        )

    # 5. Save to memory
    if payload.user_id:
        await _save_turn(payload.user_id, payload.session_id, "user", payload.prompt, db)
        await _save_turn(
            payload.user_id, payload.session_id, "assistant", raw_response, db
        )

    return PlanResponse(**result)
