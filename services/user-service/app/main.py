"""User service — FastAPI application entry-point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.database import init_db
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="SwiftRide · User Service",
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

app.include_router(router, prefix="/api/v1/users", tags=["users"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "user-service"}
