FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libc-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY services/driver-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/driver-service/ .
COPY shared/ /app/shared

EXPOSE 8002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
