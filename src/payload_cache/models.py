import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TransformedString(Base):
    __tablename__ = "transformed_strings"

    source: Mapped[str] = mapped_column(Text, primary_key=True)
    result: Mapped[str] = mapped_column(Text)


class Payload(Base):
    __tablename__ = "payloads"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    input_hash: Mapped[str] = mapped_column(String(64), unique=True)
    output: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
