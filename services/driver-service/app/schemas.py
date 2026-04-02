"""Pydantic schemas for driver service."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class DriverCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=7, max_length=20)
    email: EmailStr
    license_number: str = Field(min_length=1, max_length=50)
    vehicle_model: str = Field(min_length=1, max_length=100)
    vehicle_plate: str = Field(min_length=1, max_length=20)


class DriverResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    phone: str
    email: str
    license_number: str
    vehicle_model: str
    vehicle_plate: str
    status: str
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    rating: float
    created_at: datetime

    model_config = {"from_attributes": True}


class LocationUpdate(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class StatusUpdate(BaseModel):
    status: str = Field(pattern="^(available|busy|offline)$")


class WSLocationUpdate(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    timestamp: datetime
