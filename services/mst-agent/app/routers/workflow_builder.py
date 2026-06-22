import json
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.workflow_history import WorkflowHistory
from app.routers.plan import _call_mistika, _save_turn, PLANNER_SYSTEM_PROMPT
from app.nodes_catalog import NODES_CATALOG

router = APIRouter(prefix="/workflow", tags=["workflow"])

# Default typeVersion per node type — most are 1, some need specific versions
NODE_VERSIONS: dict[str, int] = {
    "n8n-nodes-base.webhook": 2,
    "n8n-nodes-base.httpRequest": 4,
    "n8n-nodes-base.emailSend": 2,
    "n8n-nodes-base.gmail": 2,
    "n8n-nodes-base.slack": 2,
    "n8n-nodes-base.googleSheets": 4,
    "n8n-nodes-base.postgres": 2,
    "n8n-nodes-base.set": 3,
    "n8n-nodes-base.if": 2,
    "n8n-nodes-base.code": 2,
    "n8n-nodes-base.merge": 3,
    "@n8n/n8n-nodes-langchain.agent": 1,
}


def _task_graph_to_workflow_json(name: str, task_graph: list[dict]) -> dict:
    """Convert a task_graph list into a valid n8n workflow JSON."""
    nodes = []
    connections: dict = {}

    for i, step in enumerate(task_graph):
        node_type = step["node_type"]
        node_name = step["display_name"]
        node_id = str(uuid.uuid4())

        nodes.append({
            "id": node_id,
            "name": node_name,
            "type": node_type,
            "typeVersion": NODE_VERSIONS.get(node_type, 1),
            "position": [250 + i * 250, 300],
            "parameters": {},
            "credentials": {},
        })

        # Connect this node to the next one (linear chain)
        if i < len(task_graph) - 1:
            next_name = task_graph[i + 1]["display_name"]
            connections[node_name] = {
                "main": [[{"node": next_name, "type": "main", "index": 0}]]
            }

    return {
        "name": name,
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
        "staticData": None,
    }


async def _create_workflow_in_n8n(workflow_json: dict) -> dict:
    """POST workflow JSON to n8n public API and return the created workflow."""
    url = f"{settings.n8n_base_url}/api/v1/workflows"
    headers = {
        "X-N8N-API-KEY": settings.n8n_api_key,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(url, headers=headers, json=workflow_json)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=502, detail=f"n8n API error: {exc.response.text}")
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Failed to reach n8n: {exc}")


class BuildWorkflowRequest(BaseModel):
    prompt: str
    user_id: str | None = None
    session_id: str | None = None


class BuildWorkflowResponse(BaseModel):
    message: str
    workflow_name: str
    workflow_id: str
    workflow_url: str
    steps: list[dict]


@router.post("/build", response_model=BuildWorkflowResponse, summary="Build and create an n8n workflow from a prompt")
async def build_workflow(payload: BuildWorkflowRequest, db: AsyncSession = Depends(get_db)):
    # 1. Build tools summary for the planner prompt
    tools_summary = "\n".join(
        f"- {t['node_type']} ({t['display_name']}): {t['description'][:80]}"
        for t in NODES_CATALOG
    )
    system_prompt = PLANNER_SYSTEM_PROMPT.format(tools_summary=tools_summary)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": payload.prompt},
    ]

    # 2. Call LLM to get task_graph
    raw_response = await _call_mistika(messages)

    # 3. Parse JSON response
    try:
        clean = raw_response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        plan = json.loads(clean.strip())
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail=f"LLM returned non-JSON: {raw_response[:200]}")

    task_graph: list[dict] = plan.get("task_graph", [])
    workflow_name: str = plan.get("summary", payload.prompt)[:60]

    if not task_graph:
        raise HTTPException(status_code=422, detail="LLM returned empty task_graph")

    # 4. Convert task_graph to n8n workflow JSON and create it
    workflow_json = _task_graph_to_workflow_json(workflow_name, task_graph)
    created = await _create_workflow_in_n8n(workflow_json)

    workflow_id = str(created.get("id", ""))

    # 5. Simpan ke workflow_history dan memory
    if payload.user_id:
        # Simpan ke tabel workflow_history agar bisa ditampilkan sebagai "aktivitas terakhir"
        history_entry = WorkflowHistory(
            user_id=payload.user_id,
            session_id=payload.session_id,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            workflow_url=f"{settings.n8n_base_url}/workflow/{workflow_id}",
            steps=task_graph,
            original_prompt=payload.prompt,
        )
        db.add(history_entry)
        await db.commit()

        # Simpan ringkasan ke chat memory untuk konteks percakapan
        await _save_turn(payload.user_id, payload.session_id, "user", payload.prompt, db)
        summary_text = (
            f"Workflow '{workflow_name}' dibuat dengan {len(task_graph)} langkah: "
            + ", ".join(s["display_name"] for s in task_graph)
        )
        await _save_turn(payload.user_id, payload.session_id, "assistant", summary_text, db)

    # 6. Format human-readable step list
    steps = [
        {"step": s["step"], "node": s["display_name"], "description": s["description"]}
        for s in task_graph
    ]

    return BuildWorkflowResponse(
        message=f"Workflow berhasil dibuat! Berisi {len(task_graph)} langkah.",
        workflow_name=workflow_name,
        workflow_id=workflow_id,
        workflow_url=f"http://localhost:5678/workflow/{workflow_id}",
        steps=steps,
    )
