"""
Cross-session memory — ambil riwayat workflow user dari WorkflowHistory
lalu format sebagai blok teks yang diinjeksikan ke system prompt LLM.

Dengan ini, setiap kali sesi baru dibuka, LLM langsung tahu
workflow apa yang pernah dibuat user sebelumnya — tanpa user
perlu menjelaskan ulang konteks mereka.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow_history import WorkflowHistory

logger = logging.getLogger(__name__)

# Panjang maksimal cuplikan prompt asli yang ditampilkan ke LLM.
# Cukup untuk memberi konteks tanpa membuat prompt terlalu panjang.
_MAX_PROMPT_PREVIEW = 100


def _format_relative_time(dt: datetime) -> str:
    """Ubah datetime ke label waktu relatif dalam Bahasa Indonesia."""
    # Pastikan datetime selalu timezone-aware sebelum dibandingkan
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    days = delta.days

    if days == 0:
        return "hari ini"
    if days == 1:
        return "kemarin"
    if days < 7:
        return f"{days} hari lalu"
    if days < 30:
        return f"{days // 7} minggu lalu"
    return f"{days // 30} bulan lalu"


async def get_cross_session_context(
    user_id: str,
    db: AsyncSession,
    limit: int = 5,
) -> str:
    """
    Ambil riwayat workflow terakhir user dan kembalikan sebagai teks konteks
    siap dimasukkan ke system prompt LLM.

    Mengembalikan string kosong jika:
    - user belum pernah membuat workflow (riwayat kosong)
    - terjadi error saat query DB

    Tidak pernah melempar exception ke caller — semua error di-log dan diabaikan
    agar fitur utama (build workflow) tidak terganggu jika riwayat gagal diambil.
    """
    try:
        result = await db.execute(
            select(WorkflowHistory)
            .where(WorkflowHistory.user_id == user_id)
            .order_by(WorkflowHistory.created_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
    except Exception as exc:
        logger.warning(
            "cross_session_context: gagal query riwayat untuk user_id=%s — %s",
            user_id,
            exc,
        )
        return ""

    if not rows:
        return ""

    # Tampilkan dari yang paling lama ke paling baru agar kronologi terbaca jelas
    lines = ["--- RIWAYAT WORKFLOW PENGGUNA ---"]
    for i, wf in enumerate(reversed(rows), start=1):
        preview = wf.original_prompt[:_MAX_PROMPT_PREVIEW]
        if len(wf.original_prompt) > _MAX_PROMPT_PREVIEW:
            preview += "..."
        time_label = _format_relative_time(wf.created_at)
        lines.append(
            f'{i}. "{wf.workflow_name}"'
            f' — prompt: "{preview}"'
            f" ({time_label})"
        )

    lines.append(
        "Gunakan riwayat ini jika relevan: rekomendasikan pola serupa, "
        "hindari duplikasi, atau tawarkan peningkatan dari workflow sebelumnya."
    )
    lines.append("--- END RIWAYAT ---")

    return "\n".join(lines)
