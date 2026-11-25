from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.clock import now_utc
from app.database import Base


class Dataset(Base):
    __tablename__ = 'datasets'
    __table_args__ = (UniqueConstraint('name', 'checksum'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    checksum: Mapped[str] = mapped_column(String(64))
    row_count: Mapped[int]
    created_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


class Observation(Base):
    __tablename__ = 'observations'
    __table_args__ = (UniqueConstraint('dataset_id', 'record_key'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'), index=True)
    record_key: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)


class ClockCorrection(Base):
    """An accepted batch clock/window correction and its resulting version."""

    __tablename__ = 'clock_corrections'
    id: Mapped[int] = mapped_column(primary_key=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    source_dataset_id: Mapped[int] = mapped_column(
        ForeignKey('datasets.id'), unique=True, index=True,
    )
    result_dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'), index=True)
    movement_hash: Mapped[str] = mapped_column(String(64), index=True)
    move_count: Mapped[int] = mapped_column(Integer, default=0)
    request_payload: Mapped[Any] = mapped_column(JSON)
    movements: Mapped[list[Any]] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


# Descriptive aliases for modules/tests using the generic correction name.
Correction = ClockCorrection
DatasetCorrection = ClockCorrection
WindowCorrection = ClockCorrection
