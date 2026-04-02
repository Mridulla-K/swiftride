"""Pricing service API routes."""

from __future__ import annotations

from fastapi import APIRouter
import math
import logging
import pygeohash as pgh
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from shared.redis import get_redis
from app.schemas import (
    PriceRequest, PriceResponse, PricingEstimateRequest, 
    PricingEstimateResponse, GeoJSONFeatureCollection, GeoJSONFeature
)

logger = logging.getLogger(__name__)
router = APIRouter()

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class ExternalServiceError(Exception):
    """Custom exception for external API failures."""
    pass

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(ExternalServiceError),
    reraise=True
)
async def get_google_maps_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Simulate a call to Google Maps Distance Matrix API.
    In a real app, this would use httpx to call the actual API.
    """
    # Simulate flaky API (fails 50% of the time for testing circuit breaker)
    import random
    if random.random() < 0.1: # Increased success rate for normal flow, but still fails
         raise ExternalServiceError("Google Maps API Gateway Timeout")
         
    # Return haversine + some "road" overhead (1.2x)
    return haversine_distance(lat1, lon1, lat2, lon2) * 1.2


VEHICLE_RATES = {
    "bike": {"base_fare": 25.0, "per_km_rate": 8.0, "per_min_rate": 1.2, "min_fare": 35.0},
    "auto": {"base_fare": 35.0, "per_km_rate": 10.0, "per_min_rate": 1.5, "min_fare": 50.0},
    "car": {"base_fare": 50.0, "per_km_rate": 14.0, "per_min_rate": 2.0, "min_fare": 80.0},
}

BASE_FARE = VEHICLE_RATES["car"]["base_fare"]
PER_KM_RATE = VEHICLE_RATES["car"]["per_km_rate"]
PER_MIN_RATE = VEHICLE_RATES["car"]["per_min_rate"]


@router.post("/calculate", response_model=PriceResponse)
async def calculate_fare(payload: PriceRequest) -> PriceResponse:
    """Calculate the estimated fare based on distance, duration, and surge."""
    distance_fare = payload.distance_km * PER_KM_RATE
    time_fare = payload.duration_minutes * PER_MIN_RATE
    
    subtotal = BASE_FARE + distance_fare + time_fare
    total_fare = round(subtotal * payload.surge_multiplier, 2)
    
    return PriceResponse(
        base_fare=BASE_FARE,
        distance_fare=round(distance_fare, 2),
        time_fare=round(time_fare, 2),
        surge_multiplier=payload.surge_multiplier,
        total_fare=total_fare,
    )


@router.get("/config")
async def get_pricing_config():
    """Return the current base rates."""
    return {
        "base_fare": BASE_FARE,
        "per_km_rate": PER_KM_RATE,
        "per_min_rate": PER_MIN_RATE,
        "currency": "INR",
        "vehicle_rates": VEHICLE_RATES,
    }


@router.post("/estimate", response_model=PricingEstimateResponse)
async def estimate_fare(payload: PricingEstimateRequest) -> PricingEstimateResponse:
    """Calculate the estimated fare using Google Maps (with Haversine fallback)."""
    try:
        distance_km = await get_google_maps_distance(
            payload.pickup_lat, payload.pickup_lng, 
            payload.dropoff_lat, payload.dropoff_lng
        )
    except Exception as e:
        logger.warning(f"Maps API failed ({e}), using Haversine fallback for dynamic estimation. Distance may be approximate.")
        
        # Increment metric in Redis
        redis = await get_redis()
        await redis.incr("metrics:maps_api_fallback_total")
        
        distance_km = haversine_distance(
            payload.pickup_lat, payload.pickup_lng, 
            payload.dropoff_lat, payload.dropoff_lng
        )
    
    distance_km = round(distance_km, 2)
    duration_minutes = max(1.0, distance_km / 0.5) # 30km/h = 0.5km/min

    rates = VEHICLE_RATES.get(payload.vehicle_type, VEHICLE_RATES["car"])
    distance_fare = distance_km * rates["per_km_rate"]
    time_fare = duration_minutes * rates["per_min_rate"]
    
    subtotal = rates["base_fare"] + distance_fare + time_fare
    
    redis = await get_redis()
    gh5 = pgh.encode(payload.pickup_lat, payload.pickup_lng, precision=5)
    surge_multiplier_str = await redis.get(f"surge:{gh5}")
    surge_multiplier = float(surge_multiplier_str) if surge_multiplier_str else 1.0
    
    total_fare = max(rates["min_fare"], round(subtotal * surge_multiplier, 2))
    
    return PricingEstimateResponse(
        vehicle_type=payload.vehicle_type,
        distance_km=distance_km,
        base_fare=rates["base_fare"],
        surge_multiplier=surge_multiplier,
        final_fare=total_fare,
        eta_minutes=int(duration_minutes),
    )


@router.get("/surge/zones", response_model=GeoJSONFeatureCollection)
async def get_surge_zones() -> GeoJSONFeatureCollection:
    """Return all active surge regions as a GeoJSON collection."""
    redis = await get_redis()
    active_zones_raw = await redis.smembers("surge:active_zones")
    active_zones = [z if isinstance(z, str) else z.decode('utf-8') for z in active_zones_raw]
    
    features = []
    for gh5 in active_zones:
        multiplier_str = await redis.get(f"surge:{gh5}")
        if not multiplier_str:
            continue
            
        multiplier = float(multiplier_str)
        # pygeohash.bbox returns {'s': lat_min, 'w': lon_min, 'n': lat_max, 'e': lon_max}
        bbox = pgh.bbox(gh5)
        
        # Create a polygon feature for the geohash cell
        features.append(GeoJSONFeature(
            geometry={
                "type": "Polygon",
                "coordinates": [[
                    [bbox['w'], bbox['s']],
                    [bbox['e'], bbox['s']],
                    [bbox['e'], bbox['n']],
                    [bbox['w'], bbox['n']],
                    [bbox['w'], bbox['s']]
                ]]
            },
            properties={
                "geohash": gh5,
                "surge_multiplier": multiplier,
                "label": f"{multiplier}x"
            }
        ))
        
    return GeoJSONFeatureCollection(features=features)
