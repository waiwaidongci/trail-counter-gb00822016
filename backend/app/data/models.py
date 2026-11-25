from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, JSON
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
