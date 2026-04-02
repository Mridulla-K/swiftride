import asyncio
import time
import httpx
import uuid
import statistics
import random

# Basic config
BASE_URL = "http://localhost:8000/api/v1/rides/"
CONCURRENT_REQUESTS = 50
PICKUP_LAT_RANGE = (12.90, 13.00)
PICKUP_LNG_RANGE = (77.50, 77.60)

async def send_ride_request(client, rider_id):
    payload = {
        "rider_id": str(rider_id),
        "pickup_lat": random.uniform(*PICKUP_LAT_RANGE),
        "pickup_lng": random.uniform(*PICKUP_LNG_RANGE),
        "dropoff_lat": random.uniform(*PICKUP_LAT_RANGE),
        "dropoff_lng": random.uniform(*PICKUP_LNG_RANGE),
        "pickup_address": "Test Pickup Point",
        "dropoff_address": "Test Dropoff Point"
    }
    
    start_time = time.perf_counter()
    try:
        response = await client.post("/", json=payload)
        response_time = (time.perf_counter() - start_time) * 1000 # to ms
        return response.status_code, response_time
    except Exception as e:
        return 500, (time.perf_counter() - start_time) * 1000

async def run_load_test():
    print(f"🚀 Starting load test: {CONCURRENT_REQUESTS} concurrent requests...")
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        tasks = []
        for _ in range(CONCURRENT_REQUESTS):
            tasks.append(send_ride_request(client, uuid.uuid4()))
        
        results = await asyncio.gather(*tasks)
    
    status_codes = [r[0] for r in results]
    response_times = [r[1] for r in results]
    
    success_count = status_codes.count(201)
    error_count = len(status_codes) - success_count
    
    avg_time = statistics.mean(response_times)
    p95_time = statistics.quantiles(response_times, n=20)[18] # 95th percentile
    max_time = max(response_times)
    min_time = min(response_times)
    
    print("\n" + "="*40)
    print("📊 LOAD TEST SUMMARY")
    print("="*40)
    print(f"Requests: {CONCURRENT_REQUESTS}")
    print(f"Success:  {success_count} ({(success_count/CONCURRENT_REQUESTS)*100:.1f}%)")
    print(f"Errors:   {error_count}")
    print("-" * 40)
    print(f"Min Time: {min_time:.2f}ms")
    print(f"Max Time: {max_time:.2f}ms")
    print(f"Avg Time: {avg_time:.2f}ms")
    print(f"p95 Time: {p95_time:.2f}ms")
    print("-" * 40)
    
    if p95_time < 200:
        print("✅ PERFORMANCE ASSERTION PASSED (p95 < 200ms)")
    else:
        print("❌ PERFORMANCE ASSERTION FAILED (p95 >= 200ms)")
    print("="*40)

if __name__ == "__main__":
    asyncio.run(run_load_test())
