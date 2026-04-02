"""Pydantic schemas for ride service."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RideRequest(BaseModel):
    rider_id: uuid.UUID
    pickup_lat: float = Field(ge=-90, le=90)
    pickup_lng: float = Field(ge=-180, le=180)
    dropoff_lat: float = Field(ge=-90, le=90)
    dropoff_lng: float = Field(ge=-180, le=180)
    pickup_address: Optional[str] = None
    dropoff_address: Optional[str] = None
    vehicle_type: str = Field(default="car", pattern="^(bike|auto|car)$")


class RideResponse(BaseModel):
    id: uuid.UUID
    rider_id: uuid.UUID
    driver_id: Optional[uuid.UUID] = None
    status: str
    pickup_lat: float
    pickup_lng: float
    dropoff_lat: float
    dropoff_lng: float
    pickup_address: Optional[str] = None
    dropoff_address: Optional[str] = None
    distance_km: Optional[float] = None
    duration_minutes: Optional[float] = None
    fare_amount: Optional[float] = None
    requested_at: datetime
    matched_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RideComplete(BaseModel):
    distance_km: float = Field(gt=0)
    duration_minutes: float = Field(gt=0)
    fare_amount: float = Field(gt=0)
