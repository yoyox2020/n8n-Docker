from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class WorkflowHistory(Base):
    """Menyimpan setiap workflow yang berhasil dibuat oleh user via agent."""

    __tablename__ = "workflow_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Siapa yang buat
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Info workflow di n8n
    workflow_id: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_name: Mapped[str] = mapped_column(String(512), nullable=False)
    workflow_url: Mapped[str] = mapped_column(Text, nullable=False)

    # Detail langkah-langkah yang dibuat (list of step dicts)
    steps: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Prompt asli dari user
    original_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
