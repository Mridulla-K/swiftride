# SwiftRide — Microservice Monorepo

SwiftRide is a high-performance ride-hailing backend architecture built with FastAPI, PostgreSQL, Redis, and Kafka.

---



---

## 📂 Project Structure

- `/services/` — Microservices implemented with FastAPI & SQLAlchemy.
  - `user-service`: User authentication & profiles.
  - `driver-service`: Driver management and real-time location.
  - `matching-service`: Proximity-based matching logic (Kafka consumer).
  - `ride-service`: Full ride lifecycle (request, start, complete, cancel).
  - `pricing-service`: Dynamic fare calculation.
- `/infra/` — Deployment and management infrastructure.
  - `docker-compose.yml`: Local development environment setup.
  - `kafka/`: Kafka topic configurations and initialization scripts.
- `shared/` — Common library with DB models, Kafka helpers, and global config.

---

## 🚀 Getting Started

### Prerequisites
- Docker & Docker Compose
- Python 3.12+

### Local Setup

1. **Clone the repository**
2. **Setup environment variables**
   ```bash
   cp .env.example .env
   ```
3. **Spin up the infrastructure & services**
   ```bash
   cd infra
   docker-compose up -d --build
   ```
   *Note: This will automatically start PostgreSQL, Redis, Kafka, and all five FastAPI services.*

4. **Verify services are running**
   - User Service: [http://localhost:8001/docs](http://localhost:8001/docs)
   - Driver Service: [http://localhost:8002/docs](http://localhost:8002/docs)
   - Matching Service: [http://localhost:8003/docs](http://localhost:8003/docs)
   - Ride Service: [http://localhost:8004/docs](http://localhost:8004/docs)
   - Pricing Service: [http://localhost:8005/docs](http://localhost:8005/docs)

---

## 🎮 Running the Full Demo

To see the complete system in action — including real-time driver movement, automated ride requests, and the visual dashboard — use the integrated startup scripts.

### On Windows (PowerShell)
```powershell
.\scripts\start_demo.ps1
```

### On macOS / Linux (Bash)
```bash
bash scripts/start_demo.sh
```

**What these scripts do:**
1.  Verify all Docker containers are running and **Healthy**.
2.  Install local Python dependencies for the simulators (`websockets`, `httpx`, `colorama`).
3.  Start the **Driver Simulator** (spawns 10 mock drivers in Chennai via WebSockets).
4.  Start the **Ride Simulator** (submits batches of ride requests every 30s).
5.  Automatically open the **Stitch Frontend Dashboard** in your default browser.

---

## 📦 Kafka Messaging Flow

1. **Rider requests a ride**: `Ride Service` publishes `ride.requested` to Kafka.
2. **Drivers heartbeat location**: `Driver Service` publishes `driver.location` to Kafka and updates Redis GEO set.
3. **Matching Engine**: `Matching Service` consumes `ride.requested`, performs a GEORADIUS search in Redis, and publishes `ride.matched` to Kafka.
4. **Ride Assignment**: `Ride Service` and `Driver Service` consume `ride.matched` to update state and notify parties.

---

## 📝 Configuration

All services use a shared `shared.config` module that reads from the root `.env` file. Modify the `.env` file to customize database connections, Kafka bootstrap servers, and pricing rates.
