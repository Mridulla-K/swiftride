"""Matcher logic for driver selection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import text

from shared.database import async_session
from shared.redis import get_redis

logger = logging.getLogger(__name__)

MATCHING_RADIUS_KM = 5.0
DISTANCE_WEIGHT = 0.7
RATING_WEIGHT = 0.3


@dataclass
class CandidateDriver:
    driver_id: str
    distance_km: float
    rating: float
    score: float


async def get_driver_rating_fallback(driver_id: str) -> float:
    """Fetch driver rating from PostgreSQL if not in Redis."""
    async with async_session() as session:
        result = await session.execute(
            text("SELECT rating FROM drivers WHERE id = :id"),
            {"id": driver_id}
        )
        row = result.fetchone()
        if row:
            return float(row[0])
    return 5.0  # Default if not found


async def calculate_score(distance_km: float, rating: float) -> float:
    """Calculate match score (lower is better).
    Score = (distance * 0.7) + ((5.0 - rating) * 0.3)
    """
    return (distance_km * DISTANCE_WEIGHT) + ((5.0 - rating) * RATING_WEIGHT)


async def find_best_candidates(
    pickup_lat: float,
    pickup_lng: float,
    limit: int = 3
) -> List[CandidateDriver]:
    """Find and score the best available drivers near the pickup location.

    Returns a list of CandidateDriver ordered by score (lowest first).
    """
    redis = await get_redis()
    
    # Get all drivers within radius
    results = await redis.georadius(
        "drivers:locations",
        pickup_lng, pickup_lat,
        MATCHING_RADIUS_KM,
        unit="km",
        withdist=True,
    )
    
    if not results:
        return []

    candidates = []
    
    # Process each driver found in the radius
    for result in results:
        driver_id_str, distance = result[0], float(result[1])
        
        # 1. Check availability
        status = await redis.get(f"driver:status:{driver_id_str}")
        if status != "available":
            # Skip busy or offline drivers
            continue
            
        # 2. Fetch rating
        rating_str = await redis.get(f"driver:rating:{driver_id_str}")
        if rating_str is not None:
            rating = float(rating_str)
        else:
            # Fallback to DB
            logger.info("Rating cache miss for %s. Falling back to DB.", driver_id_str)
            rating = await get_driver_rating_fallback(driver_id_str)
            # Cache it for next time
            await redis.set(f"driver:rating:{driver_id_str}", rating)
            
        # 3. Calculate score
        score = await calculate_score(distance, rating)
        
        candidates.append(CandidateDriver(
            driver_id=driver_id_str,
            distance_km=distance,
            rating=rating,
            score=score
        ))

    # Sort by score ascending (lower score is better)
    candidates.sort(key=lambda x: x.score)
    
    # Return top N
    return candidates[:limit]
