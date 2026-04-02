import asyncio
import random
from dataclasses import dataclass
from datetime import datetime

import httpx

DRIVER_SERVICE_BASE_URL = "http://localhost:8002/api/v1/drivers"
DRIVER_CREATE_URL = f"{DRIVER_SERVICE_BASE_URL}/"
CITY_LAT = 12.9716
CITY_LNG = 77.5946
DRIVER_COUNT = 100
RUN_TAG = datetime.utcnow().strftime("%H%M%S")


@dataclass
class Driver:
    driver_id: str
    lat: float
    lng: float
    status: str = "available"

    def move(self) -> None:
        self.lat += random.uniform(-0.001, 0.001)
        self.lng += random.uniform(-0.001, 0.001)


def random_vehicle_model() -> str:
    options = [
        "Honda Activa Scooter",
        "Bajaj Auto Rickshaw",
        "Maruti Suzuki Dzire",
        "Hyundai i20",
        "TVS Apache Bike",
    ]
    return random.choice(options)


async def register_driver(client: httpx.AsyncClient, index: int) -> Driver:
    lat = CITY_LAT + random.uniform(-0.09, 0.09)
    lng = CITY_LNG + random.uniform(-0.09, 0.09)
    last_error = None
    for attempt in range(1, 6):
        unique = random.randint(1000, 9999)
        payload = {
            "full_name": f"Mock Driver {index:03d}",
            "phone": f"9{RUN_TAG[-6:]}{index:02d}{attempt}"[:10],
            "email": f"mock_driver_{RUN_TAG}_{index:03d}_{unique}@swiftride.dev",
            "license_number": f"LIC-{RUN_TAG}-{index:03d}-{attempt}",
            "vehicle_model": random_vehicle_model(),
            "vehicle_plate": f"TN09{index:02d}{attempt:02d}{RUN_TAG[-2:]}",
        }

        response = await client.post(DRIVER_CREATE_URL, json=payload, timeout=15)
        if response.is_success:
            data = response.json()
            driver_id = data["id"]
            break
        last_error = f"{response.status_code}: {response.text}"
    else:
        raise RuntimeError(f"Unable to register driver {index}: {last_error}")

    await client.put(f"{DRIVER_SERVICE_BASE_URL}/{driver_id}/location", json={"lat": lat, "lng": lng}, timeout=15)
    await client.put(f"{DRIVER_SERVICE_BASE_URL}/{driver_id}/status", json={"status": "available"}, timeout=15)
    return Driver(driver_id=driver_id, lat=lat, lng=lng)


async def update_driver_loop(client: httpx.AsyncClient, driver: Driver) -> None:
    while True:
        try:
            driver.move()
            await client.put(
                f"{DRIVER_SERVICE_BASE_URL}/{driver.driver_id}/location",
                json={"lat": driver.lat, "lng": driver.lng},
                timeout=15,
            )
            await client.put(
                f"{DRIVER_SERVICE_BASE_URL}/{driver.driver_id}/status",
                json={"status": "available"},
                timeout=15,
            )
            await asyncio.sleep(5)
        except Exception:
            driver.status = "disconnected"
            await asyncio.sleep(2)


async def print_status_table(drivers: list[Driver]) -> None:
    while True:
        print("\n" + "=" * 95)
        print(f"{'Driver ID':<38} | {'Location':<18} | {'Status':<12} | {'Pool Size'}")
        print("-" * 95)
        for d in drivers[:10]:
            loc = f"{d.lat:.4f}, {d.lng:.4f}"
            print(f"{d.driver_id:<38} | {loc:<18} | {d.status:<12} | {len(drivers)}")
        print("=" * 95)
        await asyncio.sleep(10)


async def main() -> None:
    async with httpx.AsyncClient() as client:
        print(f"Registering {DRIVER_COUNT} mock drivers...")
        drivers: list[Driver] = []
        for idx in range(1, DRIVER_COUNT + 1):
            driver = await register_driver(client, idx)
            drivers.append(driver)

        print(f"{len(drivers)} drivers are now available and publishing live locations.")
        tasks = [asyncio.create_task(update_driver_loop(client, d)) for d in drivers]
        tasks.append(asyncio.create_task(print_status_table(drivers)))
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
