"""Ride service — FastAPI application entry-point."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.database import init_db
from shared.kafka import create_consumer
from shared.redis import get_redis
from app.routes import router
from app.routes_ws import router as ws_router
from app.websocket import manager
from app.models import Ride, RideStatus
from shared.database import async_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def consume_kafka_events(app: FastAPI) -> None:
    """Listen for ride events and update status."""
    consumer = await create_consumer("ride.matched", "ride.failed", group_id="ride-service")
    app.state.kafka_consumer = consumer
    logger.info("🔄 Ride event consumer started — listening on ride.matched and ride.failed")

    try:
        while True:
            msg = await consumer.poll(timeout=1.0)
            if msg is None:
                continue
            try:
                data = msg["value"]
                topic = msg["topic"]
                logger.info("Received event on %s: %s", topic, data)

                async with async_session() as db:
                    from sqlalchemy import select
                    import uuid

                    result = await db.execute(
                        select(Ride).where(Ride.id == uuid.UUID(data["ride_id"]))
                    )
                    ride = result.scalar_one_or_none()
                    if not ride:
                        continue

                    should_cache = False

                    if topic == "ride.matched" and ride.status == RideStatus.requested:
                        ride.status = RideStatus.matched
                        ride.driver_id = uuid.UUID(data["driver_id"])
                        should_cache = True
                        await db.commit()

                        await manager.broadcast(
                            data["ride_id"],
                            {
                                "type": "ride.matched",
                                "driver_id": data["driver_id"],
                                "driver_name": data.get("driver_name", "N/A"),
                                "vehicle": data.get("vehicle", {}),
                                "driver_rating": data.get("driver_rating"),
                                "estimated_fare_inr": data.get("estimated_fare_inr"),
                                "distance_km": data.get("distance_km"),
                                "estimated_pickup_seconds": data.get("estimated_pickup_seconds"),
                            }
                        )

                    elif topic == "ride.failed" and ride.status == RideStatus.requested:
                        ride.status = RideStatus.failed
                        should_cache = True
                        logger.warning("❌ Ride %s failed to match", data["ride_id"])

                        redis = await get_redis()
                        await redis.zrem("active_rides:locations", data["ride_id"])
                        await db.commit()

                    if should_cache:
                        try:
                            import json
                            from app.schemas import RideResponse
                            redis = await get_redis()
                            await db.refresh(ride)
                            ride_dict = RideResponse.model_validate(ride).model_dump(mode='json')
                            await redis.set(
                                f"ride:active:{ride.id}",
                                json.dumps(ride_dict),
                                ex=7200
                            )
                        except Exception as e:
                            logger.error("Failed to cache active ride: %s", e)
            except Exception as e:
                logger.exception("Ride event processing failed: %s", e)
    except asyncio.CancelledError:
        logger.info("Stopping Kafka consumer...")
    finally:
        await consumer.stop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(consume_kafka_events(app))
    yield
    task.cancel()
    try:
        await task
    except Exception:
        pass


app = FastAPI(
    title="SwiftRide · Ride Service",
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

app.include_router(router, prefix="/api/v1/rides", tags=["rides"])
app.include_router(ws_router, prefix="/api/v1/rides", tags=["rides-ws"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ride-service"}


@app.get("/metrics")
async def get_metrics():
    metrics_data = await get_cache_metrics("active_rides")  # just a placeholder metric name for cache hit
    redis = await get_redis()
    rate_limits = int(await redis.get("metrics:rate_limit:rejects") or 0)
    metrics_data["rate_limited_requests_total"] = rate_limits
    return metrics_data
