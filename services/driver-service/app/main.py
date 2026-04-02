"""Driver service — FastAPI application entry-point."""

import asyncio
import json
import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from shared.database import init_db, async_session
from shared.redis import get_redis
from shared.kafka import create_consumer
from app.models import Driver
from app.routes import router
from app.websocket import router as ws_router
from app.routes_tracking_ws import router as ws_tracking_router
from app.tracking_ws import manager as tracking_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def consume_driver_locations(app: FastAPI):
    """Listen for driver location events and broadcast them to tracking clients."""
    consumer = await create_consumer("driver.location", group_id="driver-service-location-broadcaster")
    app.state.kafka_consumer_locations = consumer
    logger.info("🔄 Driver location consumer started — listening on driver.location")
    redis = await get_redis()

    try:
        while True:
            msg = await consumer.poll(timeout=1.0)
            if msg is None:
                continue
            
            data = msg["value"]
            driver_id = data.get("driver_id")
            if not driver_id:
                continue

            # Find the ride_id this driver is associated with
            ride_id = await redis.get(f"driver_map:{driver_id}")
            if ride_id:
                await tracking_manager.broadcast(
                    ride_id,
                    {
                        "type": "driver.location.update",
                        "lat": data["lat"],
                        "lng": data["lng"],
                    }
                )
    finally:
        await consumer.stop()


async def sync_locations():
    """Periodically sync driver locations from Redis to PostgreSQL."""
    while True:
        try:
            await asyncio.sleep(30)
            redis = await get_redis()
            
            cursor = '0'
            keys = []
            while cursor != 0:
                cursor, iter_keys = await redis.scan(cursor=cursor, match="driver:loc:*", count=100)
                keys.extend(iter_keys)
            
            if not keys:
                continue

            values = await redis.mget(keys)
            
            updates = {}
            for key, val in zip(keys, values):
                if val:
                    driver_id_str = key.split(":")[-1]
                    try:
                        data = json.loads(val)
                        updates[uuid.UUID(driver_id_str)] = (data['lat'], data['lng'])
                    except (json.JSONDecodeError, KeyError, ValueError):
                        pass

            if updates:
                async with async_session() as session:
                    for driver_id, (lat, lng) in updates.items():
                        result = await session.execute(select(Driver).where(Driver.id == driver_id))
                        driver = result.scalar_one_or_none()
                        if driver:
                            driver.current_lat = lat
                            driver.current_lng = lng
                    await session.commit()
        except asyncio.CancelledError:
            break
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background tasks
    app.state.sync_task = asyncio.create_task(sync_locations())
    app.state.consume_task = asyncio.create_task(consume_driver_locations(app))
    yield
    # Clean up background tasks
    app.state.sync_task.cancel()
    app.state.consume_task.cancel()
    await app.state.sync_task
    await app.state.consume_task

app = FastAPI(
    title="SwiftRide · Driver Service",
    version="1.0.0",
    lifespan=lifespan,
)

# TODO: restrict to specific origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1/drivers", tags=["drivers"])
app.include_router(ws_router, prefix="/api/v1/drivers", tags=["drivers-ws"])
app.include_router(ws_tracking_router, prefix="/api/v1/drivers", tags=["drivers-tracking-ws"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "driver-service"}
