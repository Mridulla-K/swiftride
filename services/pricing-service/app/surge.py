"""Background periodic task for dynamic surge pricing calculation."""

import asyncio
import logging
from datetime import datetime, timezone
import pygeohash as pgh

from shared.redis import get_redis

logger = logging.getLogger(__name__)


def calculate_fare(distance_km: float, surge_multiplier: float) -> tuple[float, float, float]:
    """
    Calculate the estimated fare based on distance and surge.
    Returns (base_fare, surge_multiplier, final_fare).
    """
    base_fare = 2.50 + (distance_km * 1.20)
    final_fare = round(base_fare * surge_multiplier, 2)
    # Enforce min fare floor
    final_fare = max(5.00, final_fare)
    
    return round(base_fare, 2), surge_multiplier, final_fare


def compute_multiplier(demand: int, supply: int) -> float:
    """
    Calculate the surge multiplier.
    surge_multiplier = max(1.0, round(demand / max(supply, 1), 1))
    Cap at 3.0x.
    """
    multiplier = max(1.0, round(demand / max(supply, 1), 1))
    return min(3.0, multiplier)


async def calculate_surge_multipliers():
    """Background task to compute dynamic surge multipliers every 30s."""
    logger.info("🚀 Starting dynamic pricing surge engine...")
    
    while True:
        try:
            redis = await get_redis()
            
            active_rides = await redis.zrange("active_rides:locations", 0, -1)
            
            demand_by_zone = {}
            if active_rides:
                positions = await redis.geopos("active_rides:locations", *active_rides)
                for i, pos in enumerate(positions):
                    if pos:
                        lng, lat = pos
                        gh5 = pgh.encode(lat, lng, precision=5)
                        demand_by_zone[gh5] = demand_by_zone.get(gh5, 0) + 1
            
            available_drivers_raw = await redis.smembers("drivers:available")
            available_drivers = {d if isinstance(d, str) else d.decode('utf-8') for d in available_drivers_raw}
            
            new_active_zones = set()
            
            for zone, demand in demand_by_zone.items():
                if demand == 0: continue
                new_active_zones.add(zone)
                
                lat, lng = pgh.decode(zone)
                
                nearby_drivers = await redis.georadius("drivers:locations", lng, lat, 5, unit="km")
                nearby_drivers_str = {d if isinstance(d, str) else d.decode('utf-8') for d in nearby_drivers}
                
                supply = len(nearby_drivers_str.intersection(available_drivers))
                
                multiplier = compute_multiplier(demand, supply)
                
                await redis.setex(f"surge:{zone}", 60, str(multiplier))
                await redis.sadd("surge:active_zones", zone)
                
                now_iso = datetime.now(timezone.utc).isoformat()
                history_entry = f"{multiplier}:{now_iso}"
                await redis.lpush(f"surge:history:{zone}", history_entry)
                await redis.ltrim(f"surge:history:{zone}", 0, 9)
            
            current_active_zones_raw = await redis.smembers("surge:active_zones")
            current_active_zones = {z if isinstance(z, str) else z.decode('utf-8') for z in current_active_zones_raw}
            
            for old_zone in current_active_zones - new_active_zones:
                await redis.srem("surge:active_zones", old_zone)
                # optionally clean up history or leave it for TTL (though lists don't have TTL directly unless we set it)
                # Let's set a TTL on the history list just in case it's left abandoned
                await redis.expire(f"surge:history:{old_zone}", 3600)
                
        except Exception as e:
            logger.error(f"Error in surge calculation loop: {e}", exc_info=True)
            
        await asyncio.sleep(30)
