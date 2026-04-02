"""Matching service API routes — proximity search and manual match trigger."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

import json
import geohash

from shared.redis import get_redis, log_cache_hit, log_cache_miss
from shared.kafka import create_producer, publish, AsyncKafkaConsumer
from app.schemas import MatchRequest, MatchResult, NearbyDriver

router = APIRouter()

MATCHING_RADIUS_KM = 5.0
AVG_SPEED_KM_PER_MIN = 0.5  # ~30 km/h city driving


@router.get("/nearby", response_model=list[NearbyDriver])
async def find_nearby_drivers(lat: float, lng: float, radius_km: float = MATCHING_RADIUS_KM):
    """Find drivers within radius using Redis GEORADIUS."""
    redis = await get_redis()
    
    ghash = geohash.encode(lat, lng, precision=5)
    cache_key = f"nearby:{ghash}"
    
    cached_result = await redis.get(cache_key)
    if cached_result:
        await log_cache_hit("nearby")
        return [NearbyDriver(**d) for d in json.loads(cached_result)]
        
    await log_cache_miss("nearby")

    results = await redis.georadius(
        "drivers:locations", lng, lat, radius_km, unit="km", withcoord=False, withdist=True, sort="ASC",
    )
    drivers = []
    for member, dist in results:
        drivers.append(NearbyDriver(driver_id=member, distance_km=round(float(dist), 2)))
    
    if drivers:
        await redis.set(cache_key, json.dumps([d.model_dump(mode='json') for d in drivers]), ex=5)
        
    return drivers


@router.post("/match", response_model=MatchResult)
async def match_ride(payload: MatchRequest):
    """Find the closest available driver and publish ride.matched event."""
    redis = await get_redis()
    results = await redis.georadius(
        "drivers:locations",
        payload.pickup_lng,
        payload.pickup_lat,
        MATCHING_RADIUS_KM,
        unit="km",
        withdist=True,
        sort="ASC",
        count=1,
    )

    if not results:
        raise HTTPException(status_code=404, detail="No available drivers nearby")

    driver_id_str, distance = results[0][0], float(results[0][1])
    eta_seconds = int((distance / AVG_SPEED_KM_PER_MIN) * 60)

    match_result = MatchResult(
        ride_id=payload.ride_id,
        driver_id=uuid.UUID(driver_id_str),
        rider_id=payload.rider_id,
        distance_km=round(distance, 2),
        estimated_pickup_seconds=eta_seconds,
        matched_at=datetime.now(timezone.utc),
    )

    # Publish ride.matched to Kafka
    try:
        producer = await create_producer()
        await publish(producer, "ride.matched", {
            "ride_id": str(match_result.ride_id),
            "driver_id": str(match_result.driver_id),
            "rider_id": str(match_result.rider_id),
            "estimated_pickup_seconds": match_result.estimated_pickup_seconds,
            "matched_at": match_result.matched_at.isoformat(),
        }, key=str(match_result.ride_id))
        await producer.stop()
    except Exception:
        pass  # Non-critical

    return match_result


@router.get("/health/kafka")
async def kafka_health(request: Request):
    consumer: AsyncKafkaConsumer = getattr(request.app.state, "kafka_consumer", None)
    if not consumer:
        raise HTTPException(status_code=503, detail="Kafka consumer not initialized")
    
    return await consumer.get_health("ride.requested")
