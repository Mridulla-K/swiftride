"""Driver service API routes."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db, async_session
from shared.kafka import create_producer, publish
from shared.redis import get_redis
from app.models import Driver, DriverStatus
from app.schemas import DriverCreate, DriverResponse, LocationUpdate, StatusUpdate, WSLocationUpdate

router = APIRouter()


async def set_driver_offline(driver_id: uuid.UUID) -> None:
    async with async_session() as session:
        result = await session.execute(select(Driver).where(Driver.id == driver_id))
        driver = result.scalar_one_or_none()
        if driver:
            driver.status = DriverStatus.offline
            await session.commit()


@router.post("/", response_model=DriverResponse, status_code=status.HTTP_201_CREATED)
async def register_driver(payload: DriverCreate, db: AsyncSession = Depends(get_db)):
    driver = Driver(**payload.model_dump())
    db.add(driver)
    await db.flush()
    await db.refresh(driver)

    # Sync status and rating to Redis
    redis = await get_redis()
    await redis.set(f"driver:status:{driver.id}", driver.status.value)
    await redis.set(f"driver:rating:{driver.id}", driver.rating)
    if driver.status == DriverStatus.available:
        await redis.sadd("drivers:available", str(driver.id))

    return driver


@router.get("/{driver_id}", response_model=DriverResponse)
async def get_driver(driver_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver


@router.get("/", response_model=list[DriverResponse])
async def list_drivers(
    status_filter: str | None = None,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    query = select(Driver)
    if status_filter:
        query = query.where(Driver.status == status_filter)
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()


@router.put("/{driver_id}/location", response_model=DriverResponse)
async def update_location(
    driver_id: uuid.UUID,
    payload: LocationUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    driver.current_lat = payload.lat
    driver.current_lng = payload.lng
    await db.flush()
    await db.refresh(driver)

    # Cache latest location, status, and rating in Redis
    redis = await get_redis()
    await redis.geoadd("drivers:locations", (payload.lng, payload.lat, str(driver_id)))
    await redis.set(f"driver:status:{driver.id}", driver.status.value)
    await redis.set(f"driver:rating:{driver.id}", driver.rating)

    # Publish location event to Kafka
    try:
        producer = await create_producer()
        await publish(producer, "driver.location", {
            "driver_id": str(driver_id),
            "lat": payload.lat,
            "lng": payload.lng,
            "status": driver.status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, key=str(driver_id))
        await producer.stop()
    except Exception:
        pass  # Non-critical — don't block the response

    return driver


@router.put("/{driver_id}/status", response_model=DriverResponse)
async def update_status(
    driver_id: uuid.UUID,
    payload: StatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    driver.status = DriverStatus(payload.status)
    await db.flush()
    await db.refresh(driver)

    # Sync status and rating to Redis
    redis = await get_redis()
    await redis.set(f"driver:status:{driver.id}", driver.status.value)
    await redis.set(f"driver:rating:{driver.id}", driver.rating)
    if driver.status == DriverStatus.available:
        await redis.sadd("drivers:available", str(driver.id))
    else:
        await redis.srem("drivers:available", str(driver.id))

    return driver
