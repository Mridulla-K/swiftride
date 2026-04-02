"""Driver ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, Float, DateTime, Enum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

import enum

from shared.database import Base


class DriverStatus(str, enum.Enum):
    available = "available"
    busy = "busy"
    offline = "offline"


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    license_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    vehicle_model: Mapped[str] = mapped_column(String(100), nullable=False)
    vehicle_plate: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[DriverStatus] = mapped_column(Enum(DriverStatus), default=DriverStatus.offline)
    current_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating: Mapped[float] = mapped_column(Float, default=5.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
