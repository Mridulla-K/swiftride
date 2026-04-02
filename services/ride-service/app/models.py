"""Ride ORM model."""

from __future__ import annotations

import uuid
import enum
from datetime import datetime

from sqlalchemy import String, Float, DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class RideStatus(str, enum.Enum):
    requested = "requested"
    matched = "matched"
    driver_en_route = "driver_en_route"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
    failed = "failed"


class Ride(Base):
    __tablename__ = "rides"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    driver_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    status: Mapped[RideStatus] = mapped_column(Enum(RideStatus), default=RideStatus.requested)

    pickup_lat: Mapped[float] = mapped_column(Float, nullable=False)
    pickup_lng: Mapped[float] = mapped_column(Float, nullable=False)
    dropoff_lat: Mapped[float] = mapped_column(Float, nullable=False)
    dropoff_lng: Mapped[float] = mapped_column(Float, nullable=False)

    pickup_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dropoff_address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    fare_amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    matched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
