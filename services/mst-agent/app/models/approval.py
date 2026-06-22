from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ApprovalRequest(Base):
    """
    Menyimpan permintaan approval sebelum agent melakukan aksi berisiko.

    Status:
      - pending   : menunggu keputusan user
      - approved  : user setuju, aksi boleh dilanjutkan
      - rejected  : user tolak, aksi dibatalkan
      - expired   : timeout, user tidak merespons
    """

    __tablename__ = "approval_requests"

    # UUID string — dikirim ke Agent Node sebagai referensi
    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Siapa yang meminta approval dan dari eksekusi mana
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    execution_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Deskripsi aksi yang minta approval — ditampilkan ke user
    node_name: Mapped[str] = mapped_column(String(255), nullable=False)
    action_description: Mapped[str] = mapped_column(Text, nullable=False)

    # Tingkat risiko: low / medium / high / critical
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")

    # Konteks tambahan (bisa berisi data input, expected output, dll)
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Status keputusan
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    # Catatan dari user saat approve/reject (opsional)
    response_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
