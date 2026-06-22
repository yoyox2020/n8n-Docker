"""
Router: /approval

Mengelola permintaan approval sebelum agent melakukan aksi berisiko.

Endpoints:
  GET  /approval/{id}          — cek status approval (dipakai Agent Node untuk polling)
  POST /approval/{id}/respond  — user setuju atau tolak
  GET  /approval/user/{user_id} — semua approval pending milik seorang user
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.approval import ApprovalRequest

router = APIRouter(prefix="/approval", tags=["approval"])


class ApprovalStatusResponse(BaseModel):
    id: str
    user_id: str
    node_name: str
    action_description: str
    risk_level: str
    status: str  # pending / approved / rejected / expired
    context: dict | None
    requested_at: str
    responded_at: str | None
    response_note: str | None


class RespondRequest(BaseModel):
    # "approved" atau "rejected"
    decision: str
    # Catatan opsional dari user (alasan menolak, dll)
    note: str | None = None


@router.get("/{approval_id}", response_model=ApprovalStatusResponse, summary="Cek status approval")
async def get_approval(approval_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
    )
    approval = result.scalar_one_or_none()

    if approval is None:
        raise HTTPException(status_code=404, detail=f"Approval {approval_id} tidak ditemukan")

    return ApprovalStatusResponse(
        id=approval.id,
        user_id=approval.user_id,
        node_name=approval.node_name,
        action_description=approval.action_description,
        risk_level=approval.risk_level,
        status=approval.status,
        context=approval.context,
        requested_at=approval.requested_at.isoformat(),
        responded_at=approval.responded_at.isoformat() if approval.responded_at else None,
        response_note=approval.response_note,
    )


@router.post("/{approval_id}/respond", response_model=ApprovalStatusResponse, summary="Approve atau reject aksi agent")
async def respond_approval(
    approval_id: str,
    payload: RespondRequest,
    db: AsyncSession = Depends(get_db),
):
    if payload.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision harus 'approved' atau 'rejected'")

    result = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
    )
    approval = result.scalar_one_or_none()

    if approval is None:
        raise HTTPException(status_code=404, detail=f"Approval {approval_id} tidak ditemukan")

    if approval.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Approval sudah dalam status '{approval.status}', tidak bisa diubah lagi",
        )

    # Catat keputusan
    approval.status = payload.decision
    approval.response_note = payload.note
    approval.responded_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(approval)

    return ApprovalStatusResponse(
        id=approval.id,
        user_id=approval.user_id,
        node_name=approval.node_name,
        action_description=approval.action_description,
        risk_level=approval.risk_level,
        status=approval.status,
        context=approval.context,
        requested_at=approval.requested_at.isoformat(),
        responded_at=approval.responded_at.isoformat() if approval.responded_at else None,
        response_note=approval.response_note,
    )


@router.get(
    "/user/{user_id}",
    response_model=list[ApprovalStatusResponse],
    summary="Semua approval pending milik user",
)
async def list_user_approvals(
    user_id: str,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(ApprovalRequest)
        .where(ApprovalRequest.user_id == user_id)
        .order_by(ApprovalRequest.requested_at.desc())
        .limit(50)
    )

    if status:
        query = query.where(ApprovalRequest.status == status)

    result = await db.execute(query)
    approvals = result.scalars().all()

    return [
        ApprovalStatusResponse(
            id=a.id,
            user_id=a.user_id,
            node_name=a.node_name,
            action_description=a.action_description,
            risk_level=a.risk_level,
            status=a.status,
            context=a.context,
            requested_at=a.requested_at.isoformat(),
            responded_at=a.responded_at.isoformat() if a.responded_at else None,
            response_note=a.response_note,
        )
        for a in approvals
    ]
