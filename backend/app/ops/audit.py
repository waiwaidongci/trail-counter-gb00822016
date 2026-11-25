from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.clock import now_utc
from app.database import Base


class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(50))
    subject: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


def audit(db, actor: str, action: str, subject: str):
    db.add(AuditEvent(actor=actor, action=action, subject=subject))
