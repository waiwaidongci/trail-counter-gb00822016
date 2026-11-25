from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.clock import now_utc
from app.database import Base


class Delivery(Base):
    __tablename__ = 'deliveries'
    __table_args__ = (UniqueConstraint('run_id', 'recipient', 'due_at'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('analysis_runs.id'), index=True)
    recipient: Mapped[str] = mapped_column(ForeignKey('accounts.email'), index=True)
    scheduled_by: Mapped[str] = mapped_column(String(120))
    due_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    report: Mapped[dict | None] = mapped_column(JSON)
