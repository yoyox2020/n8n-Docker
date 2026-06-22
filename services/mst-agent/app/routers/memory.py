from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.memory import AgentMemory
from app.models.workflow_history import WorkflowHistory
from app.models.approval import ApprovalRequest

router = APIRouter(prefix="/memory", tags=["memory"])


class MemorySaveRequest(BaseModel):
    user_id: str
    session_id: str | None = None
    role: str  # 'user' | 'assistant'
    content: str
    meta: dict | None = None


class MemoryEntry(BaseModel):
    id: int
    user_id: str
    session_id: str | None
    role: str
    content: str
    meta: dict | None
    created_at: str

    class Config:
        from_attributes = True


@router.post("/save", summary="Save a conversation turn to memory")
async def save_memory(payload: MemorySaveRequest, db: AsyncSession = Depends(get_db)):
    entry = AgentMemory(
        user_id=payload.user_id,
        session_id=payload.session_id,
        role=payload.role,
        content=payload.content,
        meta=payload.meta,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return {"id": entry.id, "status": "saved"}


@router.get("/{user_id}", summary="Get conversation history for a user")
async def get_memory(
    user_id: str,
    session_id: str | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(AgentMemory)
        .where(AgentMemory.user_id == user_id)
        .order_by(AgentMemory.created_at.desc())
        .limit(limit)
    )
    if session_id:
        query = query.where(AgentMemory.session_id == session_id)

    result = await db.execute(query)
    entries = result.scalars().all()

    return {
        "user_id": user_id,
        "session_id": session_id,
        "count": len(entries),
        "history": [
            {
                "id": e.id,
                "role": e.role,
                "content": e.content,
                "created_at": e.created_at.isoformat(),
            }
            for e in reversed(entries)  # oldest first
        ],
    }


@router.get("/{user_id}/last-activity", summary="Ambil aktivitas terakhir user (workflow + approval pending)")
async def get_last_activity(
    user_id: str,
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
):
    """
    Dipakai oleh sidebar frontend untuk menampilkan:
    - Workflow terakhir yang dibuat user
    - Approval yang masih menunggu keputusan user
    """
    # Ambil workflow terakhir
    wf_result = await db.execute(
        select(WorkflowHistory)
        .where(WorkflowHistory.user_id == user_id)
        .order_by(WorkflowHistory.created_at.desc())
        .limit(limit)
    )
    workflows = wf_result.scalars().all()

    # Ambil approval yang masih pending
    ap_result = await db.execute(
        select(ApprovalRequest)
        .where(ApprovalRequest.user_id == user_id, ApprovalRequest.status == "pending")
        .order_by(ApprovalRequest.requested_at.desc())
        .limit(10)
    )
    pending_approvals = ap_result.scalars().all()

    return {
        "user_id": user_id,
        "recent_workflows": [
            {
                "id": w.id,
                "workflow_id": w.workflow_id,
                "workflow_name": w.workflow_name,
                "workflow_url": w.workflow_url,
                "step_count": len(w.steps) if w.steps else 0,
                "original_prompt": w.original_prompt,
                "created_at": w.created_at.isoformat(),
            }
            for w in workflows
        ],
        "pending_approvals": [
            {
                "id": a.id,
                "node_name": a.node_name,
                "action_description": a.action_description,
                "risk_level": a.risk_level,
                "requested_at": a.requested_at.isoformat(),
            }
            for a in pending_approvals
        ],
    }


@router.delete("/{user_id}", summary="Clear all memory for a user")
async def clear_memory(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        delete(AgentMemory).where(AgentMemory.user_id == user_id)
    )
    await db.commit()
    return {"user_id": user_id, "deleted": result.rowcount}
