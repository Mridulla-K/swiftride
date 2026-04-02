#!/bin/bash
set -e

echo "⏳ Waiting for Kafka to be fully ready..."
cub kafka-ready -b kafka:9092 1 30 2>/dev/null || sleep 10

KAFKA_BIN="kafka-topics --bootstrap-server kafka:9092"

echo "📦 Creating Kafka topics..."

$KAFKA_BIN --create --if-not-exists \
  --topic ride.requested \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000 \
  --config cleanup.policy=delete

$KAFKA_BIN --create --if-not-exists \
  --topic driver.location \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=86400000 \
  --config cleanup.policy=delete

$KAFKA_BIN --create --if-not-exists \
  --topic ride.matched \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000 \
  --config cleanup.policy=delete

$KAFKA_BIN --create --if-not-exists \
  --topic ride.unmatched \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000 \
  --config cleanup.policy=delete

$KAFKA_BIN --create --if-not-exists \
  --topic ride.failed \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000 \
  --config cleanup.policy=delete

$KAFKA_BIN --create --if-not-exists \
  --topic driver.disconnected \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000 \
  --config cleanup.policy=delete

echo "✅ All topics created:"
$KAFKA_BIN --list
