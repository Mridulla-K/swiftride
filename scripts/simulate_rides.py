import asyncio
import httpx
import random
import uuid
from colorama import init, Fore, Style

init(autoreset=True)

CHENNAI_LAT = 12.9716
CHENNAI_LNG = 80.2209
API_BASE = "http://localhost:8004/api/v1/rides"
PRICING_API = "http://localhost:8005/api/v1/pricing"

class RideSimulator:
    def __init__(self):
        self.rider_id = str(uuid.uuid4())
        self.pickup_lat = CHENNAI_LAT + random.uniform(-0.045, 0.045)
        self.pickup_lng = CHENNAI_LNG + random.uniform(-0.045, 0.045)
        self.dropoff_lat = CHENNAI_LAT + random.uniform(-0.045, 0.045)
        self.dropoff_lng = CHENNAI_LNG + random.uniform(-0.045, 0.045)
        self.ride_id = None
        
    async def simulate(self):
        async with httpx.AsyncClient() as client:
            payload = {
                "rider_id": self.rider_id,
                "pickup_lat": self.pickup_lat,
                "pickup_lng": self.pickup_lng,
                "dropoff_lat": self.dropoff_lat,
                "dropoff_lng": self.dropoff_lng,
                "pickup_address": f"Lat {self.pickup_lat:.4f}, Lng {self.pickup_lng:.4f}",
                "dropoff_address": f"Lat {self.dropoff_lat:.4f}, Lng {self.dropoff_lng:.4f}"
            }
            try:
                response = await client.post(f"{API_BASE}/", json=payload)
                if response.status_code == 429:
                    print(Fore.RED + f"Rate limited for rider {self.rider_id}. Retrying later.")
                    return
                response.raise_for_status()
                data = response.json()
                self.ride_id = data["id"]
                print(Fore.YELLOW + f"Ride {self.ride_id} requested. Searching for driver...")
            except Exception as e:
                print(Fore.RED + f"Failed to request ride: {e}")
                return

            for _ in range(15):
                await asyncio.sleep(3)
                try:
                    res = await client.get(f"{API_BASE}/{self.ride_id}")
                    if res.status_code == 200:
                        ride_data = res.json()
                        status = ride_data.get("status")
                        if status == "matched":
                            driver = ride_data.get("driver_id")
                            try:
                                p_res = await client.post(f"{PRICING_API}/estimate", json={
                                    "pickup_lat": self.pickup_lat,
                                    "pickup_lng": self.pickup_lng,
                                    "dropoff_lat": self.dropoff_lat,
                                    "dropoff_lng": self.dropoff_lng
                                })
                                p_data = p_res.json()
                                fare = p_data.get("final_fare")
                                eta = p_data.get("eta_minutes")
                                print(Fore.GREEN + f"✅ Ride {self.ride_id} matched! Driver: {driver} | Fare: ${fare} | ETA: {eta} mins")
                            except Exception:
                                print(Fore.GREEN + f"✅ Ride {self.ride_id} matched! Driver: {driver} | Fare/ETA error")
                            return
                        elif status in ("unmatched", "cancelled"):
                            print(Fore.RED + f"❌ Ride {self.ride_id} failed: {status}")
                            return
                except Exception:
                    pass
            print(Fore.RED + f"❌ Ride {self.ride_id} matched timeout/abandoned.")

async def run_batch():
    simulators = [RideSimulator() for _ in range(5)]
    tasks = [sim.simulate() for sim in simulators]
    await asyncio.gather(*tasks)

async def main():
    print(Style.BRIGHT + "Starting ride simulation... Spawning 5 requests every 30s")
    while True:
        print(Style.DIM + "\n--- Spawning new ride requests batch ---")
        asyncio.create_task(run_batch())
        await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
