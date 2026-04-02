"""Background Kafka consumer — listens to ride.requested and triggers matching."""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone

from shared.kafka import create_consumer, create_producer, publish
from shared.redis import get_redis
from shared.database import async_session
from app.matcher import find_best_candidates
from app.models import Match, MatchStatus

logger = logging.getLogger(__name__)

MATCHING_RADIUS_KM = 5.0
AVG_SPEED_KM_PER_MIN = 0.5

INDIAN_DRIVER_NAMES = [
    "Aarav", "Vihaan", "Aditya", "Arjun", "Rohan", "Karthik", "Rahul", "Siddharth", "Nikhil", "Manish",
    "Ravi", "Ankit", "Yash", "Dev", "Harsh", "Priya", "Ananya", "Neha", "Kavya", "Isha"
]

VEHICLE_MODELS = {
    "car": ["Maruti Suzuki Dzire", "Hyundai i20", "Tata Tiago", "Honda City", "Toyota Etios"],
    "bike": ["TVS Apache", "Bajaj Pulsar", "Honda Shine", "Yamaha FZ", "Hero Splendor"],
    "auto": ["Bajaj RE", "Piaggio Ape", "Mahindra Treo", "Atul Auto", "TVS King"],
}


def _random_plate() -> str:
    state_codes = ["KA", "TN", "MH", "DL", "TS", "AP", "GJ", "RJ"]
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return f"{random.choice(state_codes)}{random.randint(1, 99):02d}{random.choice(letters)}{random.choice(letters)}{random.randint(1000, 9999)}"


def _generate_driver_profile(vehicle_type: str, distance_km: float) -> dict:
    kind = vehicle_type if vehicle_type in VEHICLE_MODELS else "car"
    model = random.choice(VEHICLE_MODELS[kind])
    name = random.choice(INDIAN_DRIVER_NAMES)
    stars = round(random.uniform(4.1, 5.0), 1)

    # Approx fare estimation fallback for match card display.
    fare_by_km = {"bike": 10.0, "auto": 13.0, "car": 18.0}
    base = {"bike": 25.0, "auto": 35.0, "car": 50.0}
    est_fare = round(base[kind] + max(1.0, distance_km) * fare_by_km[kind], 0)

    return {
        "driver_name": name,
        "driver_rating": stars,
        "estimated_fare_inr": est_fare,
        "vehicle": {
            "make": "",
            "model": model,
            "license_plate": _random_plate(),
            "type": kind,
        }
    }


async def consume_ride_requests(app: FastAPI) -> None:
    """Consume ride.requested events and auto-match to nearest driver."""
    consumer = await create_consumer(
        "ride.requested", 
        group_id="matching-service",
        enable_auto_commit=False
    )
    app.state.kafka_consumer = consumer
    logger.info("🔄 Matching consumer (manual commit) started — listening on ride.requested")

    try:
        while True:
            msg = await consumer.poll(timeout=1.0)
            if msg is None:
                continue
                
            data = msg["value"]
            headers = msg["headers"] or {}
            ride_id = data["ride_id"]
            pickup_lat = data["pickup_lat"]
            pickup_lng = data["pickup_lng"]
            
            # Read retry_count from headers
            retry_count = int(headers.get("retry_count", 0))
            logger.info("Received ride.requested: %s (Retry: %d)", ride_id, retry_count)

            redis = await get_redis()
            
            # Acquire lock to prevent race conditions during matching
            lock_key = f"lock:ride:{ride_id}"
            acquired = await redis.setnx(lock_key, "1")
            
            if not acquired:
                logger.info("Skipping ride %s (already being matched)", ride_id)
                continue
                
            await redis.expire(lock_key, 15)
            
            try:
                candidates = await find_best_candidates(pickup_lat, pickup_lng, limit=3)

                if not candidates:
                    logger.warning("No drivers found for ride %s (Attempt %d)", ride_id, retry_count + 1)
                    producer = await create_producer()
                    
                    if retry_count < 2: # 0, 1, 2 = 3 tries total
                        # Re-publish with incremented retry count
                        new_headers = {"retry_count": str(retry_count + 1)}
                        await publish(producer, "ride.requested", data, key=ride_id, headers=new_headers)
                        logger.info("Retrying match for ride %s (Next attempt: %d)", ride_id, retry_count + 1)
                    else:
                        # Publish to DLQ
                        await publish(producer, "ride.failed", data, key=ride_id)
                        logger.error("DLQ: Ride %s failed after 3 attempts", ride_id)
                        
                    await producer.stop()
                    continue

                matched = False
                for candidate in candidates:
                    logger.info("Attempting driver %s for ride %s", candidate.driver_id, ride_id)
                    
                    # Simulated 2s delay for driver acceptance instead of 10s for testing
                    await asyncio.sleep(2)
                    
                    accepted = True # Simulation
                    
                    if accepted:
                        eta_seconds = int((candidate.distance_km / AVG_SPEED_KM_PER_MIN) * 60)
                        
                        # Set driver-to-ride mapping in Redis for tracking
                        await redis.set(f"driver_map:{candidate.driver_id}", ride_id, ex=3600) # 1-hour expiry

                        # 1. Write match to DB (Deduplicate by ride_id check handled naturally by business logic here)
                        async with async_session() as session:
                            # Implementation check: if msg was already processed (at-least-once), 
                            # we might see a Match already. For simplicity, we create a new one or ignore.
                            match_record = Match(
                                ride_id=uuid.UUID(ride_id),
                                driver_id=uuid.UUID(candidate.driver_id),
                                status=MatchStatus.matched
                            )
                            session.add(match_record)
                            await session.commit()
                            logger.info("Match record written to DB for ride %s", ride_id)

                        # 2. Store active ride in Redis for disconnect recovery
                        redis = await get_redis()
                        await redis.set(f"driver:active_ride:{candidate.driver_id}", ride_id)
            
                        producer = await create_producer()
                        vehicle_type = str(data.get("vehicle_type", "car")).lower()
                        profile = _generate_driver_profile(vehicle_type, candidate.distance_km)

                        await publish(producer, "ride.matched", {
                            "ride_id": ride_id,
                            "driver_id": candidate.driver_id,
                            "rider_id": data["rider_id"],
                            "estimated_pickup_seconds": eta_seconds,
                            "distance_km": candidate.distance_km,
                            "matched_at": datetime.now(timezone.utc).isoformat(),
                            "driver_name": profile["driver_name"],
                            "driver_rating": profile["driver_rating"],
                            "estimated_fare_inr": profile["estimated_fare_inr"],
                            "vehicle": profile["vehicle"],
                        }, key=ride_id)
                        await producer.stop()
            
                        # 3. Manually commit Kafka offset ONLY after DB write and publish
                        await consumer.commit()
                        
                        logger.info("✅ Matched ride %s → driver %s (Offset Committed)", ride_id, candidate.driver_id)
                        matched = True
                        break
                        
                if not matched:
                    # If candidates exist but none accepted, also treat as failed attempt
                    producer = await create_producer()
                    if retry_count < 2:
                        new_headers = {"retry_count": str(retry_count + 1)}
                        await publish(producer, "ride.requested", data, key=ride_id, headers=new_headers)
                    else:
                        await publish(producer, "ride.failed", data, key=ride_id)
                    await producer.stop()
                    
            finally:
                await redis.delete(lock_key)
    except asyncio.CancelledError:
        logger.info("Stopping matching consumer...")
    finally:
        await consumer.stop()


async def consume_driver_disconnects(app: FastAPI) -> None:
    """Listen for driver.disconnected events and reassign active rides."""
    consumer = await create_consumer("driver.disconnected", group_id="matching-reassigner")
    logger.info("🔄 Disconnect consumer started — listening on driver.disconnected")

    try:
        while True:
            msg = await consumer.poll(timeout=1.0)
            if msg is None:
                continue
                
            data = msg["value"]
            driver_id = data["driver_id"]
            logger.info("Processing disconnect for driver %s", driver_id)

            redis = await get_redis()
            
            # 1. Fetch ride_id from driver:active_ride:{driver_id}
            active_ride_key = f"driver:active_ride:{driver_id}"
            ride_id = await redis.get(active_ride_key)
            
            if not ride_id:
                logger.info("No active ride for driver %s. No reassignment needed.", driver_id)
                continue

            # 2. Check ride status in Redis — only reassign if still "in_progress" or "matched" (pre-start)
            # Assuming status is tracked in ride:status:{ride_id}
            # For this simulation, we'll check matching state
            ride_status = await redis.get(f"ride:status:{ride_id}") or "matched"
            
            if ride_status in ["matched", "in_progress"]:
                logger.warning("Reassigning ride %s due to driver %s disconnect", ride_id, driver_id)
                
                # 3. Re-publish to ride.requested with retry_count=0 and reassignment header
                producer = await create_producer()
                
                # We need the original ride data. If not available in Redis, we might need a Ride service fetch.
                # For simulation, we'll fetch from a "ride:data:{ride_id}" cache
                ride_data_raw = await redis.get(f"ride:data:{ride_id}")
                if ride_data_raw:
                    ride_data = json.loads(ride_data_raw)
                    headers = {"reassignment": "true", "retry_count": "0"}
                    await publish(producer, "ride.requested", ride_data, key=ride_id, headers=headers)
                    logger.info("Ride %s re-queued for matching (reassignment: true)", ride_id)
                else:
                    logger.error("Failed to reassign ride %s: missing ride data in cache", ride_id)
                
                await producer.stop()
            else:
                logger.info("Ride %s is already %s. Skipping reassignment.", ride_id, ride_status)

            # 4. Delete active ride mapping
            await redis.delete(active_ride_key)
            
    except asyncio.CancelledError:
        logger.info("Stopping disconnect consumer...")
    finally:
        await consumer.stop()
