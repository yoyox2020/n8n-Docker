"""
Router: /approval

Mengelola permintaan approval sebelum agent melakukan aksi berisiko.

Endpoints:
  GET  /approval/{id}          — cek status approval (dipakai Agent Node untuk polling)
  POST /approval/{id}/respond  — user setuju atau tolak
  GET  /approval/user/{user_id} — semua approval pending milik seorang user
"""

import logging
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.approval import ApprovalRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approval", tags=["approval"])


class CreateApprovalRequest(BaseModel):
    user_id: str
    node_name: str
    action_description: str
    risk_level: str = "medium"  # low / medium / high / critical
    context: dict | None = None
    execution_id: str | None = None
    workflow_id: str | None = None


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


@router.post("/", response_model=ApprovalStatusResponse, summary="Buat approval request baru")
async def create_approval(payload: CreateApprovalRequest, db: AsyncSession = Depends(get_db)):
    """
    Dipanggil oleh workflow/agent node ketika ingin meminta persetujuan user
    sebelum melakukan aksi berisiko (kirim email, hapus data, dll).
    """
    if payload.risk_level not in ("low", "medium", "high", "critical"):
        raise HTTPException(status_code=400, detail="risk_level harus: low, medium, high, atau critical")

    approval = ApprovalRequest(
        id=str(uuid.uuid4()),
        user_id=payload.user_id,
        node_name=payload.node_name,
        action_description=payload.action_description,
        risk_level=payload.risk_level,
        context=payload.context,
        execution_id=payload.execution_id,
        workflow_id=payload.workflow_id,
        status="pending",
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)

    # Kirim notifikasi real-time ke chat user via n8n internal endpoint
    import asyncio
    asyncio.create_task(_notify_chat(approval))

    return ApprovalStatusResponse(
        id=approval.id,
        user_id=approval.user_id,
        node_name=approval.node_name,
        action_description=approval.action_description,
        risk_level=approval.risk_level,
        status=approval.status,
        context=approval.context,
        requested_at=approval.requested_at.isoformat(),
        responded_at=None,
        response_note=None,
    )


async def _get_n8n_cookie() -> str | None:
    """Login ke n8n sebagai admin dan kembalikan cookie session."""
    if not settings.n8n_admin_email or not settings.n8n_admin_password:
        return None
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.post(
                f"{settings.n8n_base_url}/rest/login",
                json={"emailOrLdapLoginId": settings.n8n_admin_email, "password": settings.n8n_admin_password},
            )
            if resp.status_code == 200:
                return "; ".join(f"{k}={v}" for k, v in resp.cookies.items()) or None
    except Exception as exc:
        logger.warning("[ApprovalNotify] Login n8n gagal: %s", exc)
    return None


async def _notify_chat(approval: ApprovalRequest) -> None:
    """Push notifikasi approval ke chat session user via n8n internal API."""
    cookie = await _get_n8n_cookie()
    if not cookie:
        logger.warning("[ApprovalNotify] Tidak bisa login ke n8n, skip notifikasi")
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{settings.n8n_base_url}/rest/chat/approval-notify",
                headers={"Cookie": cookie, "Content-Type": "application/json"},
                json={
                    "user_id": approval.user_id,
                    "id": approval.id,
                    "node_name": approval.node_name,
                    "action_description": approval.action_description,
                    "risk_level": approval.risk_level,
                },
            )
            if resp.status_code == 200:
                logger.info("[ApprovalNotify] ✅ Notifikasi terkirim ke chat user %s", approval.user_id)
            else:
                logger.warning("[ApprovalNotify] n8n balas %d: %s", resp.status_code, resp.text[:100])
    except Exception as exc:
        logger.warning("[ApprovalNotify] Gagal notifikasi: %s", exc)


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
