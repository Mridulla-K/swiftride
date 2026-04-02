"""Redis connection helper."""

from __future__ import annotations

import redis.asyncio as aioredis
import time

from shared.config import get_settings

settings = get_settings()

redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)


async def get_redis() -> aioredis.Redis:
    return redis_client


async def log_cache_hit(metric: str = "cache"):
    """Increment cache hit counter."""
    await redis_client.incr(f"metrics:{metric}:hits")


async def log_cache_miss(metric: str = "cache"):
    """Increment cache miss counter."""
    await redis_client.incr(f"metrics:{metric}:misses")


async def get_cache_metrics(metric: str = "cache") -> dict[str, float | int]:
    """Calculate and return cache hit rate and totals."""
    hits = int(await redis_client.get(f"metrics:{metric}:hits") or 0)
    misses = int(await redis_client.get(f"metrics:{metric}:misses") or 0)
    total = hits + misses
    hit_rate = (hits / total) if total > 0 else 0.0
    return {
        "cache_hit_rate": round(hit_rate, 4),
        "cache_hits": hits,
        "cache_misses": misses,
    }

async def check_rate_limit(redis: aioredis.Redis, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """
    Sliding window rate limit implementation using Redis Sorted Sets.
    Returns (allowed, retry_after_seconds).
    """
    now = time.time()
    window_start = now - window_seconds
    
    # Use a pipeline to ensure atomic operations
    async with redis.pipeline(transaction=True) as pipe:
        # Remove old requests
        pipe.zremrangebyscore(key, 0, window_start)
        # Count requests in window
        pipe.zcard(key)
        # Add current request (using timestamp as both score and member value to ensure uniqueness)
        # However, member must be unique. we can use a timestamp with a small tie-breaker or just timestamp
        # Actually time.time() has high precision, let's use now as score and value
        pipe.zadd(key, {f"{now}": now})
        # Set expiry for the key to avoid memory leak
        pipe.expire(key, window_seconds)
        # To calculate retry_after, we need the oldest timestamp in the current window
        # Get the first item in the sorted set
        pipe.zrange(key, 0, 0, withscores=True)
        
        results = await pipe.execute()
    
    # results[1] is the count before adding the new one
    current_count = results[1]
    
    if current_count >= limit:
        # We need to remove the one we just added since it's rejected
        await redis.zrem(key, f"{now}")
        await redis.incr("metrics:rate_limit:rejects")
        
        # Calculate retry_after. The oldest member is at results[4]
        oldest_records = results[4]
        if oldest_records:
            oldest_time = oldest_records[0][1]
            # Time until the oldest record falls out of the window
            retry_after = max(0, int((oldest_time + window_seconds) - now))
            
            # If for some reason retry_after is 0 (due to timing), set it to 1
            retry_after = max(1, retry_after)
            return False, retry_after
        else:
            return False, window_seconds
            
    return True, 0
