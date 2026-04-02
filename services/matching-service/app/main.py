"""Matching service — FastAPI application entry-point."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.database import init_db
from app.routes import router
from app.consumer import consume_ride_requests, consume_driver_disconnects

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB (create matches table)
    await init_db()
    
    # Start background Kafka consumers
    task1 = asyncio.create_task(consume_ride_requests(app))
    task2 = asyncio.create_task(consume_driver_disconnects(app))
    
    yield
    
    task1.cancel()
    task2.cancel()
    try:
        await asyncio.gather(task1, task2, return_exceptions=True)
    except Exception:
        pass


app = FastAPI(
    title="SwiftRide · Matching Service",
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

app.include_router(router, prefix="/api/v1/matching", tags=["matching"])


from shared.redis import get_redis, get_cache_metrics

@app.get("/health")
async def health():
    return {"status": "ok", "service": "matching-service"}


@app.get("/metrics")
async def get_metrics():
    metrics_data = await get_cache_metrics("nearby")
    redis = await get_redis()
    rate_limits = int(await redis.get("metrics:rate_limit:rejects") or 0)
    metrics_data["rate_limited_requests_total"] = rate_limits
    return metrics_data

