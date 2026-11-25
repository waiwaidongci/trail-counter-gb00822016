from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Account(Base):
    __tablename__ = 'accounts'
    email: Mapped[str] = mapped_column(String(120), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(200))
