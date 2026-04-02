"""Pricing service — FastAPI application entry-point."""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import router
from app.surge import calculate_surge_multipliers

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the background task
    task = asyncio.create_task(calculate_surge_multipliers())
    yield
    # Stop the background task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title="SwiftRide · Pricing Service",
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

app.include_router(router, prefix="/api/v1/pricing", tags=["pricing"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "pricing-service"}
