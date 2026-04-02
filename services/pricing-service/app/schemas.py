"""Pydantic schemas for pricing service."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class PriceRequest(BaseModel):
    distance_km: float = Field(gt=0)
    duration_minutes: float = Field(gt=0)
    surge_multiplier: float = Field(default=1.0, ge=1.0)


class PriceResponse(BaseModel):
    base_fare: float
    distance_fare: float
    time_fare: float
    surge_multiplier: float
    total_fare: float
    currency: str = "USD"


class PricingEstimateRequest(BaseModel):
    pickup_lat: float
    pickup_lng: float
    dropoff_lat: float
    dropoff_lng: float
    vehicle_type: str = Field(default="car", pattern="^(bike|auto|car)$")


class PricingEstimateResponse(BaseModel):
    vehicle_type: str
    distance_km: float
    base_fare: float
    surge_multiplier: float
    final_fare: float
    eta_minutes: int
    currency: str = "INR"


class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: dict[str, Any]
    properties: dict[str, Any]


class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[GeoJSONFeature]
