from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.clock import now_utc
from app.database import Base


class AnalysisRun(Base):
    __tablename__ = 'analysis_runs'
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    options: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class Review(Base):
    __tablename__ = 'reviews'
    run_id: Mapped[int] = mapped_column(ForeignKey('analysis_runs.id'), primary_key=True)
    decision: Mapped[str] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(Text)
    reviewer: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
