"""Pydantic schemas for matching service."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MatchRequest(BaseModel):
    ride_id: uuid.UUID
    rider_id: uuid.UUID
    pickup_lat: float = Field(ge=-90, le=90)
    pickup_lng: float = Field(ge=-180, le=180)
    dropoff_lat: float = Field(ge=-90, le=90)
    dropoff_lng: float = Field(ge=-180, le=180)


class MatchResult(BaseModel):
    ride_id: uuid.UUID
    driver_id: uuid.UUID
    rider_id: uuid.UUID
    distance_km: float
    estimated_pickup_seconds: int
    matched_at: datetime


class NearbyDriver(BaseModel):
    driver_id: str
    distance_km: float
