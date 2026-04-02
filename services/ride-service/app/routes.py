"""Ride service API routes."""

from __future__ import annotations

import logging
import math
import random
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.kafka import create_producer, publish, AsyncKafkaConsumer
from shared.redis import get_redis
from app.models import Ride, RideStatus
from app.schemas import RideRequest, RideResponse, RideComplete

SYNTHETIC_DRIVER_POOL_KEY = "drivers:synthetic:pool"
MIN_DRIVER_RADIUS_KM = 0.1
MAX_DRIVER_RADIUS_KM = 10.0
TARGET_SYNTHETIC_DRIVERS = 100


def _random_point_around(lat: float, lng: float, min_radius_km: float, max_radius_km: float) -> tuple[float, float]:
    distance_km = random.uniform(min_radius_km, max_radius_km)
    bearing = random.uniform(0, 2 * math.pi)
    earth_radius_km = 6371.0

    lat_rad = math.radians(lat)
    lng_rad = math.radians(lng)
    angular_distance = distance_km / earth_radius_km

    new_lat = math.asin(
        math.sin(lat_rad) * math.cos(angular_distance)
        + math.cos(lat_rad) * math.sin(angular_distance) * math.cos(bearing)
    )
    new_lng = lng_rad + math.atan2(
        math.sin(bearing) * math.sin(angular_distance) * math.cos(lat_rad),
        math.cos(angular_distance) - math.sin(lat_rad) * math.sin(new_lat),
    )

    return (math.degrees(new_lat), math.degrees(new_lng))


async def _ensure_synthetic_drivers_near_pickup(redis, pickup_lat: float, pickup_lng: float) -> None:
    existing = await redis.smembers(SYNTHETIC_DRIVER_POOL_KEY)
    driver_ids = [d if isinstance(d, str) else d.decode("utf-8") for d in existing]

    while len(driver_ids) < TARGET_SYNTHETIC_DRIVERS:
        new_id = str(uuid.uuid4())
        driver_ids.append(new_id)
        await redis.sadd(SYNTHETIC_DRIVER_POOL_KEY, new_id)

    for driver_id in driver_ids[:TARGET_SYNTHETIC_DRIVERS]:
        lat, lng = _random_point_around(pickup_lat, pickup_lng, MIN_DRIVER_RADIUS_KM, MAX_DRIVER_RADIUS_KM)
        await redis.geoadd("drivers:locations", (lng, lat, driver_id))
        await redis.set(f"driver:status:{driver_id}", "available", ex=3600)
        await redis.set(f"driver:rating:{driver_id}", str(round(random.uniform(4.2, 5.0), 1)), ex=3600)

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, ride_id: str):
        await websocket.accept()
        if ride_id not in self.active_connections:
            self.active_connections[ride_id] = []
        self.active_connections[ride_id].append(websocket)

    def disconnect(self, websocket: WebSocket, ride_id: str):
        if ride_id in self.active_connections:
            self.active_connections[ride_id].remove(websocket)
            if not self.active_connections[ride_id]:
                del self.active_connections[ride_id]

    async def send_personal_message(self, message: dict, ride_id: str):
        if ride_id in self.active_connections:
            for connection in self.active_connections[ride_id]:
                await connection.send_json(message)
        
        # Also send to global listeners
        if "all" in self.active_connections:
            for connection in self.active_connections["all"]:
                await connection.send_json(message)

    async def broadcast(self, message: dict):
        """Send message to the 'all' group (Ops Center)."""
        if "all" in self.active_connections:
            for connection in self.active_connections["all"]:
                await connection.send_json(message)

manager = ConnectionManager()
router = APIRouter()


from fastapi.responses import JSONResponse
from shared.redis import get_redis, check_rate_limit, log_cache_hit, log_cache_miss

@router.post("/", response_model=RideResponse, status_code=status.HTTP_201_CREATED)
async def request_ride(payload: RideRequest, db: AsyncSession = Depends(get_db)):
    redis = await get_redis()
    user_id_str = str(payload.rider_id)
    rate_limit_key = f"ratelimit:rider:{user_id_str}"
    
    allowed, retry_after = await check_rate_limit(redis, rate_limit_key, 3, 60)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limit_exceeded",
                "retry_after_seconds": retry_after,
                "limit": 3,
                "window": "60s"
            }
        )
        
    ride = Ride(
        rider_id=payload.rider_id,
        pickup_lat=payload.pickup_lat,
        pickup_lng=payload.pickup_lng,
        dropoff_lat=payload.dropoff_lat,
        dropoff_lng=payload.dropoff_lng,
        pickup_address=payload.pickup_address,
        dropoff_address=payload.dropoff_address,
        status=RideStatus.requested,
    )
    db.add(ride)
    await db.flush()
    await db.refresh(ride)

    # Store in Redis for pricing surge calculation
    redis = await get_redis()
    await redis.geoadd("active_rides:locations", (ride.pickup_lng, ride.pickup_lat, str(ride.id)))

    # Ensure driver density around chosen pickup (100m to 10km radius)
    await _ensure_synthetic_drivers_near_pickup(redis, ride.pickup_lat, ride.pickup_lng)

    # Publish ride.requested to Kafka
    try:
        producer = await create_producer()
        await publish(producer, "ride.requested", {
            "ride_id": str(ride.id),
            "rider_id": str(ride.rider_id),
            "pickup_lat": ride.pickup_lat,
            "pickup_lng": ride.pickup_lng,
            "dropoff_lat": ride.dropoff_lat,
            "dropoff_lng": ride.dropoff_lng,
            "vehicle_type": payload.vehicle_type,
            "requested_at": ride.requested_at.isoformat() if ride.requested_at else datetime.now(timezone.utc).isoformat(),
        }, key=str(ride.id), headers={"retry_count": "0"})
        await producer.stop()
    except Exception as e:
        logger.error("Failed to publish ride request: %s", e)

    return ride


@router.get("/{ride_id}", response_model=RideResponse)
async def get_ride(ride_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    redis = await get_redis()
    cache_key = f"ride:active:{ride_id}"
    cached_ride = await redis.get(cache_key)
    if cached_ride:
        import json
        from app.schemas import RideResponse
        await log_cache_hit("active_rides")
        return RideResponse(**json.loads(cached_ride))
        
    await log_cache_miss("active_rides")
    result = await db.execute(select(Ride).where(Ride.id == ride_id))
    ride = result.scalar_one_or_none()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    return ride


@router.get("/", response_model=list[RideResponse])
async def list_rides(
    rider_id: uuid.UUID | None = None,
    driver_id: uuid.UUID | None = None,
    status_filter: str | None = None,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    query = select(Ride)
    if rider_id:
        query = query.where(Ride.rider_id == rider_id)
    if driver_id:
        query = query.where(Ride.driver_id == driver_id)
    if status_filter:
        query = query.where(Ride.status == status_filter)
    result = await db.execute(query.order_by(Ride.requested_at.desc()).offset(skip).limit(limit))
    return result.scalars().all()


@router.put("/{ride_id}/cancel", response_model=RideResponse)
async def cancel_ride(ride_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Ride).where(Ride.id == ride_id))
    ride = result.scalar_one_or_none()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    if ride.status in (RideStatus.completed, RideStatus.cancelled):
        raise HTTPException(status_code=400, detail=f"Cannot cancel ride in '{ride.status.value}' state")

    ride.status = RideStatus.cancelled
    ride.cancelled_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(ride)
    
    redis = await get_redis()
    await redis.zrem("active_rides:locations", str(ride.id))
    
    return ride


@router.put("/{ride_id}/start", response_model=RideResponse)
async def start_ride(ride_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Ride).where(Ride.id == ride_id))
    ride = result.scalar_one_or_none()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    if ride.status != RideStatus.matched and ride.status != RideStatus.driver_en_route:
        raise HTTPException(status_code=400, detail="Ride must be matched before starting")

    ride.status = RideStatus.in_progress
    ride.started_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(ride)
    
    phone = f"+919876543210" # Mocked phone number
    logger.info(f"[MOCK:SMS] Driver en route alert sent to {phone}")
    
    return ride


@router.put("/{ride_id}/complete", response_model=RideResponse)
async def complete_ride(
    ride_id: uuid.UUID,
    payload: RideComplete,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Ride).where(Ride.id == ride_id))
    ride = result.scalar_one_or_none()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    if ride.status != RideStatus.in_progress:
        raise HTTPException(status_code=400, detail="Ride must be in progress to complete")

    ride.status = RideStatus.completed
    ride.distance_km = payload.distance_km
    ride.duration_minutes = payload.duration_minutes
    ride.fare_amount = payload.fare_amount
    ride.completed_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(ride)
    
    redis = await get_redis()
    await redis.zrem("active_rides:locations", str(ride.id))
    
    logger.info(f"[MOCK:STRIPE] Charged {ride.fare_amount} to customer {ride.rider_id}")
    
    return ride


@router.websocket("/ws/rides/all")
async def ride_all_websocket(websocket: WebSocket):
    await manager.connect(websocket, "all")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, "all")


@router.websocket("/ws/rides/{ride_id}")
async def ride_websocket(websocket: WebSocket, ride_id: str):
    await manager.connect(websocket, ride_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, ride_id)


@router.get("/health/kafka")
async def kafka_health(request: Request):
    consumer: AsyncKafkaConsumer = getattr(request.app.state, "kafka_consumer", None)
    if not consumer:
        raise HTTPException(status_code=503, detail="Kafka consumer not initialized")
    
    # We track lag for ride.matched topic
    return await consumer.get_health("ride.matched")
