"""
Router: /runtime/decide

Agent Node di n8n memanggil endpoint ini saat workflow sedang berjalan
dan perlu membuat keputusan berdasarkan AI.

Alur:
  1. Agent Node kirim konteks (data dari node sebelumnya, instruksi, aksi yang tersedia)
  2. Agent Service kirim ke LLM untuk dianalisa
  3. LLM memutuskan: lakukan aksi / butuh approval / tidak bisa
  4. Jika butuh approval → buat ApprovalRequest dan kembalikan approval_id
  5. Agent Node routing ke output yang sesuai (decided / needs_approval / error)
"""

import uuid
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.approval import ApprovalRequest
from app.routers.plan import _call_mistika

router = APIRouter(prefix="/runtime", tags=["runtime"])

# Tingkat risiko yang WAJIB minta approval sebelum dilanjutkan
HIGH_RISK_LEVELS = {"high", "critical"}

# Prompt untuk LLM agar memutuskan aksi runtime
RUNTIME_DECISION_PROMPT = """Kamu adalah agen pengambil keputusan untuk platform workflow otomasi.

Kamu menerima konteks eksekusi workflow yang sedang berjalan dan harus memutuskan langkah berikutnya.

Konteks yang diberikan:
- Instruksi: apa yang ingin dilakukan
- Data input: data yang tersedia dari node sebelumnya
- Aksi yang tersedia: pilihan aksi yang bisa dijalankan

Aturan keputusan:
1. Jika aksi aman dan jelas → putuskan langsung
2. Jika aksi menyangkut: hapus data, transaksi keuangan, ubah kredensial, perubahan produksi → WAJIB minta approval
3. Jika tidak bisa memutuskan karena data tidak cukup → kembalikan error dengan penjelasan

Tingkat risiko:
- low: baca data, kirim notifikasi biasa
- medium: tulis data baru, update non-kritis
- high: hapus data, update data produksi
- critical: transaksi keuangan, ubah akses/kredensial

Format respons (JSON only, tanpa markdown):
{
  "decision": "proceed" | "needs_approval" | "cannot_decide",
  "chosen_action": "nama aksi yang dipilih dari daftar tersedia",
  "reason": "penjelasan singkat keputusan",
  "risk_level": "low" | "medium" | "high" | "critical",
  "approval_description": "deskripsi untuk user jika butuh approval (kosong jika proceed)"
}"""


class DecideRequest(BaseModel):
    # Siapa yang menjalankan workflow
    user_id: str
    execution_id: str | None = None
    workflow_id: str | None = None
    node_name: str = "MST Agent Node"

    # Instruksi dan data untuk diputuskan
    instruction: str
    input_data: dict | None = None

    # Pilihan aksi yang tersedia (Agent Node mendaftarkan ini)
    available_actions: list[str] = []

    # Konteks tambahan (misalnya histori langkah sebelumnya)
    context: dict | None = None


class DecideResponse(BaseModel):
    # Salah satu dari: "decided" / "needs_approval" / "error"
    output: str

    # Aksi yang dipilih (diisi jika output = "decided")
    chosen_action: str | None = None

    # Alasan keputusan — selalu diisi
    reason: str

    # Tingkat risiko yang dinilai LLM
    risk_level: str

    # Diisi jika output = "needs_approval" — Agent Node pakai ini untuk polling
    approval_id: str | None = None

    # Pesan error jika output = "error"
    error: str | None = None


@router.post("/decide", response_model=DecideResponse, summary="Minta keputusan runtime dari AI agent")
async def decide(payload: DecideRequest, db: AsyncSession = Depends(get_db)):
    # 1. Susun pesan untuk LLM
    user_message = f"""
Instruksi: {payload.instruction}

Data input: {json.dumps(payload.input_data or {}, ensure_ascii=False, indent=2)}

Aksi yang tersedia: {json.dumps(payload.available_actions, ensure_ascii=False)}

Node: {payload.node_name}
""".strip()

    messages = [
        {"role": "system", "content": RUNTIME_DECISION_PROMPT},
        {"role": "user", "content": user_message},
    ]

    # 2. Panggil LLM
    raw_response = await _call_mistika(messages)

    # 3. Parse JSON dari LLM
    try:
        clean = raw_response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        llm_result = json.loads(clean.strip())
    except json.JSONDecodeError:
        return DecideResponse(
            output="error",
            reason="LLM tidak menghasilkan JSON yang valid",
            risk_level="low",
            error=f"Raw response: {raw_response[:300]}",
        )

    decision = llm_result.get("decision", "cannot_decide")
    chosen_action = llm_result.get("chosen_action")
    reason = llm_result.get("reason", "Tidak ada penjelasan")
    risk_level = llm_result.get("risk_level", "medium")

    # 4a. Jika LLM putuskan proceed dan risiko rendah/medium → langsung jalankan
    if decision == "proceed" and risk_level not in HIGH_RISK_LEVELS:
        return DecideResponse(
            output="decided",
            chosen_action=chosen_action,
            reason=reason,
            risk_level=risk_level,
        )

    # 4b. Jika butuh approval (karena LLM bilang atau risiko tinggi)
    if decision in ("needs_approval", "proceed") and risk_level in HIGH_RISK_LEVELS:
        approval_id = str(uuid.uuid4())
        action_desc = llm_result.get("approval_description") or (
            f"Agent ingin melakukan: {chosen_action}. Alasan: {reason}"
        )

        approval = ApprovalRequest(
            id=approval_id,
            user_id=payload.user_id,
            execution_id=payload.execution_id,
            workflow_id=payload.workflow_id,
            node_name=payload.node_name,
            action_description=action_desc,
            risk_level=risk_level,
            context={
                "instruction": payload.instruction,
                "chosen_action": chosen_action,
                "input_data": payload.input_data,
            },
            status="pending",
        )
        db.add(approval)
        await db.commit()

        return DecideResponse(
            output="needs_approval",
            chosen_action=chosen_action,
            reason=reason,
            risk_level=risk_level,
            approval_id=approval_id,
        )

    # 4c. LLM tidak bisa memutuskan
    return DecideResponse(
        output="error",
        reason=reason,
        risk_level=risk_level,
        error="Agent tidak dapat memutuskan. Periksa instruksi dan data input.",
    )
